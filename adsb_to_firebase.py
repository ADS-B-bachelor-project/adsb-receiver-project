

# """
# adsb_to_firebase.py
# ────────────────────────────────────────────────────────────────────────────
# Standalone watcher process.  Run this in a SEPARATE terminal alongside
# SignalVisualizer.py:

#     Terminal 1:  python3 SignalVisualizer.py
#     Terminal 2:  python3 adsb_to_firebase.py

# How it works:
#   1. Watches the  output/  folder using watchdog (OS-level file events,
#      no polling delay).
#   2. The instant SignalVisualizer writes  output/<shift_index>.json ,
#      this process picks it up, reads it, and pushes it to Firebase at
#          adsb/latest/messages/<icao>
#      so the Flutter app receives the update in real time.
#   3. The processed file is moved to  output/sent/  so it is never
#      pushed twice.
#   4. Also maintains a rolling  output/results_all.json  with every
#      frame seen in the current session.

# Requirements:
#     pip install watchdog firebase-admin

# Firebase setup:
#   1. Firebase Console → Project Settings → Service Accounts
#      → Generate new private key → save as  serviceAccountKey.json
#   2. Set FIREBASE_DB_URL below.
# ────────────────────────────────────────────────────────────────────────────
# """

# import json
# import os
# import shutil
# import time
# import datetime
# import threading

# from watchdog.observers import Observer
# from watchdog.events import FileSystemEventHandler

# # ── CONFIG ─────────────────────────────────────────────────────

# SERVICE_ACCOUNT = "serviceAccountKey.json"

# OUTPUT_DIR = "output"
# SENT_DIR = os.path.join(OUTPUT_DIR, "sent")
# RESULTS_ALL = os.path.join(OUTPUT_DIR, "results_all.json")

# # ───────────────────────────────────────────────────────────────

# os.makedirs(OUTPUT_DIR, exist_ok=True)
# os.makedirs(SENT_DIR, exist_ok=True)

# SESSION_START = datetime.datetime.now(datetime.UTC).isoformat()

# # ═══════════════════════════════════════════════════════════════
# # FIREBASE FIRESTORE INIT
# # ═══════════════════════════════════════════════════════════════

# _firestore_ready = False
# _firestore_db = None


# def _init_firebase():
#     global _firestore_ready, _firestore_db

#     try:
#         import firebase_admin
#         from firebase_admin import credentials, firestore
#     except ImportError:
#         print("[!] firebase-admin not installed")
#         print("Run: pip install firebase-admin")
#         return

#     if not os.path.exists(SERVICE_ACCOUNT):
#         print(f"[!] Missing {SERVICE_ACCOUNT}")
#         return

#     try:
#         if not firebase_admin._apps:
#             cred = credentials.Certificate(SERVICE_ACCOUNT)
#             firebase_admin.initialize_app(cred)

#         _firestore_db = firestore.client()

#         _firestore_ready = True

#         print("[✓] Firestore connected successfully")

#     except Exception as e:
#         print(f"[!] Firebase init failed: {e}")


# # ═══════════════════════════════════════════════════════════════
# # SESSION STORAGE
# # ═══════════════════════════════════════════════════════════════

# _session_messages = {}
# _session_lock = threading.Lock()


# def _write_results_all():
#     data = {
#         "session_start": SESSION_START,
#         "total_frames": len(_session_messages),
#         "messages": list(_session_messages.values()),
#     }

#     tmp = RESULTS_ALL + ".tmp"

#     with open(tmp, "w") as f:
#         json.dump(data, f, indent=2)

#     os.replace(tmp, RESULTS_ALL)


# # ═══════════════════════════════════════════════════════════════
# # FIRESTORE PUSH
# # ═══════════════════════════════════════════════════════════════

# def _push_single(record: dict, icao: str):

#     msg_type = record.get("message_type", "UNKNOWN")

#     payload = {
#         "registration": record.get("registration"),
#         "manufacturername": record.get("manufacturername"),
#         "model": record.get("model"),
#         "serialnumber": record.get("serialnumber"),
#         "linenumber": record.get("linenumber"),
#         "operator": record.get("operator"),
#         "operatorcallsign": record.get("operatorcallsign"),
#         "operatoricao": record.get("operatoricao"),
#         "owner": record.get("owner"),
#         "built": record.get("built"),
#         "status": record.get("status"),
#         "registered": record.get("registered"),
#         "typecode_db": record.get("typecode_db"),
#         "icao": record.get("icao"),
#         "callsign": record.get("callsign"),
#         "type": msg_type,
#         "altitude_ft": record.get("altitude_ft"),
#         "altitude_m": record.get("altitude_m"),
#         "latitude": record.get("latitude"),
#         "longitude": record.get("longitude"),
#         "raw_cpr_lat": record.get("raw_cpr_lat"),
#         "raw_cpr_lon": record.get("raw_cpr_lon"),
#         "cpr_format": record.get("cpr_format"),
#         "groundspeed_kt": record.get("groundspeed_kt"),
#         "groundspeed_kmh": record.get("groundspeed_kmh"),
#         "track_angle_deg": record.get("track_angle_deg"),
#         "vertical_rate_fpm": record.get("vertical_rate_fpm"),
#         "vertical_rate_ms": record.get("vertical_rate_ms"),
#         "vertical_status": record.get("vertical_status"),
#         "snr_db": record.get("snr_db"),
#         "crc_valid": record.get("crc_valid", False),
#         "shift_index": record.get("shift_index"),
#         "captured_at": record.get("captured_at"),
#         "last_update": datetime.datetime.now(datetime.UTC).isoformat(),
#     }

#     try:

#         (
#             _firestore_db
#             .collection("adsb")
#             .document("latest")
#             .collection("messages")
#             .document(icao)
#             .collection("types")
#             .document(msg_type)
#             .set(payload)
#         )

#         print(f"  [✓] Firestore → {icao}/{msg_type}")

#     except Exception as e:
#         print(f"  [!] Firestore push failed: {e}")

# # ═══════════════════════════════════════════════════════════════
# # PROCESS FILE
# # ═══════════════════════════════════════════════════════════════

# def _process_file(filepath: str):

#     for _ in range(10):
#         try:
#             if os.path.getsize(filepath) > 0:
#                 break
#         except FileNotFoundError:
#             return

#         time.sleep(0.02)

#     try:
#         with open(filepath, "r") as f:
#             record = json.load(f)

#     except Exception as e:
#         print(f"[!] Could not read {filepath}: {e}")
#         return

#     icao = record.get("icao") or "UNKNOWN"
#     shift_index = record.get("shift_index", 0)
#     msg_type = record.get("message_type", "UNKNOWN")
#     crc_ok = record.get("crc_valid", False)
#     snr = record.get("snr_db")

#     print(
#         f"\n[→] Frame detected idx:{shift_index:>8} "
#         f"ICAO:{icao} type:{msg_type} "
#         f"CRC:{'✓' if crc_ok else '✗'} "
#         f"SNR:{snr} dB"
#     )

#     if _firestore_ready:
#         _push_single(record, icao)

#     session_key = f"{icao}_{shift_index}"

#     with _session_lock:
#         _session_messages[session_key] = record
#         _write_results_all()

#     dest = os.path.join(SENT_DIR, os.path.basename(filepath))

#     try:
#         shutil.move(filepath, dest)
#         print(f"  [✓] archived → {dest}")

#     except Exception as e:
#         print(f"[!] Could not move file: {e}")


# # ═══════════════════════════════════════════════════════════════
# # WATCHDOG
# # ═══════════════════════════════════════════════════════════════

# class _JSONHandler(FileSystemEventHandler):

#     def _is_target(self, path: str) -> bool:
#         name = os.path.basename(path)

#         return (
#             name.endswith(".json")
#             and name[:-5].lstrip("-").isdigit()
#         )

#     def on_created(self, event):

#         if not event.is_directory and self._is_target(event.src_path):

#             time.sleep(0.02)
#             _process_file(event.src_path)

#     def on_moved(self, event):

#         if not event.is_directory and self._is_target(event.dest_path):

#             time.sleep(0.02)
#             _process_file(event.dest_path)


# # ═══════════════════════════════════════════════════════════════
# # DRAIN OLD FILES
# # ═══════════════════════════════════════════════════════════════

# def _drain_existing():

#     pending = sorted([
#         os.path.join(OUTPUT_DIR, f)
#         for f in os.listdir(OUTPUT_DIR)
#         if f.endswith(".json")
#         and f[:-5].lstrip("-").isdigit()
#     ])

#     if pending:

#         print(f"[i] {len(pending)} unprocessed file(s)")

#         for fp in pending:
#             _process_file(fp)


# # ═══════════════════════════════════════════════════════════════
# # MAIN
# # ═══════════════════════════════════════════════════════════════

# if __name__ == "__main__":

#     print("======================================")
#     print(" ADS-B → Firestore Watcher")
#     print("======================================")

#     _init_firebase()

#     _drain_existing()

#     observer = Observer()

#     observer.schedule(
#         _JSONHandler(),
#         path=OUTPUT_DIR,
#         recursive=False
#     )

#     observer.start()

#     print(f"[✓] Watching {OUTPUT_DIR}/")

#     try:
#         while True:
#             time.sleep(1)

#     except KeyboardInterrupt:
#         observer.stop()

#     observer.join()

#     print(f"\n[i] Session total: {len(_session_messages)}")

"""
adsb_to_firebase.py  — updated version
────────────────────────────────────────────────────────────────────────────
Run in a SEPARATE terminal alongside SignalVisualizer.py:

    Terminal 1:  python SignalVisualizer.py
    Terminal 2:  python adsb_to_firebase.py

What changed vs the old version:
  1. Pushes ALL new aircraft-database fields (registration, manufacturer,
     serialnumber, linenumber, operator, etc.) to Firestore.
  2. Pushes the CPR-decoded lat/lon (only arrives after a valid even+odd
     pair — never a raw CPR value).
  3. All new position fields (cpr_even_hex, cpr_odd_hex, cpr_time_gap_s,
     position_source) are forwarded to Firestore.
────────────────────────────────────────────────────────────────────────────
"""

import json
import os
import shutil
import time
import datetime
import threading

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ── CONFIG ────────────────────────────────────────────────────────────────
SERVICE_ACCOUNT = "serviceAccountKey.json"
OUTPUT_DIR      = "output"
SENT_DIR        = os.path.join(OUTPUT_DIR, "sent")
RESULTS_ALL     = os.path.join(OUTPUT_DIR, "results_all.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(SENT_DIR,   exist_ok=True)

SESSION_START = datetime.datetime.now(datetime.timezone.utc).isoformat()

# ── Firebase init ─────────────────────────────────────────────────────────
_firestore_ready = False
_firestore_db    = None


def _init_firebase():
    global _firestore_ready, _firestore_db
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except ImportError:
        print("[!] firebase-admin not installed — run: pip install firebase-admin")
        return

    if not os.path.exists(SERVICE_ACCOUNT):
        print(f"[!] Missing {SERVICE_ACCOUNT} — Firestore disabled")
        return

    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(SERVICE_ACCOUNT)
            firebase_admin.initialize_app(cred)
        _firestore_db    = firestore.client()
        _firestore_ready = True
        print("[✓] Firestore connected")
    except Exception as e:
        print(f"[!] Firebase init failed: {e}")


# ── Session storage ───────────────────────────────────────────────────────
_session_messages = {}
_session_lock     = threading.Lock()


def _write_results_all():
    data = {
        "session_start": SESSION_START,
        "total_frames":  len(_session_messages),
        "messages":      list(_session_messages.values()),
    }
    tmp = RESULTS_ALL + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, RESULTS_ALL)


# ── Firestore push ────────────────────────────────────────────────────────
def _push_to_firestore(record: dict):
    """
    Push one decoded ADS-B record to Firestore.
    Path:  adsb/latest/messages/<icao>/types/<message_type>

    Every field from the JSON is forwarded — including all new
    aircraft-database fields and the CPR-decoded position.
    """
    icao     = record.get("icao") or "UNKNOWN"
    msg_type = record.get("message_type", "UNKNOWN")

    payload = {
        # ── Signal metadata ───────────────────────────────────────────────
        "shift_index":       record.get("shift_index"),
        "captured_at":       record.get("captured_at"),
        "snr_db":            record.get("snr_db"),
        "crc_valid":         record.get("crc_valid", False),
        "hex_message":       record.get("hex_message"),
        "df":                record.get("df"),
        "typecode":          record.get("typecode"),
        "type":              msg_type,
        "icao":              icao,

        # ── Aircraft identity (from database) ─────────────────────────────
        "registration":      record.get("registration"),
        "manufacturericao":  record.get("manufacturericao"),
        "manufacturername":  record.get("manufacturername"),
        "model":             record.get("model"),
        "typecode_db":       record.get("typecode_db"),
        "serialnumber":      record.get("serialnumber"),
        "linenumber":        record.get("linenumber"),
        "icaoaircrafttype":  record.get("icaoaircrafttype"),

        # ── Operator / Owner ──────────────────────────────────────────────
        "operator":          record.get("operator"),
        "operatorcallsign":  record.get("operatorcallsign"),
        "operatoricao":      record.get("operatoricao"),
        "operatoriata":      record.get("operatoriata"),
        "owner":             record.get("owner"),

        # ── Registration history ──────────────────────────────────────────
        "registered":        record.get("registered"),
        "reguntil":          record.get("reguntil"),
        "status":            record.get("status"),
        "built":             record.get("built"),
        "firstflightdate":   record.get("firstflightdate"),

        # ── Technical specs ───────────────────────────────────────────────
        "seatconfiguration": record.get("seatconfiguration"),
        "engines":           record.get("engines"),
        "adsb_equipped":     record.get("adsb_equipped"),
        "acars":             record.get("acars"),
        "categoryDescription": record.get("categoryDescription"),

        # ── Decoded position (CPR-resolved — never raw CPR values) ────────
        "latitude":          record.get("latitude"),
        "longitude":         record.get("longitude"),
        "altitude_ft":       record.get("altitude_ft"),
        "altitude_m":        record.get("altitude_m"),
        "position_source":   record.get("position_source"),
        "cpr_format":        record.get("cpr_format"),
        "cpr_even_hex":      record.get("cpr_even_hex"),
        "cpr_odd_hex":       record.get("cpr_odd_hex"),
        "cpr_gap_samples":   record.get("cpr_gap_samples"),
        "cpr_gap_rf_s":      record.get("cpr_gap_rf_s"),

        # ── Velocity ─────────────────────────────────────────────────────
        "callsign":          record.get("callsign"),
        "groundspeed_kt":    record.get("groundspeed_kt"),
        "groundspeed_kmh":   record.get("groundspeed_kmh"),
        "track_angle_deg":   record.get("track_angle_deg"),
        "airspeed_kt":       record.get("airspeed_kt"),
        "airspeed_kmh":      record.get("airspeed_kmh"),
        "heading_deg":       record.get("heading_deg"),
        "vertical_rate_fpm": record.get("vertical_rate_fpm"),
        "vertical_rate_ms":  record.get("vertical_rate_ms"),
        "vertical_status":   record.get("vertical_status"),

        "last_update": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    try:
        (
            _firestore_db
            .collection("adsb")
            .document("latest")
            .collection("messages")
            .document(icao)
            .collection("types")
            .document(msg_type)
            .set(payload)
        )
        print(f"  [✓] Firestore → {icao}/{msg_type}")
    except Exception as e:
        print(f"  [!] Firestore push failed: {e}")


# ── Process one JSON file ─────────────────────────────────────────────────
def _process_file(filepath: str):
    # Wait until the file is fully written
    for _ in range(10):
        try:
            if os.path.getsize(filepath) > 0:
                break
        except FileNotFoundError:
            return
        time.sleep(0.02)

    try:
        with open(filepath, "r") as f:
            record = json.load(f)
    except Exception as e:
        print(f"[!] Could not read {filepath}: {e}")
        return

    icao      = record.get("icao") or "UNKNOWN"
    msg_type  = record.get("message_type", "UNKNOWN")
    crc_ok    = record.get("crc_valid", False)
    snr       = record.get("snr_db")
    lat       = record.get("latitude")
    lon       = record.get("longitude")
    reg       = record.get("registration") or "—"
    model     = record.get("model") or "—"

    print(
        f"\n[→] ICAO:{icao}  type:{msg_type}  "
        f"CRC:{'✓' if crc_ok else '✗'}  SNR:{snr} dB\n"
        f"    reg:{reg}  model:{model}  "
        f"lat:{lat}  lon:{lon}"
    )

    if _firestore_ready:
        _push_to_firestore(record)

    session_key = f"{icao}_{record.get('shift_index', 0)}"
    with _session_lock:
        _session_messages[session_key] = record
        _write_results_all()

    dest = os.path.join(SENT_DIR, os.path.basename(filepath))
    try:
        shutil.move(filepath, dest)
        print(f"  [✓] archived → {dest}")
    except Exception as e:
        print(f"[!] Could not move {filepath}: {e}")


# ── Watchdog ──────────────────────────────────────────────────────────────
class _JSONHandler(FileSystemEventHandler):

    def _is_target(self, path: str) -> bool:
        name = os.path.basename(path)
        return name.endswith(".json") and name[:-5].lstrip("-").isdigit()

    def on_created(self, event):
        if not event.is_directory and self._is_target(event.src_path):
            time.sleep(0.02)
            _process_file(event.src_path)

    def on_moved(self, event):
        if not event.is_directory and self._is_target(event.dest_path):
            time.sleep(0.02)
            _process_file(event.dest_path)


# ── Drain any leftover files from previous run ────────────────────────────
def _drain_existing():
    pending = sorted([
        os.path.join(OUTPUT_DIR, f)
        for f in os.listdir(OUTPUT_DIR)
        if f.endswith(".json") and f[:-5].lstrip("-").isdigit()
    ])
    if pending:
        print(f"[i] {len(pending)} unprocessed file(s) from previous run")
        for fp in pending:
            _process_file(fp)


# ── Main ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print(" ADS-B → Firestore Watcher")
    print("=" * 50)

    _init_firebase()
    _drain_existing()

    observer = Observer()
    observer.schedule(_JSONHandler(), path=OUTPUT_DIR, recursive=False)
    observer.start()
    print(f"[✓] Watching {OUTPUT_DIR}/")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

    print(f"\n[i] Session total: {len(_session_messages)} frames")