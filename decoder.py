# =============================================================================
#  ADS_B_Decoder.py
#  Merged ADS-B Signal Decoder & Visualizer
# =============================================================================
#
#  ARCHITECTURE SUMMARY:
#  ─────────────────────
#  This file combines two previous versions:
#
#  From SignalVisualizer2.py  (the FAST version):
#    • Chunked file streaming  — reads 100k samples at a time, never loads
#      the full file into RAM. Handles files of any size.
#    • Overlap buffer          — 256-sample overlap between chunks prevents
#      missing preambles that straddle a chunk boundary.
#    • Single-pass 4-criteria  — C2, C3, C4 are tested inside the C1 loop,
#      so failing candidates are discarded immediately. No wasted iterations.
#
#  From SignalVisualizer.py   (the ADVANCED version):
#    • export_message()        — builds a complete, clean JSON record with
#      all decoded fields, DB lookup, and CPR metadata.
#    • aircraft_lookup.py      — instant ICAO → registration/operator/model
#      lookup from a 500k-row CSV loaded once into a dict.
#    • cpr_position_buffer.py  — waits for an EVEN+ODD pair before writing
#      the JSON, then calls pyModeS to decode the real lat/lon.
#    • adsb_to_firebase.py     — file watcher that pushes every JSON file
#      to Firestore in real time (run in a separate terminal).
#
#  FIXES APPLIED IN THIS MERGE:
#  ─────────────────────────────
#  FIX 1 — Visualization: was plotting chunk_mag (last chunk) instead of
#           vis_Magnitude (the user-selected slice). Now correctly uses
#           vis_Magnitude for both the signal plot and the correlation plot.
#
#  FIX 2 — CPR format: pms.decode() does NOT reliably return a "cpr_format"
#           key. Both versions fell back to reading bit 53 of the binary
#           string, but only after a failed dict lookup. Now the binary bit
#           is always the primary source — no ambiguity.
#
#  FIX 3 — Bit_Slicer for C2 in process_chunk: the original built a Python
#           list from window slices, then passed it as the "value" to
#           Bit_Slicer which iterates it with an integer index. This works
#           only because list supports integer indexing. Kept as-is but
#           documented clearly.
#
#  HOW TO RUN:
#  ────────────
#  Terminal 1:  python ADS_B_Decoder.py
#  Terminal 2:  python adsb_to_firebase.py      (optional — Firebase push)
#
#  COMPANION FILES REQUIRED (unchanged from the advanced version):
#    cpr_position_buffer.py
#    aircraft_lookup.py
#    adsb_to_firebase.py
#    aircraft-database.csv
#    serviceAccountKey.json   (only if you use Firebase)
#
# =============================================================================

import math
import os
import datetime
import json
import threading

import matplotlib
matplotlib.use("TkAgg")          # explicit backend — avoids blank-window bug
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.widgets import Button, TextBox

import pyModeS as pms
from pyModeS.util import bin2hex

# ── Companion modules from the advanced version ───────────────────────────────
from aircraft_lookup    import lookup, load_database
from cpr_position_buffer import attempt_position_decode, get_buffer_status

# =============================================================================
#  CONFIGURATION
# =============================================================================

SAMPLE_RATE    = 2_000_000          # 2 MSPS — RTL-SDR at 1090 MHz
CHUNK_SAMPLES  = 100_000            # IQ pairs per processing chunk
OVERLAP        = 256                # samples carried from chunk to next chunk
DC_SHIFT       = 0.7               # DC offset correction for magnitude
C1_THRESHOLD   = 8                 # CFAR ratio threshold for Criterion 1
C3_THRESHOLD   = 5.656             # max peak/min ratio for Criterion 3
C4_MIN_NULLS   = 2                 # minimum null pairs required for C4

OUTPUT_DIR     = "output"
AIRCRAFT_DB    = "aircraft-database.csv"

# Preamble reference for 1090 MHz Mode S  (26-element α-pattern)
# α-positions 0,2,7,9,16,19,21,23,24 are HIGH — all others are LOW
# Source: Sun (2021) "The 1090 MHz Riddle", Chapter 2, Figure 1.4
PREAMBLE_TEMPLATE = np.zeros(26)
for _p in [0, 2, 7, 9, 16, 19, 21, 23, 24]:
    PREAMBLE_TEMPLATE[_p] = 1

# Deterministic 9-bit pattern expected at the start of a DF=17 (ADS-B) preamble
# Derived from the fixed preamble bit sequence: 1100 1000 1
C2_REFERENCE = "110010001"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# =============================================================================
#  STARTUP: Load aircraft database once
# =============================================================================

print("[INIT] Loading aircraft database …")
try:
    load_database(AIRCRAFT_DB)
    print("[INIT] Aircraft database ready.")
except FileNotFoundError:
    print(f"[INIT] WARNING: {AIRCRAFT_DB} not found — DB lookup disabled.")

# =============================================================================
#  SECTION 1 — SIGNAL PROCESSING UTILITIES
# =============================================================================

def raw_bytes_to_magnitude(raw_bytes):
    """
    Convert a block of raw RTL-SDR bytes to a list of magnitude floats.

    RTL-SDR interleaves I and Q samples as unsigned 8-bit integers.
    The centre value is 127.5 (midpoint of 0–255).
    Magnitude = sqrt(I² + Q²) − DC_SHIFT

    The DC_SHIFT removes the small positive bias caused by the integer
    centring and improves preamble detection reliability.

    Parameters
    ----------
    raw_bytes : bytes
        Raw binary data from the .bin file. Must have even length.

    Returns
    -------
    list of float
        One magnitude value per IQ pair (len = len(raw_bytes) // 2).
    """
    magnitude = []
    for i in range(0, len(raw_bytes) - 1, 2):
        I = raw_bytes[i]     - 127.5
        Q = raw_bytes[i + 1] - 127.5
        magnitude.append(math.sqrt(I * I + Q * Q) - DC_SHIFT)
    return magnitude


def compute_snr(index, signal):
    """
    Estimate the Signal-to-Noise Ratio at a preamble candidate position.

    Method  (from Sun 2021, Section 2.1):
      - Signal power : mean square of the 224 samples of the message body.
      - Noise power  : mean square of 224 samples BEFORE the preamble.
    SNR (dB) = 10 * log10( signal_power / noise_power )

    Parameters
    ----------
    index  : int   — local index of the preamble start in the signal list
    signal : list  — magnitude values

    Returns
    -------
    float  SNR in dB, or 0.0 if noise is zero / insufficient samples.
    """
    sig_window   = signal[index:        index + 224]
    noise_window = signal[max(0, index - 225): max(0, index - 1)]

    if len(sig_window) < 10 or len(noise_window) < 10:
        return 0.0

    sig_power   = (sum(sig_window)   ** 2) / len(sig_window)
    noise_power = (sum(noise_window) ** 2) / len(noise_window)

    if noise_power <= 0:
        return 0.0

    return round(10 * math.log10(sig_power / noise_power), 2)


def slice_bits_from_samples(samples, msg_length=224):
    """
    Convert PPM-encoded magnitude samples into a binary string.

    In Mode S PPM encoding, each bit occupies 2 samples (0.5 µs each).
    Bit = 1 if samples[k] >= samples[k+1]
    Bit = 0 if samples[k] <  samples[k+1]
    (Sun 2021, Chapter 1, Section 1.4.2 — PPM modulation)

    Parameters
    ----------
    samples    : list of float   — magnitude values, length must be msg_length
    msg_length : int             — number of samples (112 bits × 2 = 224)

    Returns
    -------
    str   — binary string of length msg_length // 2, e.g. "10001101…"
    """
    bits = []
    for k in range(0, msg_length, 2):
        bits.append('1' if samples[k] >= samples[k + 1] else '0')
    return "".join(bits)

# =============================================================================
#  SECTION 2 — FOUR-CRITERION PREAMBLE DETECTOR
# =============================================================================
#
#  The 4-criterion algorithm matches the multi-layer filtering described in:
#  "A Novel Multi-Criteria Preamble Detection Algorithm for ADS-B Signals"
#  (the paper you also uploaded to your project).
#
#  Criterion 1 — CFAR Correlation:
#    Correlate the signal with the 26-sample preamble template.
#    Compute a local peak-to-valley ratio. Accept if ratio > C1_THRESHOLD.
#    Valleys are 5 samples chosen from positions before the peak that
#    correspond to known null zones.
#
#  Criterion 2 — Deterministic Symbol Match:
#    The first 9 bits of a valid DF=17 preamble always decode to "110010001".
#    Extract 18 samples (9 pairs), slice to 9 bits, compare to reference.
#
#  Criterion 3 — Consistent Power Test:
#    The 9 α-position samples must all be roughly the same amplitude.
#    If max/min > C3_THRESHOLD, the signal has too much amplitude variation
#    to be a valid preamble — likely noise.
#
#  Criterion 4 — Null Symbol Validation:
#    The 4 β-intervals (null pairs at positions 4-5, 10-11, 12-13, 14-15)
#    must be below half the mean α-amplitude. At least C4_MIN_NULLS must pass.

def process_chunk(signal, byte_offset, overlap_len,
                  total_c1, total_c2, total_c3, total_c4,
                  export_fn):
    """
    Run the 4-criterion preamble detector on one chunk of signal data.

    IMPORTANT: 'signal' = overlap_buffer + current_chunk_magnitude.
    The first overlap_len samples belong to the END of the previous chunk.
    Their global byte position is (byte_offset - overlap_len * 2).

    Global byte address of signal[i]:
        global_sample = (byte_offset // 2) - overlap_len + i
        global_byte   = global_sample * 2

    Parameters
    ----------
    signal       : list of float — overlap buffer + this chunk's magnitude
    byte_offset  : int           — file byte position of the FIRST byte of
                                   this chunk (not counting the overlap)
    overlap_len  : int           — number of overlap samples prepended
    total_c1/2/3/4 : int        — running counters (for display)
    export_fn    : callable      — called with (local_idx, global_sample,
                                   c1_ratio, c3_ratio, c4_count, signal)
                                   when all 4 criteria pass

    Returns
    -------
    (total_c1, total_c2, total_c3, total_c4, c1_candidates_list)
    """

    # ── CRITERION 1: CFAR Correlation ────────────────────────────────────────
    # np.correlate computes a dot-product of signal vs PREAMBLE_TEMPLATE at
    # every position. High correlation = the signal looks like the preamble.
    # "valid" mode: output length = len(signal) - len(template) + 1
    correlation = np.correlate(signal, PREAMBLE_TEMPLATE, mode="valid")

    # CFAR (Constant False Alarm Rate) thresholding:
    # Instead of a fixed threshold, compare the peak to nearby valley samples.
    # This adapts to local noise level — critical for ADS-B where signal
    # strength varies enormously depending on aircraft range.
    c1_candidates = {}   # { local_index: c1_ratio }

    for i in range(20, len(correlation)):
        # valley_avg: average of 5 correlation values at known null positions
        # These offsets (6, 11, 13, 18, 20) place us in β-intervals before i
        valley_avg = 0.2 * (
            correlation[i - 6]  +
            correlation[i - 11] +
            correlation[i - 13] +
            correlation[i - 18] +
            correlation[i - 20]
        )

        if valley_avg < 0.001:    # skip if noise floor is essentially zero
            continue

        ratio = correlation[i] / valley_avg

        if ratio > C1_THRESHOLD:
            if c1_candidates:
                last_idx = list(c1_candidates)[-1]
                if i - last_idx < 240:
                    # Two peaks within 240 samples = same preamble re-triggered.
                    # Keep only the stronger one to avoid double-counting.
                    if ratio > list(c1_candidates.values())[-1]:
                        c1_candidates.popitem()
                        c1_candidates[i] = ratio
                else:
                    c1_candidates[i] = ratio
            else:
                c1_candidates[i] = ratio

    total_c1 += len(c1_candidates)

    # ── CRITERIA 2 / 3 / 4: cascade filter on each C1 candidate ─────────────
    # By running C2, C3, C4 immediately inside this loop, any failing candidate
    # is discarded without ever reaching the next criterion.
    # This is the key speed advantage over the original single-pass approach.

    for local_idx, c1_ratio in c1_candidates.items():

        # Safety: need at least 26 samples ahead for the preamble window,
        # plus 224 more for the message body = 250 total from local_idx
        if local_idx + 250 > len(signal):
            continue

        window = signal[local_idx: local_idx + 26]

        # ── CRITERION 2: Deterministic Symbol Match ───────────────────────────
        # Assemble 18 samples covering the first 9 symbol pairs of the preamble.
        # Pairs come from α-positions: (0,1), (2,3), (6,7), (8,9) → first 4 pairs
        # then (16,17),(18,19),(20,21),(22,23),(24,25) → last 5 pairs
        # window[0:4]  = samples at positions 0,1,2,3  → pairs (0,1) and (2,3)
        # window[6:10] = samples at positions 6,7,8,9  → pairs (6,7) and (8,9)
        # window[16:]  = samples at positions 16…25    → last 5 pairs
        samples_c2 = window[0:4] + window[6:10] + window[16:]
        decoded_9  = slice_bits_from_samples(samples_c2, msg_length=18)

        if decoded_9 != C2_REFERENCE:
            continue    # C2 failed — not a valid DF=17 preamble start

        total_c2 += 1

        # ── CRITERION 3: Consistent Power Test ───────────────────────────────
        # Extract the 9 α-position magnitudes.
        # If one is much larger than others, this is not a coherent preamble.
        alpha_samples = [
            window[0],  window[2],  window[7],  window[9],
            window[16], window[19], window[21], window[23], window[24]
        ]

        peak_min = min(alpha_samples)
        if peak_min <= 0:
            continue    # avoid division by zero

        c3_ratio = max(alpha_samples) / peak_min

        if c3_ratio >= C3_THRESHOLD:
            continue    # C3 failed — too much amplitude variation

        total_c3 += 1

        # ── CRITERION 4: Null Symbol Validation ──────────────────────────────
        # β-positions are the null intervals between α-pulses.
        # Their amplitude should be below half the mean α-amplitude (sigma/2).
        sigma = sum(alpha_samples) / 9   # dynamic threshold = mean of α-samples

        null_pairs = [
            (window[4],  window[5]),    # β-interval 1
            (window[10], window[11]),   # β-interval 2
            (window[12], window[13]),   # β-interval 3
            (window[14], window[15]),   # β-interval 4
        ]

        null_count = sum(
            1 for s1, s2 in null_pairs
            if s1 <= sigma / 2 and s2 <= sigma / 2
        )

        if null_count < C4_MIN_NULLS:
            continue    # C4 failed — null intervals not sufficiently quiet

        # ── ALL 4 CRITERIA PASSED ─────────────────────────────────────────────
        total_c4 += 1

        # Compute global sample index (position in the full .bin file)
        # signal[0] = first overlap sample = end of previous chunk
        # signal[local_idx] is at file position:
        #   global_sample = (byte_offset // 2) - overlap_len + local_idx
        global_sample = (byte_offset // 2) - overlap_len + local_idx

        # Call the export function — this handles decoding, DB lookup,
        # CPR buffering, and writing JSON to the output/ folder
        export_fn(local_idx, global_sample, c1_ratio, c3_ratio, null_count, signal)

    return total_c1, total_c2, total_c3, total_c4, list(c1_candidates.keys())

# =============================================================================
#  SECTION 3 — DECODING AND EXPORT PIPELINE
# =============================================================================

def build_record(local_idx, global_sample, c1_ratio, c3_ratio, c4_count, signal,
                 capture_file):
    """
    Extract the 112-bit message body from the signal, decode it with pyModeS,
    and build a complete record dictionary with all fields.

    This is the 'brain' of the output pipeline. It fills every field from
    signal metadata, pyModeS decoded values, and prepares CPR fields.
    Aircraft DB lookup and CPR position decoding happen in export_message().

    Parameters
    ----------
    local_idx     : int   — index of preamble start in the local signal list
    global_sample : int   — absolute sample index in the full .bin file
    c1_ratio      : float — CFAR ratio from Criterion 1
    c3_ratio      : float — power ratio from Criterion 3
    c4_count      : int   — number of null pairs that passed Criterion 4
    signal        : list  — the magnitude samples (overlap + chunk)
    capture_file  : str   — path to the source .bin file

    Returns
    -------
    dict  — the complete record (no JSON file written yet)
    """

    # ── Extract the 224-sample message body (after the 16-sample preamble) ──
    msg_start  = local_idx + 16
    msg_end    = msg_start + 224

    if msg_end > len(signal):
        return None   # message body extends beyond the current signal buffer

    msg_samples = signal[msg_start: msg_end]
    bin_str     = slice_bits_from_samples(msg_samples, msg_length=224)

    # ── Build the base record — all fields set to None initially ─────────────
    record = {
        # Signal / detection metadata
        "shift_index":        global_sample,
        "captured_at":        datetime.datetime.utcnow().isoformat() + "Z",
        "capture_file":       capture_file,
        "sample_rate_msps":   SAMPLE_RATE // 1_000_000,
        "final_decision":     True,
        "snr_db":             compute_snr(local_idx, signal),
        "c1_ratio":           round(c1_ratio,  3),
        "c2_match":           True,
        "c3_power_ratio":     round(c3_ratio,  4),
        "c4_null_count":      int(c4_count),

        # Aircraft database fields (filled by _db_lookup below)
        "registration":       None, "manufacturericao": None,
        "manufacturername":   None, "model":            None,
        "typecode_db":        None, "serialnumber":     None,
        "linenumber":         None, "icaoaircrafttype": None,
        "operator":           None, "operatorcallsign": None,
        "operatoricao":       None, "operatoriata":     None,
        "owner":              None, "testreg":          None,
        "registered":         None, "reguntil":         None,
        "status":             None, "built":            None,
        "firstflightdate":    None, "seatconfiguration":None,
        "engines":            None, "modes":            None,
        "adsb_equipped":      None, "acars":            None,
        "notes":              None, "categoryDescription": None,

        # Decoded ADS-B fields
        "hex_message":        None,
        "bin_str":            bin_str,   # kept internally for CPR bit extraction
        "crc_valid":          False,
        "icao":               None,
        "typecode":           None,
        "df":                 None,
        "message_type":       "UNKNOWN",

        # Position (filled by CPR buffer for TC 9-18)
        "altitude_ft":        None, "altitude_m":      None,
        "latitude":           None, "longitude":       None,
        "raw_cpr_lat":        None, "raw_cpr_lon":     None,
        "cpr_format":         None, "position_source": None,
        "cpr_even_hex":       None, "cpr_odd_hex":     None,
        "cpr_gap_samples":    None, "cpr_gap_rf_s":    None,

        # Identification
        "callsign":           None,

        # Velocity
        "groundspeed_kt":     None, "groundspeed_kmh": None,
        "track_angle_deg":    None, "airspeed_kt":     None,
        "airspeed_kmh":       None, "heading_deg":     None,
        "vertical_rate_fpm":  None, "vertical_rate_ms":None,
        "vertical_status":    None,
    }

    # ── Decode with pyModeS ───────────────────────────────────────────────────
    try:
        hex_msg  = bin2hex(bin_str)
        decoded  = pms.decode(hex_msg)
        is_valid = decoded.get("crc_valid", False)
        tc       = decoded.get("typecode")

        record["hex_message"] = hex_msg
        record["crc_valid"]   = bool(is_valid)
        record["icao"]        = decoded.get("icao")
        record["typecode"]    = tc
        record["df"]          = decoded.get("df")

        if is_valid and tc is not None:

            # ── IDENTIFICATION (TC 1-4) ──────────────────────────────────────
            # Sun (2021) Chapter 4: callsign encoded as 6-bit ASCII characters
            if 1 <= tc <= 4:
                record["message_type"] = "IDENTIFICATION"
                record["callsign"]     = decoded.get("callsign")

            # ── SURFACE POSITION (TC 5-8) ────────────────────────────────────
            # Sun (2021) Chapter 6: CPR-encoded surface position + ground speed
            elif 5 <= tc <= 8:
                record["message_type"] = "SURFACE_POSITION"
                gs = decoded.get("groundspeed")
                if gs is not None:
                    record["groundspeed_kt"]  = round(gs, 2)
                    record["groundspeed_kmh"] = round(gs * 1.852, 2)
                # Raw CPR values — real position decoded by CPR buffer
                if len(bin_str) >= 88:
                    record["raw_cpr_lat"] = int(bin_str[54:71], 2)
                    record["raw_cpr_lon"] = int(bin_str[71:88], 2)
                # FIX 2: always derive CPR format from bit 53 of the binary
                # string (message bit 54, 0-indexed as 53).
                # 0 = Even frame, 1 = Odd frame  (Sun 2021, Table 5.1)
                record["cpr_format"] = "Odd" if bin_str[53] == "1" else "Even"

            # ── AIRBORNE POSITION (TC 9-18) ───────────────────────────────────
            # Sun (2021) Chapter 5: barometric altitude + CPR-encoded position
            elif 9 <= tc <= 18:
                record["message_type"] = "AIRBORNE_POSITION"
                alt_ft = decoded.get("altitude")
                if alt_ft is not None:
                    record["altitude_ft"] = alt_ft
                    record["altitude_m"]  = round(alt_ft * 0.3048, 1)
                if len(bin_str) >= 88:
                    record["raw_cpr_lat"] = int(bin_str[54:71], 2)
                    record["raw_cpr_lon"] = int(bin_str[71:88], 2)
                # FIX 2 applied here too — bit 53 is always authoritative
                record["cpr_format"] = "Odd" if bin_str[53] == "1" else "Even"

            # ── AIRBORNE VELOCITY (TC 19) ─────────────────────────────────────
            # Sun (2021) Chapter 7: ground speed OR airspeed + vertical rate
            elif tc == 19:
                record["message_type"] = "AIRBORNE_VELOCITY"
                gs = decoded.get("groundspeed")
                if gs is not None:
                    record["groundspeed_kt"]  = round(gs, 2)
                    record["groundspeed_kmh"] = round(gs * 1.852, 2)
                    record["track_angle_deg"] = decoded.get("track")
                airspeed = decoded.get("airspeed")
                if airspeed is not None:
                    record["airspeed_kt"]  = round(airspeed, 2)
                    record["airspeed_kmh"] = round(airspeed * 1.852, 2)
                    record["heading_deg"]  = decoded.get("heading")
                vrate = decoded.get("vertical_rate")
                if vrate is not None:
                    record["vertical_rate_fpm"] = vrate
                    # Convert ft/min → m/s:  1 ft = 0.3048 m, 1 min = 60 s
                    record["vertical_rate_ms"]  = round((vrate * 0.3048) / 60, 2)
                    record["vertical_status"]   = "Climbing" if vrate > 0 else "Descending"

            # ── OPERATIONAL STATUS (TC 31) ────────────────────────────────────
            elif tc == 31:
                record["message_type"] = "OPERATIONAL_STATUS"
                record["callsign"]     = str(decoded.get("capability", "N/A"))

            else:
                record["message_type"] = f"RESERVED_TC{tc}"

        else:
            record["message_type"] = "INVALID_CRC" if not is_valid else "UNKNOWN_TC"

    except Exception as e:
        record["message_type"] = f"DECODE_ERROR:{e}"

    # ── Aircraft database lookup ──────────────────────────────────────────────
    _fill_db_fields(record)

    return record


def _fill_db_fields(record):
    """
    Look up the ICAO address in the aircraft database and fill all 26 DB
    fields into the record dict in-place.
    Called for every message type, regardless of CRC validity.
    """
    icao_hex = record.get("icao")
    if not icao_hex:
        return

    try:
        label, info = lookup(icao_hex)
        if info:
            record["registration"]       = info.get("registration")
            record["manufacturericao"]   = info.get("manufacturericao")
            record["manufacturername"]   = info.get("manufacturername")
            record["model"]              = info.get("model")
            record["typecode_db"]        = info.get("typecode")
            record["serialnumber"]       = info.get("serialnumber")
            record["linenumber"]         = info.get("linenumber")
            record["icaoaircrafttype"]   = info.get("icaoaircrafttype")
            record["operator"]           = info.get("operator")
            record["operatorcallsign"]   = info.get("operatorcallsign")
            record["operatoricao"]       = info.get("operatoricao")
            record["operatoriata"]       = info.get("operatoriata")
            record["owner"]              = info.get("owner")
            record["testreg"]            = info.get("testreg")
            record["registered"]         = info.get("registered")
            record["reguntil"]           = info.get("reguntil")
            record["status"]             = info.get("status")
            record["built"]              = info.get("built")
            record["firstflightdate"]    = info.get("firstflightdate")
            record["seatconfiguration"]  = info.get("seatconfiguration")
            record["engines"]            = info.get("engines")
            record["modes"]              = info.get("modes")
            record["adsb_equipped"]      = info.get("adsb")
            record["acars"]              = info.get("acars")
            record["notes"]              = info.get("notes")
            record["categoryDescription"]= info.get("categoryDescription")
            print(f"  [DB] ✓ {icao_hex.upper()} → {label}")
        else:
            print(f"  [DB] ✗ {icao_hex.upper()} not in database")
    except Exception as e:
        print(f"  [DB] Lookup error for {icao_hex}: {e}")


def write_json(record):
    """
    Atomically write one JSON file to output/<shift_index>.json.

    Uses a temp file + os.replace() so adsb_to_firebase.py never reads
    a partially-written file — the rename is atomic on both Linux and Windows.

    The 'bin_str' field is removed before writing — it is an internal field
    used for CPR bit extraction and should not appear in the output.
    """
    # Remove the internal binary string — not needed in the JSON output
    record_clean = {k: v for k, v in record.items() if k != "bin_str"}

    shift_index = record_clean.get("shift_index", "unknown")
    out_path    = os.path.join(OUTPUT_DIR, f"{shift_index}.json")
    tmp_path    = out_path + ".tmp"

    with open(tmp_path, "w") as f:
        json.dump(record_clean, f, indent=2)
    os.replace(tmp_path, out_path)

    print(f"  [JSON] → {out_path}  "
          f"ICAO:{record_clean.get('icao')}  "
          f"type:{record_clean.get('message_type')}  "
          f"lat:{record_clean.get('latitude')}  "
          f"lon:{record_clean.get('longitude')}")


def export_message(local_idx, global_sample, c1_ratio, c3_ratio, c4_count,
                   signal, capture_file):
    """
    Top-level export function — called by process_chunk() after all 4 criteria pass.

    ROUTING LOGIC:
    ──────────────
    • Position messages (TC 9-18, TC 5-8):
        → Send to CPR buffer (attempt_position_decode).
        → Do NOT write JSON yet.
        → JSON is written only when the buffer has a valid EVEN+ODD pair
          and pyModeS successfully decodes the real lat/lon.

    • All other message types (identification, velocity, operational status):
        → Write JSON immediately.

    • Invalid CRC or decode error:
        → Still write JSON immediately (useful for signal quality analysis).

    Parameters
    ----------
    local_idx     : int   — index of preamble in the local signal list
    global_sample : int   — absolute sample index in the full .bin file
    c1_ratio      : float — CFAR ratio
    c3_ratio      : float — power ratio
    c4_count      : int   — null pair count
    signal        : list  — magnitude samples
    capture_file  : str   — path to the source .bin file
    """

    # Build the complete record (decode + DB lookup)
    record = build_record(
        local_idx, global_sample, c1_ratio, c3_ratio, c4_count,
        signal, capture_file
    )

    if record is None:
        return    # message body extended beyond signal buffer — skip

    # Print a one-line summary to the terminal
    crc_sym  = "✓" if record["crc_valid"]  else "✗"
    print(f"\n[DET] idx={global_sample:,}  "
          f"ICAO={record['icao']}  "
          f"TC={record['typecode']}  "
          f"CRC={crc_sym}  "
          f"SNR={record['snr_db']} dB  "
          f"type={record['message_type']}  "
          f"HEX={record['hex_message']}")

    # Route based on message type
    tc            = record.get("typecode")
    is_position   = (
        record.get("crc_valid") and
        tc is not None and
        (9 <= tc <= 18 or 5 <= tc <= 8)
    )

    if is_position:
        icao       = record.get("icao")
        cpr_format = record.get("cpr_format")
        hex_msg    = record.get("hex_message")

        if icao and cpr_format and hex_msg:
            print(f"  [CPR] {cpr_format.upper()} from ICAO {icao.upper()}  "
                  f"Buffer: {get_buffer_status()}")

            # attempt_position_decode returns:
            #   None → still waiting for the opposite CPR format
            #   dict → both formats received, real lat/lon decoded → write JSON
            completed = attempt_position_decode(icao, cpr_format, hex_msg, record)

            if completed is None:
                opposite = "ODD" if cpr_format == "Even" else "EVEN"
                print(f"  [CPR] ⏳ Waiting for {opposite} from ICAO {icao.upper()}")
                return   # JSON not written yet — waiting for pair
            else:
                record = completed
                print(f"  [CPR] ✅ Position decoded for ICAO {icao.upper()}: "
                      f"lat={record.get('latitude')}  lon={record.get('longitude')}")
        else:
            print(f"  [CPR] Missing ICAO/format/hex — skipping CPR buffer")
            return

    # Write the JSON file (position messages only reach here after CPR decode)
    write_json(record)

# =============================================================================
#  SECTION 4 — MAIN LOOP: File Selection, Chunked Processing, Visualization
# =============================================================================

def run_main_loop():
    """
    Interactive main loop.

    Flow per iteration:
      1. User selects a file and optionally converts 16-bit → 8-bit format.
      2. User picks a window: number of samples to visualize + which slice.
      3. The file is read in 100k-sample chunks from the selected slice.
      4. Each chunk is processed by the 4-criterion detector.
      5. After all chunks: display signal plot + correlation plot.
      6. User can shift the preamble overlay with a button or text box.
      7. Loop repeats until the user enters 0 to exit.
    """

    while True:
        print("\n" + "=" * 60)
        print("  ADS-B Decoder & Visualizer")
        print("=" * 60)
        print("  1 — Convert 16-bit .bin file and process")
        print("  2 — Process existing 8-bit .bin file")
        print("  0 — Exit")

        choice = input("\nSelect: ").strip()

        if choice == "0":
            print("Exiting.")
            break

        # ── File Selection ────────────────────────────────────────────────────
        elif choice == "1":
            fname = input("Enter filename (will look in C:/Users/ucef-/Desktop/Captures/): ").strip()
            in_path  = os.path.join("C:/Users/ucef-/Desktop/Captures", fname)
            out_path = "C:/Users/ucef-/Desktop/Captures/ForRtl/output_8bit.bin"
            print(f"Converting {in_path} → {out_path} …")
            data = np.fromfile(in_path, dtype=np.int16)
            (((data.astype(np.float32) + 32768) / 256))  \
                .astype(np.uint8).tofile(out_path)
            capture_file = out_path

        elif choice == "2":
            capture_file = input("Enter full path to the .bin file: ").strip()
            if not capture_file:
                # Default file for quick testing
                capture_file = "C:/Users/ucef-/Desktop/raw_iq_signalsflights5.bin"

        else:
            print("Invalid selection — try again.")
            continue

        if not os.path.exists(capture_file):
            print(f"ERROR: File not found: {capture_file}")
            continue

        file_size = os.path.getsize(capture_file)
        print(f"\nFile : {capture_file}")
        print(f"Size : {file_size / 1e6:.1f} MB  "
              f"({file_size // 2:,} IQ samples)")

        # ── Window Selection ──────────────────────────────────────────────────
        try:
            n_plot_samples = int(input(
                "\nSamples to VISUALIZE (e.g. 200, 1000, 2000): "
            )) * 2   # ×2 because each IQ pair = 2 bytes
        except ValueError:
            print("Invalid number — using 2000.")
            n_plot_samples = 2000 * 2

        time_window_us = (n_plot_samples / 2) * 0.5   # each sample = 0.5 µs
        try:
            slice_n = int(input(
                f"Which slice? (1 = first {time_window_us:.0f} µs, "
                f"2 = second, etc.): "
            ))
        except ValueError:
            slice_n = 1

        if slice_n == 0:
            print("Exiting.")
            break

        # ── x-axis tick scaler for the visualization plot ────────────────────
        if   n_plot_samples <= 50:   scaler = 1
        elif n_plot_samples <= 200:  scaler = 2
        elif n_plot_samples <= 1000: scaler = 50
        else:                         scaler = 100

        # ── Byte position of the visualization slice ─────────────────────────
        # n_plot_samples is in bytes (2 bytes per IQ pair, ×2 already applied)
        vis_start_byte = n_plot_samples * (slice_n - 1)

        # ── Chunk size: use full slice if small, else 100k samples ───────────
        chunk_samples = n_plot_samples // 2 if n_plot_samples < 50_000 \
                        else CHUNK_SAMPLES

        print(f"\nProcessing slice {slice_n} "
              f"(byte {vis_start_byte:,} → {vis_start_byte + n_plot_samples:,}) …")

        # ── Storage for the visualization data ───────────────────────────────
        # FIX 1: vis_Magnitude stores the FIRST chunk of the selected slice.
        # This is what the signal plot will draw — NOT the last chunk_mag.
        vis_magnitude        = []
        vis_correlation      = None

        # Running totals for the criterion counters
        total_c1 = total_c2 = total_c3 = total_c4 = 0

        # Overlap buffer: last OVERLAP samples of the previous chunk
        # are prepended to the next chunk so preambles at chunk boundaries
        # are never missed.
        overlap_buffer = []

        # ── Chunked file reading and processing ───────────────────────────────
        read_limit  = vis_start_byte + n_plot_samples
        byte_offset = vis_start_byte

        with open(capture_file, "rb") as fh:
            fh.seek(vis_start_byte)

            while byte_offset < read_limit and byte_offset < file_size:
                raw = fh.read(chunk_samples * 2)    # 2 bytes per IQ pair
                if not raw:
                    break

                chunk_mag = raw_bytes_to_magnitude(raw)
                signal    = overlap_buffer + chunk_mag

                # ── Capture visualization data from the FIRST chunk ───────────
                # FIX 1: save ONLY the first chunk's data for plotting,
                # not chunk_mag which gets overwritten every iteration.
                if not vis_magnitude and byte_offset == vis_start_byte:
                    vis_magnitude   = signal[:n_plot_samples // 2]
                    vis_correlation = np.correlate(
                        vis_magnitude, PREAMBLE_TEMPLATE, mode="valid"
                    )

                # ── Run the 4-criterion detector ──────────────────────────────
                # export_message is passed as a lambda so process_chunk doesn't
                # need to know about capture_file — keeps the function pure.
                total_c1, total_c2, total_c3, total_c4, _ = process_chunk(
                    signal, byte_offset, len(overlap_buffer),
                    total_c1, total_c2, total_c3, total_c4,
                    export_fn=lambda li, gs, c1, c3, c4, sig: export_message(
                        li, gs, c1, c3, c4, sig, capture_file
                    )
                )

                # Carry overlap to next iteration (prevents missing preambles
                # that straddle a chunk boundary)
                overlap_buffer = chunk_mag[-OVERLAP:] if chunk_samples == CHUNK_SAMPLES else []

                byte_offset += len(raw)

                print(f"  [{byte_offset/1e6:.1f} MB]  "
                      f"C1={total_c1}  C2={total_c2}  C3={total_c3}  "
                      f"confirmed(C4)={total_c4}",
                      end="\r")

        print(f"\n\n{'─'*60}")
        print(f"Processing complete:")
        print(f"  Criterion 1 candidates  : {total_c1}")
        print(f"  Criterion 2 passed      : {total_c2}")
        print(f"  Criterion 3 passed      : {total_c3}")
        print(f"  Criterion 4 (confirmed) : {total_c4}")
        print(f"  JSON files written to   : {OUTPUT_DIR}/")
        print(f"{'─'*60}")

        # ── Visualization ─────────────────────────────────────────────────────
        n_vis = n_plot_samples // 2   # number of IQ pairs = number of magnitude values

        if n_vis > 2000:
            print(f"\nVisualization skipped: {n_vis} samples > 2000 limit.")
            print("Reduce the plot window to 2000 or fewer samples to see the graph.")
            continue

        if not vis_magnitude:
            print("\nNo visualization data captured — check file path and slice number.")
            continue

        _show_plots(vis_magnitude, vis_correlation, n_vis, scaler, vis_start_byte)


def _show_plots(magnitude, correlation, n_samples, scaler, start_byte):
    """
    Display two Matplotlib windows:
      Window 1 — Signal magnitude vs sample index, with a draggable preamble overlay.
      Window 2 — CFAR correlation values vs sample index.

    The preamble overlay (red stems) can be shifted left/right using:
      • The [Shift →] button (moves 1 sample right per click)
      • The text box (jump to any sample index)

    Parameters
    ----------
    magnitude   : list of float — the magnitude values to plot
    correlation : np.ndarray    — CFAR correlation output
    n_samples   : int           — number of samples (x-axis length)
    scaler      : int           — spacing between x-axis tick marks
    start_byte  : int           — file byte of the slice start (for x-axis label)
    """

    plt.style.use("_mpl-gallery")

    # ── Preamble overlay template (red stems) ─────────────────────────────────
    xx_base = np.arange(0, 26, dtype=float)
    yy_base = np.zeros(26)
    for p in [0, 2, 7, 9, 16, 19, 21, 23, 24]:
        yy_base[p] = 3.0    # height = 3.0 for visibility

    # ── Figure 1: Signal + Preamble overlay ───────────────────────────────────
    fig_sig, ax_sig = plt.subplots(figsize=(12, 4))
    fig_sig.subplots_adjust(bottom=0.15)

    x_sig = np.arange(n_samples)
    # FIX 1: plot vis_magnitude (the user-selected slice), NOT chunk_mag
    ax_sig.plot(x_sig, magnitude[:n_samples], color="steelblue",
                linewidth=0.8, label="Signal magnitude")

    preamble_stems = ax_sig.stem(
        xx_base, yy_base,
        linefmt="red", markerfmt="ro", basefmt=" ",
        label="Preamble template"
    )

    ax_sig.set_xlabel(
        f"IQ Sample index  (1 sample = 0.5 µs)   "
        f"[file byte start: {start_byte:,}]"
    )
    ax_sig.set_ylabel("Magnitude")
    ax_sig.set_title("ADS-B Signal — 1090 MHz")
    ax_sig.set_xlim(0, n_samples)
    ax_sig.set_ylim(0, 12)
    ax_sig.set_xticks(scaler * np.arange(1, n_samples // scaler + 1))
    ax_sig.set_yticks(np.arange(0, 13))
    ax_sig.legend(loc="upper right", fontsize=8)
    ax_sig.grid(True, alpha=0.3)

    # ── Interactive preamble shifter ──────────────────────────────────────────
    class PreambleShifter:
        """
        Allows the user to slide the red preamble overlay horizontally
        to visually align it with detected preambles in the signal.
        """
        def __init__(self):
            self.offset = 0

        def _redraw(self):
            new_xx = xx_base + self.offset
            preamble_stems.markerline.set_xdata(new_xx)
            # Rebuild the vertical stem line segments at the new positions
            preamble_stems.stemlines.set_segments([
                [[x, 0], [x, y]] for x, y in zip(new_xx, yy_base)
            ])
            fig_sig.canvas.draw_idle()

        def on_button(self, _event):
            self.offset += 1
            self._redraw()

        def on_textbox(self, text):
            try:
                self.offset = int(text)
                self._redraw()
            except ValueError:
                pass

    shifter = PreambleShifter()

    # Button: [Shift →]
    ax_btn = fig_sig.add_axes([0.04, 0.02, 0.10, 0.05])
    btn    = Button(ax_btn, "Shift →", color="lightgray", hovercolor="white")
    btn.on_clicked(shifter.on_button)

    # Text box: "Jump to:"
    ax_tb = fig_sig.add_axes([0.87, 0.02, 0.10, 0.05])
    tb    = TextBox(ax_tb, "Jump to: ", initial="0")
    tb.on_submit(shifter.on_textbox)

    # ── Figure 2: CFAR Correlation ────────────────────────────────────────────
    fig_cor, ax_cor = plt.subplots(figsize=(12, 3))
    fig_cor.subplots_adjust(bottom=0.15)

    n_corr  = len(correlation)
    x_corr  = np.arange(n_corr)
    ax_cor.plot(x_corr, correlation, color="crimson", linewidth=0.8)
    ax_cor.axhline(
        y=C1_THRESHOLD * correlation.mean() if correlation.mean() > 0 else 50,
        color="orange", linestyle="--", linewidth=1, label=f"C1 threshold ×{C1_THRESHOLD}"
    )
    ax_cor.set_xlabel("Sample index")
    ax_cor.set_ylabel("Correlation value")
    ax_cor.set_title("CFAR Correlation — Preamble detector output")
    ax_cor.set_xlim(0, n_corr)
    ax_cor.set_ylim(0, max(500, float(correlation.max()) * 1.1))
    ax_cor.set_xticks(scaler * np.arange(1, n_corr // scaler + 1))
    ax_cor.legend(fontsize=8)
    ax_cor.grid(True, alpha=0.3)

    plt.show()


# =============================================================================
#  ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    run_main_loop()