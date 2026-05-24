# cpr_position_buffer.py
# ================================================================
#  CPR POSITION BUFFER
#  ----------------------------------------------------------------
#  WHY THIS FILE EXISTS:
#
#  ADS-B airborne position (TC 9-18) uses Compact Position Reporting
#  (CPR). A SINGLE position message is NOT enough to compute the
#  real latitude/longitude. You need TWO messages from the SAME
#  aircraft:
#       - one EVEN  (cpr_format == 0)
#       - one ODD   (cpr_format == 1)
#
#  This module acts as a "waiting room":
#  1. When we get an EVEN message  → store it, wait for the ODD.
#  2. When we get an ODD  message  → store it, wait for the EVEN.
#  3. When we have BOTH for the same ICAO → decode the real position
#     using pyModeS, return the completed record, clear the slot.
#
#  The JSON file is only written AFTER step 3 — never before.
#  This is exactly what the book "The 1090 MHz Riddle" (Sun, 2021)
#  describes in Chapter 5 (Globally Unambiguous Position Decoding).
#
# ================================================================
#  TIMEOUT — WHY SAMPLES, NOT WALL-CLOCK SECONDS
# ----------------------------------------------------------------
#  The standard says: the two CPR messages must be from within
#  10 seconds of SIGNAL TIME (i.e. RF recording time), not
#  processing time.
#
#  Your data comes from a binary file processed much faster than
#  real time. 10 wall-clock seconds of processing could correspond
#  to only 2 ms of RF signal — or vice versa. Wall-clock time is
#  therefore meaningless here.
#
#  The correct unit is SAMPLE INDEX (shift_index in your code).
#
#  Math:
#    Sampling rate            = 2,000,000 samples/second  (2 MSPS)
#    Each sample is one IQ pair = 2 bytes in the .bin file
#    10 seconds of RF time    = 10 × 2,000,000 = 20,000,000 samples
#
#  So the timeout is:
#    CPR_TIMEOUT_SAMPLES = 10 × 2,000,000 = 20,000,000  samples
#
#  When a new message arrives at shift_index N, any stored message
#  whose shift_index is older than  N - 20,000,000  is discarded.
#
#  This correctly mirrors pyModeS's 10-second requirement, but
#  measured in the signal's own time axis — regardless of how fast
#  or slow the file is being processed on your CPU.
# ================================================================

import pyModeS as pms

# ── Timeout in samples ────────────────────────────────────────────────────
SAMPLE_RATE      = 2_000_000          # 2 MSPS  (RTL-SDR at 1090 MHz)
CPR_TIMEOUT_RF_S = 10                 # 10 seconds of RF / signal time
CPR_TIMEOUT_SAMPLES = SAMPLE_RATE * CPR_TIMEOUT_RF_S   # = 20,000,000 samples

# ── Internal storage ──────────────────────────────────────────────────────
# Structure:
# {
#   "icao_hex": {
#       "even": { "hex_msg": str,
#                 "shift_index": int,     ← sample position in the .bin file
#                 "record": dict },
#       "odd":  { "hex_msg": str,
#                 "shift_index": int,
#                 "record": dict }
#   }
# }
_buffer = {}


def _purge_expired(current_shift_index):
    """
    Discard any stored CPR message whose sample index is more than
    CPR_TIMEOUT_SAMPLES behind the current message.

    Called automatically every time a new message arrives so the
    buffer never accumulates stale half-pairs.

    Parameters
    ----------
    current_shift_index : int
        The shift_index of the message currently being processed.
        Used as the reference "now" in sample space.
    """
    expired = []
    for icao, slot in _buffer.items():
        for fmt in ("even", "odd"):
            if fmt in slot:
                age_samples = current_shift_index - slot[fmt]["shift_index"]
                if age_samples > CPR_TIMEOUT_SAMPLES:
                    expired.append((icao, fmt))
                    print(
                        f"[CPR] ⚠ Expired {fmt.upper()} for ICAO {icao.upper()} — "
                        f"age={age_samples:,} samples "
                        f"({age_samples / SAMPLE_RATE:.2f} s RF time > "
                        f"{CPR_TIMEOUT_RF_S} s limit)"
                    )

    for icao, fmt in expired:
        if icao in _buffer and fmt in _buffer[icao]:
            del _buffer[icao][fmt]
        # Remove the ICAO entry entirely if both slots are now empty
        if icao in _buffer and not _buffer[icao]:
            del _buffer[icao]


def attempt_position_decode(icao, cpr_format_str, hex_msg, partial_record):
    """
    Main entry point — called by export_message() in SignalVisualizer.py
    for every AIRBORNE_POSITION (TC 9-18) or SURFACE_POSITION (TC 5-8).

    Parameters
    ----------
    icao            : str   e.g. "4840d6"
    cpr_format_str  : str   "Even" or "Odd"
    hex_msg         : str   full 28-char hex ADS-B message
    partial_record  : dict  record dict built so far in export_message()
                            — must contain "shift_index" (int)

    Returns
    -------
    dict or None
        dict  → pair decoded, real lat/lon filled in, ready to write JSON
        None  → still waiting for the opposite CPR format; do NOT write JSON
    """

    icao = icao.lower().strip()
    fmt  = cpr_format_str.lower()          # "even" or "odd"

    if fmt not in ("even", "odd"):
        print(f"[CPR] Unknown format '{cpr_format_str}' for ICAO {icao} — skipped")
        return None

    # The sample index of this message — used as "time" in sample space
    current_idx = partial_record.get("shift_index")
    if current_idx is None:
        print(f"[CPR] Missing shift_index in record for ICAO {icao} — skipped")
        return None

    # Purge any messages that are too old (in sample space) before doing anything
    _purge_expired(current_idx)

    opposite = "odd" if fmt == "even" else "even"

    # Initialise slot for this ICAO on first appearance
    if icao not in _buffer:
        _buffer[icao] = {}

    # Store this message in the buffer
    _buffer[icao][fmt] = {
        "hex_msg":     hex_msg,
        "shift_index": current_idx,
        "record":      partial_record,
    }

    print(
        f"[CPR] Stored {fmt.upper()} for ICAO {icao.upper()} "
        f"at sample {current_idx:,} — "
        f"waiting for {opposite.upper()}"
    )

    # Do we now have both formats?
    if opposite not in _buffer[icao]:
        print(
            f"[CPR] ⏳ No {opposite.upper()} yet for ICAO {icao.upper()} "
            f"— holding in buffer"
        )
        return None    # ← caller must NOT write JSON

    # ── Both EVEN and ODD are present — check their sample gap ───────────
    even_slot = _buffer[icao]["even"]
    odd_slot  = _buffer[icao]["odd"]

    idx_even = even_slot["shift_index"]
    idx_odd  = odd_slot["shift_index"]
    gap_samples = abs(idx_even - idx_odd)
    gap_rf_s    = gap_samples / SAMPLE_RATE

    print(
        f"[CPR] Pair found for ICAO {icao.upper()} — "
        f"gap={gap_samples:,} samples ({gap_rf_s:.3f} s RF time)"
    )

    # Final safety check: gap must be within the 10-second RF window
    # (purge_expired should have caught this, but double-check)
    if gap_samples > CPR_TIMEOUT_SAMPLES:
        print(
            f"[CPR] ✗ Gap too large ({gap_rf_s:.1f} s > {CPR_TIMEOUT_RF_S} s) "
            f"— discarding pair for ICAO {icao.upper()}"
        )
        del _buffer[icao]
        return None

    # ── Call pyModeS to decode the real lat/lon ───────────────────────────
    #
    # pms.adsb.position() expects timestamps in seconds.
    # We convert sample indices → RF seconds by dividing by SAMPLE_RATE.
    # The absolute value does not matter — only the DIFFERENCE matters
    # (pyModeS uses it to decide which message is more recent).
    #
    t_even = idx_even / SAMPLE_RATE    # e.g. 12345678 / 2000000 = 6.17 s
    t_odd  = idx_odd  / SAMPLE_RATE

    msg_even = even_slot["hex_msg"]
    msg_odd  = odd_slot["hex_msg"]

    print(f"[CPR] Decoding position for ICAO {icao.upper()} ...")

    try:
        lat, lon = pms.adsb.position(msg_even, msg_odd, t_even, t_odd)
    except Exception as e:
        print(f"[CPR] ✗ pyModeS decode failed for {icao.upper()}: {e}")
        del _buffer[icao]
        return None

    if lat is None or lon is None:
        print(f"[CPR] ✗ pyModeS returned None for {icao.upper()} — discarding")
        del _buffer[icao]
        return None

    print(f"[CPR] ✅ ICAO {icao.upper()} → lat={lat:.6f}  lon={lon:.6f}")

    # ── Build the final complete record ───────────────────────────────────
    # Use the record of the MORE RECENT message as the base
    # (it carries the latest altitude, SNR, shift_index)
    if idx_even >= idx_odd:
        final_record = dict(even_slot["record"])
        final_record["cpr_format"] = "Even"
    else:
        final_record = dict(odd_slot["record"])
        final_record["cpr_format"] = "Odd"

    # Fill in the properly decoded position
    final_record["latitude"]         = round(lat, 6)
    final_record["longitude"]        = round(lon, 6)
    final_record["raw_cpr_lat"]      = None   # real position known — raw no longer needed
    final_record["raw_cpr_lon"]      = None
    final_record["position_source"]  = "CPR_GLOBALLY_DECODED"

    # Keep both hex messages for reference / debugging
    final_record["cpr_even_hex"]     = msg_even
    final_record["cpr_odd_hex"]      = msg_odd

    # Store gap in both samples and RF seconds for the JSON / Firebase
    final_record["cpr_gap_samples"]  = gap_samples
    final_record["cpr_gap_rf_s"]     = round(gap_rf_s, 4)

    # ── Consumed — clear the buffer slot ─────────────────────────────────
    del _buffer[icao]

    return final_record


def get_buffer_status():
    """
    Returns a human-readable summary of what is currently in the buffer.
    Useful for debugging.

    Example output:
        { "4840d6": ["even"], "70602d": ["odd"] }
    """
    return {icao: list(slot.keys()) for icao, slot in _buffer.items()}