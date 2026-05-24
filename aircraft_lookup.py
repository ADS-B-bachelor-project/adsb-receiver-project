# import csv
# import os
# import time

# # ================================================================
# #  AIRCRAFT DATABASE LOOKUP
# #  Task 3 — Systems Lead (Validator & Visualizer)
# #
# #  What this file does:
# #  1. Loads the aircraft-database.csv ONCE into a dictionary
# #  2. Provides a fast lookup function — instant results
# #  3. Handles missing aircraft gracefully
# #  4. Converts "70602d" → "7T-VHL (Air Algérie) — Boeing 737-800"
# # ================================================================


# # Global dictionary — loaded once, reused forever
# # Stored at module level so it persists between lookups
# _DATABASE = {}
# _DB_LOADED = False

# # Default path to the aircraft database CSV.
# # Change this value to point to another database file if needed.
# DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "aircraft-database.csv")


# def load_database(csv_path):
#     """
#     Loads the aircraft-database.csv into a Python dictionary.

#     WHY A DICTIONARY and not searching the CSV every time?
#     --------------------------------------------------------
#     CSV search (slow):
#         For each lookup → read 500,000 rows one by one
#         500 lookups × 500,000 rows = 250,000,000 operations

#     Dictionary lookup (fast):
#         Load CSV once → build index → each lookup = 1 operation
#         500 lookups × 1 = 500 operations

#     Speed difference: milliseconds vs several minutes.

#     Args:
#         csv_path (str): full path to aircraft-database.csv

#     Returns:
#         dict: { "icao24_hex": { registration, operator, model } }
#     """

#     global _DATABASE, _DB_LOADED

#     # Don't reload if already loaded — saves time on repeated calls
#     if _DB_LOADED:
#         print(f"[DB] Already loaded ({len(_DATABASE):,} aircraft) — skipping reload")
#         return _DATABASE

#     # Check file exists
#     if not os.path.exists(csv_path):
#         raise FileNotFoundError(
#             f"[DB] Database not found: {csv_path}\n"
#             f"[DB] Make sure aircraft-database.csv is at that path."
#         )

#     print(f"[DB] Loading database: {csv_path}")
#     print(f"[DB] File size: {os.path.getsize(csv_path) / 1e6:.1f} MB")

#     start_time = time.time()
#     count = 0
#     skipped = 0

#     # Open with utf-8-sig to handle BOM character at start of some CSV files
#     with open(csv_path, encoding="utf-8-sig", errors="replace") as f:
#         reader = csv.DictReader(f)

#         for row in reader:
#             # The ICAO hex code is in column "icao24"
#             # Always store in LOWERCASE for consistent matching
#             # Aircraft transmit in any case — we normalise to lower
#             icao = row.get("icao24", "").strip().lower()

#             # Skip rows with no ICAO code — they are useless for lookup
#             if not icao:
#                 skipped += 1
#                 continue

#             # Store only the 4 fields Task 3 needs
#             # This keeps memory usage low — we ignore the other 23 columns
#             _DATABASE[icao] = {
#     "registration"      : row.get("registration", "").strip(),
#     "manufacturername"  : row.get("manufacturername", "").strip(),
#     "model"             : row.get("model", "").strip(),
#     "serialnumber"      : row.get("serialnumber", "").strip(),
#     "linenumber"        : row.get("linenumber", "").strip(),
#     "icao24"            : row.get("icao24", "").strip(),
#     "operator"          : row.get("operator", "").strip(),
#     "operatorcallsign"  : row.get("operatorcallsign", "").strip(),
#     "operatoricao"      : row.get("operatoricao", "").strip(),
#     "owner"             : row.get("owner", "").strip(),
#     "testreg"           : row.get("testreg", "").strip(),
#     "registered"        : row.get("registered", "").strip(),
#     "status"            : row.get("status", "").strip(),
#     "built"             : row.get("built", "").strip(),
#     "typecode"          : row.get("typecode", "").strip(),
# }
#             count += 1

#     elapsed = time.time() - start_time
#     _DB_LOADED = True

#     print(f"[DB] Loaded {count:,} aircraft in {elapsed:.2f}s")
#     print(f"[DB] Skipped {skipped:,} rows with no ICAO code")
#     print(f"[DB] Ready for instant lookups")

#     return _DATABASE


# def lookup(icao_hex, csv_path=None):
#     """
#     Look up an aircraft by its ICAO hex code.

#     This is the main function your team calls.
#     Returns a formatted string AND a dict with all details.

#     Args:
#         icao_hex (str): 6-character ICAO hex code e.g. "70602D" or "70602d"
#         csv_path (str): path to CSV — only needed on first call

#     Returns:
#         tuple: (display_string, details_dict)

#     Example:
#         label, info = lookup("70602D")
#         print(label)
#         → "7T-VHL (Air Algérie) — Boeing 737-800"
#     """

#     global _DATABASE, _DB_LOADED

#     # Auto-load database on first call if not already loaded
#     if not _DB_LOADED:
#         if csv_path is None:
#             # Try to find the database automatically in common locations
#             candidates = [
#                 DEFAULT_DB_PATH,
#                 os.path.join(os.path.dirname(__file__), "aircraftDatabase.csv"),
#                 # os.path.join(os.path.dirname(__file__),
#                 #              "aircraft-database.csv"),
#             ]
#             for candidate in candidates:
#                 if os.path.exists(candidate):
#                     csv_path = candidate
#                     break

#             if csv_path is None:
#                 print("[DB] WARNING: Database not loaded and path not given")
#                 print("[DB] Call load_database('path/to/aircraft-database.csv') first")
#                 return _format_unknown(icao_hex), {}

#         load_database(csv_path)

#     # Normalise to lowercase — ICAO codes are case-insensitive
#     # "70602D" and "70602d" and "70602D" must all find the same aircraft
#     key = icao_hex.strip().lower()

#     # Dictionary lookup — this is O(1) — instant regardless of database size
#     if key in _DATABASE:
#         info = _DATABASE[key]
#         display = _format_found(icao_hex.upper(), info)
#         return display, info
#     else:
#         display = _format_unknown(icao_hex.upper())
#         return display, {}


# def _format_found(icao, info):
#     """
#     Builds the human-readable label for a found aircraft.

#     Examples:
#         "7T-VHL (Air Algérie) — Boeing 737-800"
#         "EI-DAA (Aer Lingus) — Airbus A320"
#         "G-EUOE (British Airways)"        ← if no model in database
#     """

#     registration = info.get("registration") or icao   # fallback to ICAO if no reg
#     operator     = info.get("operator", "")
#     model        = info.get("model", "")

#     # Build label piece by piece
#     label = registration

#     if operator:
#         label += f" ({operator})"

#     if model:
#         label += f" — {model}"

#     return label


# def _format_unknown(icao):
#     """Returns a clear label for aircraft not in the database."""
#     return f"Unknown Aircraft [{icao}]"


# def lookup_many(icao_list, csv_path=None):
#     """
#     Look up multiple aircraft at once.
#     Useful for processing a full capture file.

#     Args:
#         icao_list (list): list of ICAO hex strings
#         csv_path  (str):  path to CSV — only needed on first call

#     Returns:
#         dict: { "icao_hex": (display_string, details_dict) }

#     Example:
#         results = lookup_many(["70602d", "4ca7b2", "400f3b"])
#         for icao, (label, info) in results.items():
#             print(f"{icao} → {label}")
#     """

#     # Ensure database is loaded before processing the list
#     if not _DB_LOADED and csv_path:
#         load_database(csv_path)

#     results = {}
#     found = 0
#     missing = 0

#     for icao in icao_list:
#         label, info = lookup(icao)
#         results[icao] = (label, info)
#         if info:
#             found += 1
#         else:
#             missing += 1

#     print(f"\n[DB] Batch lookup: {found} found, {missing} not in database")
#     return results


# # ================================================================
# #  QUICK TEST — run this file directly to test your database
# #  python src/aircraft_lookup.py
# # ================================================================

# if __name__ == "__main__":

#     import sys

#     # Path to your database — adjust if needed
#     DB_PATH = DEFAULT_DB_PATH

#     print("=" * 60)
#     print(" AIRCRAFT DATABASE LOOKUP — Task 3")
#     print("=" * 60)

#     # Load the database once
#     load_database(DB_PATH)

#     print()
#     print("-" * 60)
#     print(" SINGLE LOOKUPS")
#     print("-" * 60)

#     # Test with known ICAO codes — replace with real ones from your captures
#     test_codes = [
#         "4d2023",   # 9H-AEM — Airbus (from dump1090 test file)
#         "4840d6",   # common European aircraft
#         "70602d",   # Air Algérie (relevant to your location)
#         "02A1AA",   # Should return Unknown
#         "FFFFFF",   # Should return Unknown
#     ]

#     for code in test_codes:
#         label, info = lookup(code, DB_PATH)
#         print(f"\n  ICAO : {code.upper()}")
#         print(f"  Result : {label}")
#         if info:
#             print(f"  Registration : {info.get('registration', 'N/A')}")
#             print(f"  Operator     : {info.get('operator', 'N/A')}")
#             print(f"  Model        : {info.get('model', 'N/A')}")
#             print(f"  Type code    : {info.get('typecode', 'N/A')}")

#     print()
#     print("-" * 60)
#     print(" BATCH LOOKUP")
#     print("-" * 60)

#     batch_results = lookup_many(test_codes, DB_PATH)
#     print()
#     for icao, (label, info) in batch_results.items():
#         status = "✓" if info else "✗"
#         print(f"  [{status}] {icao.upper()} → {label}")

#     print()
#     print("=" * 60)
#     print(" SPEED TEST")
#     print("=" * 60)

#     # Test lookup speed — do 10,000 lookups and measure time
#     import random
#     all_keys = list(_DATABASE.keys())

#     if all_keys:
#         test_sample = random.choices(all_keys, k=10_000)
#         start = time.time()
#         for k in test_sample:
#             lookup(k)
#         elapsed = time.time() - start
#         print(f"  10,000 lookups completed in {elapsed*1000:.1f} ms")
#         print(f"  Average per lookup: {elapsed/10_000*1_000_000:.2f} microseconds")
#     else:
#         print("  No data loaded — check your CSV path")


# aircraft_lookup.py
# ================================================================
#  AIRCRAFT DATABASE LOOKUP  — updated for full CSV schema
#
#  CSV columns used (from aircraft-database.csv):
#  icao24, registration, manufacturericao, manufacturername,
#  model, typecode, serialnumber, linenumber, icaoaircrafttype,
#  operator, operatorcallsign, operatoricao, operatoriata,
#  owner, testreg, registered, reguntil, status, built,
#  firstflightdate, seatconfiguration, engines,
#  modes, adsb, acars, notes, categoryDescription
# ================================================================

import csv
import os
import time

_DATABASE  = {}
_DB_LOADED = False


def load_database(csv_path):
    """
    Load aircraft-database.csv into memory once.
    All 27 columns are stored so any field can be returned on lookup.
    """
    global _DATABASE, _DB_LOADED

    if _DB_LOADED:
        print(f"[DB] Already loaded ({len(_DATABASE):,} aircraft) — skipping reload")
        return _DATABASE

    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"[DB] Database not found: {csv_path}\n"
            f"      Download from: https://opensky-network.org/datasets/metadata/"
        )

    print(f"[DB] Loading: {csv_path}  ({os.path.getsize(csv_path)/1e6:.1f} MB)")
    start = time.time()
    count = 0
    skipped = 0

    with open(csv_path, encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)

        for row in reader:
            icao = row.get("icao24", "").strip().lower()
            if not icao:
                skipped += 1
                continue

            # Store ALL useful columns — keep empty strings as None for clean JSON
            def _val(key):
                v = row.get(key, "").strip()
                return v if v else None

            _DATABASE[icao] = {
                # ── Identity ──────────────────────────────────────────────
                "registration":      _val("registration"),
                "manufacturericao":  _val("manufacturericao"),
                "manufacturername":  _val("manufacturername"),
                "model":             _val("model"),
                "typecode":          _val("typecode"),
                "serialnumber":      _val("serialnumber"),
                "linenumber":        _val("linenumber"),
                "icaoaircrafttype":  _val("icaoaircrafttype"),
                # ── Operator / Owner ──────────────────────────────────────
                "operator":          _val("operator"),
                "operatorcallsign":  _val("operatorcallsign"),
                "operatoricao":      _val("operatoricao"),
                "operatoriata":      _val("operatoriata"),
                "owner":             _val("owner"),
                # ── Registration history ──────────────────────────────────
                "testreg":           _val("testreg"),
                "registered":        _val("registered"),
                "reguntil":          _val("reguntil"),
                "status":            _val("status"),
                "built":             _val("built"),
                "firstflightdate":   _val("firstflightdate"),
                # ── Technical specs ───────────────────────────────────────
                "seatconfiguration": _val("seatconfiguration"),
                "engines":           _val("engines"),
                # ── Capabilities ──────────────────────────────────────────
                "modes":             _val("modes"),
                "adsb":              _val("adsb"),
                "acars":             _val("acars"),
                # ── Extra ─────────────────────────────────────────────────
                "notes":             _val("notes"),
                "categoryDescription": _val("categoryDescription"),
            }
            count += 1

    _DB_LOADED = True
    elapsed = time.time() - start
    print(f"[DB] Loaded {count:,} aircraft in {elapsed:.2f}s  |  skipped {skipped:,} empty rows")
    return _DATABASE


def lookup(icao_hex, csv_path=None):
    """
    Look up one aircraft by its 6-character ICAO hex code.

    Returns
    -------
    (label_str, info_dict)
        label_str : human-readable string, e.g. "7T-VHL (Air Algérie) — Boeing 737-800"
        info_dict : full dict of all stored fields, or {} if not found
    """
    global _DB_LOADED

    if not _DB_LOADED:
        if csv_path is None:
            # Try common locations automatically
            candidates = [
                "aircraft-database.csv",
                "data/aircraft-database.csv",
                os.path.join(os.path.dirname(__file__), "aircraft-database.csv"),
            ]
            for c in candidates:
                if os.path.exists(c):
                    csv_path = c
                    break
            if csv_path is None:
                print("[DB] WARNING: database not found. Call load_database() first.")
                return f"Unknown [{icao_hex.upper()}]", {}

        load_database(csv_path)

    key = icao_hex.strip().lower()

    if key in _DATABASE:
        info  = _DATABASE[key]
        label = _build_label(icao_hex.upper(), info)
        return label, info
    else:
        return f"Unknown Aircraft [{icao_hex.upper()}]", {}


def _build_label(icao, info):
    """
    Build the human-readable label.
    Examples:
        "7T-VHL (Air Algérie) — Boeing 737-800"
        "N757F (Vintage Aircraft Llc) — Raytheon A36"
        "EI-DAA — Airbus A320"   (no operator in DB)
    """
    reg      = info.get("registration") or icao
    operator = info.get("operator") or ""
    model    = info.get("model") or ""

    label = reg
    if operator:
        label += f" ({operator})"
    if model:
        label += f" — {model}"
    return label


# ── Quick self-test ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    DB_PATH = r"aircraft-database.csv"
    load_database(DB_PATH)

    test_codes = ["aa3487", "4840d6", "70602d", "000000"]
    for code in test_codes:
        label, info = lookup(code)
        print(f"\n{code.upper()} → {label}")
        if info:
            for k, v in info.items():
                if v:
                    print(f"    {k:25s}: {v}")