import math
import matplotlib.pyplot as plt
import numpy as np
import time
from matplotlib.widgets import Button, TextBox
import threading
import json
import pyModeS as pms
from pyModeS.util import bin2hex, crc
import os

# A script to visualize the sample(or time) versus magnitude signal from SDR tuned to 1090 MHz
# WITH SDR Sampling Frequency set to 2 Million Samples Per Second
# Chunked streaming version: processes 120 MB file in 100k-sample chunks
# Results are written to JSON immediately when a preamble is confirmed

# ── Global results store (written live to disk on every confirmed detection) ──
RESULTS_FILE = "output/results.json"
os.makedirs("output", exist_ok=True)
"""
if os.path.exists(RESULTS_FILE):
    with open(RESULTS_FILE, "r") as _f:
        all_results = json.load(_f)
    # Ensure any legacy or manually edited results file still has required keys
    all_results.setdefault("capture_file", "")
    all_results.setdefault("sample_rate_msps", 2)
    all_results.setdefault("detections", [])
    all_results.setdefault("total_c1", 0)
    all_results.setdefault("total_c2", 0)
    all_results.setdefault("total_c3", 0)
    all_results.setdefault("total_final", 0)
else:"""
all_results = {
        "capture_file": "",
        "sample_rate_msps": 2,
        "detections": [],
        "total_c1": 0,
        "total_c2": 0,
        "total_c3": 0,
        "total_final": 0
    }

# ── Preamble template (26-element characteristic word) ───────────────────────
preamble    = np.zeros(26)
PeaksIndex  = [0, 2, 7, 9, 16, 19, 21, 23, 24]   # α-positions
for _p in PeaksIndex:
    preamble[_p] = 1

# ── Bit slicer (unchanged from your original) ────────────────────────────────
def Bit_Slicer(message, Msg_length=224):
    for key, value in message.items():
        decoded = []
        for k in range(0, Msg_length, 2):
            if value[k] >= value[k + 1]:
                decoded.append(1)
            elif value[k] < value[k + 1]:
                decoded.append(0)
            else:
                decoded[:] = "Rejected"
                break
        message[key] = "".join(map(str, decoded))
def DecoderAdsb(binmsg,global_byte,c1_ratio,c3_ratio,c4_count):
               


    try :
        bin_str = str(binmsg)
        hex_msg = pms.util.bin2hex(bin_str)
        
        # Use pyModeS high-level decode
        decoded = pms.decode(hex_msg)
        
        is_valid = decoded.get("crc_valid", False)
        tc = decoded.get("typecode")
        icao = decoded.get("icao")
        
        # Initialize the output dictionary with all potential fields set to None
        output = {
            "hex_msg": hex_msg,
            "crc_valid": is_valid,
            "icao": icao,
            "typecode": tc,
            "message_category": None,
            "global_byte" : global_byte,
            "c1_ratio": c1_ratio,
            "c3_ratio": c3_ratio,
            "c4_count": c4_count,
            "callsign": None,
            "groundspeed_kts": None,
            "groundspeed_kmh": None,
            "airspeed_kts": None,
            "airspeed_kmh": None,
            "track_angle": None,
            "heading": None,
            "vertical_rate_fpm": None,
            "vertical_rate_ms": None,
            "vertical_status": None,
            "altitude_ft": None,
            "latitude": None,
            "longitude": None,
            "raw_cpr_lat": None,
            "raw_cpr_lon": None,
            "capability": None,
            "error": None
        }

        # Check for message validity before proceeding
        if not is_valid or tc is None:
            output["error"] = "Invalid CRC or Unknown Typecode"
            return output

        # [1-4] IDENTIFICATION
        if 1 <= tc <= 4:
            output["message_category"] = "IDENTIFICATION"
            output["callsign"] = decoded.get("callsign")

        # [5-8] SURFACE POSITION
        elif 5 <= tc <= 8:
            output["message_category"] = "SURFACE POSITION"
            gs = decoded.get('groundspeed')
            if gs is not None:
                output["groundspeed_kts"] = gs
                output["groundspeed_kmh"] = round(gs * 1.852, 2)
            
            lat = decoded.get('latitude')
            lon = decoded.get('longitude')
            if lat is not None and lon is not None:
                output["latitude"] = lat
                output["longitude"] = lon
            elif len(bin_str) >= 88:
                output["raw_cpr_lat"] = int(bin_str[54:71], 2)
                output["raw_cpr_lon"] = int(bin_str[71:88], 2)

        # [9-18] AIRBORNE POSITION
        elif 9 <= tc <= 18:
            output["message_category"] = "AIRBORNE POSITION"
            output["altitude_ft"] = decoded.get('altitude')  # Fixed the syntax from your original snippet
            
            lat = decoded.get('latitude')
            lon = decoded.get('longitude')
            if lat is not None and lon is not None:
                output["latitude"] = lat
                output["longitude"] = lon
            elif len(bin_str) >= 88:
                output["raw_cpr_lat"] = int(bin_str[54:71], 2)
                output["raw_cpr_lon"] = int(bin_str[71:88], 2)

        # [19] AIRBORNE VELOCITY
        elif tc == 19:
            output["message_category"] = "AIRBORNE VELOCITY"
            
            gs = decoded.get('groundspeed')
            if gs is not None:
                output["groundspeed_kts"] = gs
                output["groundspeed_kmh"] = round(gs * 1.852, 2)
                output["track_angle"] = decoded.get('track')
                
            airspeed = decoded.get('airspeed')
            if airspeed is not None:
                output["airspeed_kts"] = airspeed
                output["airspeed_kmh"] = round(airspeed * 1.852, 2)
                output["heading"] = decoded.get('heading')
                
            vrate_fpm = decoded.get('vertical_rate')
            if vrate_fpm is not None:
                output["vertical_rate_fpm"] = vrate_fpm
                output["vertical_rate_ms"] = round((vrate_fpm * 0.3048) / 60, 2)
                output["vertical_status"] = "Climbing" if vrate_fpm > 0 else "Descending"

        # [31] OPERATIONAL STATUS
        elif tc == 31:
            output["message_category"] = "OPERATIONAL STATUS"
            output["capability"] = decoded.get("capability")
        #print(output)
        return output

    except Exception as e:
        # Returns the error safely inside the dict rather than crashing the script
        return {"error": str(e)}

# ── SNR calculation (unchanged from your original) ───────────────────────────
def SNR_Calculation(index, signal):
    l = signal[index: index + 224]
    p = signal[max(0, index - 225): index - 1]
    x = (sum(l)) * (sum(l)) / 224          # signal power estimate
    w = (sum(p)) * (sum(p)) / 224          # noise power estimate
    if w <= 0:
        return 0.0
    return round(10 * math.log10(x / w), 2)

def save_detection(local_idx, global_byte, c1_ratio, c3_ratio, c4_count, signal):
    # Assuming SNR_Calculation is defined elsewhere in your script
    snr = SNR_Calculation(local_idx, signal)

    
    start = local_idx + 16
    end = start + 224
    if end > len(signal):
        return None

    msg_samples = signal[start:end]
    bits = []
    for k in range(0, 224, 2):
        if msg_samples[k] >= msg_samples[k + 1]:
            bits.append('1')
        else:
            bits.append('0')

    bin_strr = "".join(bits)
       # Call the decoding function to print message details
    # Execute the decode attempt
    detection = DecoderAdsb(bin_strr,global_byte,c1_ratio,c3_ratio,c4_count)

    # Set up default empty values in case decoding failed
    """msg_data = {
        "hex_msg": None, "offset": None, "icao": None, "typecode": None, 
        "crc_valid": False, "callsign": None, "altitude": None, 
        "latitude": None, "longitude": None, "speed": None, 
        "heading": None, "vertical_rate": None
    }
    
    # If successful, overwrite the defaults with actual data
    if msg_data is not None:
        msg_data.update(best_candidate)
    
    # Build the final detection dictionary mapped cleanly
    detection = {
        "global_byte_offset": global_byte,
        "message_offset":     msg_data["offset"],
        "c1_ratio":           round(c1_ratio, 3),
        "c2_match":           True,
        "c3_power_ratio":     round(c3_ratio, 3),
        "c4_null_count":      c4_count,
        "snr_db":             snr,
        "final_decision":     True,
        "hex_message":        msg_data["hex"],
        "icao":               msg_data["icao"],
        "typecode":           msg_data["typecode"],
        "crc_valid":          msg_data["crc_valid"],
        "callsign":           msg_data["callsign"],
        "altitude":           msg_data["altitude"],
        "latitude":           msg_data["latitude"],
        "longitude":          msg_data["longitude"],
        "groundspeed":        msg_data["speed"],       # Maps your groundspeed field to the extracted speed
        "track":              msg_data["heading"],     # Maps your track field to the extracted heading
        "vertical_rate":      msg_data["vertical_rate"]
    }
    """
    print(detection)
    all_results["detections"].append(detection)
    all_results["total_final"] += 1
   # Save the updated results to the JSON file
    with open(RESULTS_FILE, "w") as _f:
        json.dump(all_results, _f, indent=2)

    # Safely extract values from the 'detection' dict we just built
    """icao = detection["icao"] if detection["icao"] is not None else "N/A"
    tc = detection["typecode"] if detection["typecode"] is not None else "N/A"
    hex_msg_str = detection["hex_message"] if detection["hex_message"] is not None else "N/A"
    crc_status = "✓ VALID" if detection["crc_valid"] else "✗ FAIL"
    """
    # Print the formatted output
    print(f"\n✓  PREAMBLE CONFIRMED"
          f"  global_byte={global_byte:,}"
          f"  SNR={snr:.1f} dB"
          f"  C1={c1_ratio:.1f}"
          f"  C3={c3_ratio:.2f}"
          f"  C4_nulls={c4_count}"
          f"  HEX={detection["hex_msg"]}"
          f"  ICAO={detection["icao"]}"
          f"  TC={detection["typecode"]}"
          f"  CRC={detection["crc_valid"]}")
# ── Process one chunk: run all 4 criteria, write JSON on each confirmation ───
def process_chunk(signal, byte_offset, overlap_len,
                  total_c1, total_c2, total_c3, total_c4):
    """
    signal      : list of magnitude floats  =  overlap_buffer + chunk_mag
                  signal[0]  is NOT the start of the current chunk —
                  the first overlap_len samples belong to the END of the
                  previous chunk (already counted in byte_offset).

    byte_offset : file byte position of the FIRST byte of chunk_mag
                  (i.e. the position AFTER the previous chunk, NOT
                  counting the overlap).

    overlap_len : number of samples prepended from the previous chunk.

    Global sample index of signal[i]:
        global_sample = (byte_offset // 2) - overlap_len + i
    Global byte offset of signal[i]:
        global_byte   = global_sample * 2

    total_c1/2/3/4 : running counters, returned updated
    """

    # ── CRITERION 1: CFAR correlation ────────────────────────────────────────
    CorrelationValues = np.correlate(signal, preamble, mode="valid")

    Threshold        = 8
    ExceedThreshold  = {}           # { local_index : c1_ratio }

    for maximum in range(20, len(CorrelationValues)):
        valleyAvg = 0.2 * (
            CorrelationValues[maximum - 6]  +
            CorrelationValues[maximum - 11] +
            CorrelationValues[maximum - 13] +
            CorrelationValues[maximum - 18] +
            CorrelationValues[maximum - 20]
        )
        if valleyAvg < 0.001:       # avoid division by zero / very small noise
            continue

        PeakValue    = CorrelationValues[maximum]
        Static_Ratio = PeakValue / valleyAvg

        if Static_Ratio > Threshold:
            if ExceedThreshold:
                last_key = list(ExceedThreshold)[-1]
                if maximum - last_key < 240:
                    # Re-triggering: keep only the stronger peak
                    if Static_Ratio > list(ExceedThreshold.values())[-1]:
                        ExceedThreshold.popitem()
                        ExceedThreshold[maximum] = Static_Ratio
                else:
                    ExceedThreshold[maximum] = Static_Ratio
            else:
                ExceedThreshold[maximum] = Static_Ratio

    total_c1 += len(ExceedThreshold)

    #print(f"  C1: {len(ExceedThreshold)} candidates at indices "
     #     f"{list(ExceedThreshold.keys())}")

    # ── CRITERIA 2 / 3 / 4: tested immediately for each C1 candidate ─────────
    ref = "110010001"     # deterministic symbol pattern for DF=17

    for local_idx, c1_ratio in ExceedThreshold.items():

        # bounds check: need at least 26 samples ahead
        if local_idx + 26 > len(signal):
            continue

        # ── CRITERION 2: Deterministic Symbol Match ───────────────────────
        window = signal[local_idx: local_idx + 26]

        # 18 samples covering the 9 symbol pairs
        samples_18 = window[0:4] + window[6:10] + window[16:]  # same as your original

        temp = {local_idx: samples_18}
        Bit_Slicer(temp, Msg_length=18)

        if temp[local_idx] != ref:
            continue                # C2 failed → discard immediately

        total_c2 += 1
      #  print(f"    C2 passed at local_idx={local_idx}")

        # ── CRITERION 3: Consistent Power Test ───────────────────────────
        # Use the CORRECT α-positions from the paper
        peaks_9 = [
            window[0],  window[2],  window[7],  window[9],
            window[16], window[19], window[21], window[23], window[24]
        ]

        peak_min = min(peaks_9)
        if peak_min <= 0:
            continue                # avoid division by zero

        c3_ratio  = max(peaks_9) / peak_min
        Threshold3 = 5.656

        if c3_ratio >= Threshold3:
            continue                # C3 failed → discard immediately

        total_c3 += 1
       # print(f"    C3 passed at local_idx={local_idx}  power_ratio={c3_ratio:.2f}")

        # ── CRITERION 4: Null Symbol Validation ──────────────────────────
        sigma = sum(peaks_9) / 9    # dynamic threshold = mean of 9 peaks

        # β-positions: the 4 null symbol intervals (2 samples each)
        null_pairs = [
            (window[4],  window[5]),
            (window[10], window[11]),
            (window[12], window[13]),
            (window[14], window[15])
        ]

        empty_count = 0
        for s1, s2 in null_pairs:
            if s1 <= sigma / 2 and s2 <= sigma / 2:
                empty_count += 1

        if empty_count < 2:
            continue                # C4 failed → discard immediately

        # ── ALL 4 CRITERIA PASSED ─────────────────────────────────────────
        total_c4 += 1

        # ── Correct global byte address ───────────────────────────────────
        # signal = buffer + chunk_mag
        # signal[0] is the first overlap sample, which already appeared
        # at the END of the previous chunk. Its file byte position is:
#            (byte_offset - overlap_len * 2)
        # Therefore signal[local_idx] is at:
#            global_sample = (byte_offset // 2) - overlap_len + local_idx
#            global_byte   = global_sample * 2
        global_sample = (byte_offset // 2) - overlap_len + local_idx
        global_byte   = global_sample

        save_detection(local_idx, global_byte,
                       c1_ratio, c3_ratio, empty_count, signal)

    return total_c1, total_c2, total_c3, total_c4, list(ExceedThreshold.keys())


#main 
condition = True
while condition:
    print("=====================>>>>>>>><<<<<<<==================")
    
    print("=====================>>>>>>>><<<<<<<==================")
    print("\nWelcome to ADS-B Visualizer >>>")
    print("\nPress 0 to exit")
    File = (input("\nTo Convert File Select 1, to read from file select 2 : "))

    if File =="1":
        Filename =  input("\n Filename: ")
        Filename = "C:/Users/ucef-/Desktop/Captures/"+Filename
        data = np.fromfile(Filename, dtype=np.int16);
        (((data.astype(np.float32) + 32768) / 256)).astype(np.uint8).tofile('C:/Users/ucef-/Desktop/Captures/ForRtl/output_8bit.bin')
        BinaryFile = "C:/Users/ucef-/Desktop/Captures/ForRtl/output_8bit.bin"
    elif File =="2" :

        BinaryFile = "C:/Users/ucef-/Desktop/raw_iq_signalsflights5.bin"
    
    file_size  = os.path.getsize(BinaryFile)
    print(f"\n>>> your file is of size {file_size} number of IQ Samples is : {file_size//2} <<<")
    NSamples   = int(input("Enter the number of samples in plot (20, 100, 2000): ")) * 2
    timeOfPlot = (NSamples / 2) * 0.5
    SliceN     = input(
        f"Select the slice you want to visualize by entering the X multiple "
        f"integer of the {timeOfPlot} micro sec: "
    )

    # Only exit the main loop when the user explicitly requests it by
    # entering '0' at the top menu. The previous condition always
    # evaluated to True for non-zero numeric inputs, causing an early exit.
    if File == "0":
        break

    # scaler for plot x-axis ticks (unchanged)
    if NSamples <= 50:
        scaler = 1
    elif NSamples <= 200:
        scaler = 2
    elif NSamples <= 1000:
        scaler = 50
    else:
        scaler = 100

    
    file_size  = os.path.getsize(BinaryFile)
    all_results["capture_file"] = BinaryFile

    print(f"\nFile: {BinaryFile}  ({file_size/1e6:.1f} MB)")
    if NSamples//50_000 ==0:
        
        CHUNK_SAMPLES = NSamples//2 
    else :
        CHUNK_SAMPLES = 100_000
             # 100k IQ pairs = 200k bytes per chunk
    OVERLAP       = 256         # samples carried over to next chunk
    DC_Shift      = 0.7

    buffer      = []            # overlap buffer from previous chunk
    byte_offset = 0             # current file position in bytes
    total_c1 = total_c2 = total_c3 = total_c4 = 0

    # ── Calculate byte position for the desired slice ──
    # NSamples is already multiplied by 2 from user input
    # Each sample is 1 byte (I or Q), so NSamples bytes per sample pair
    vis_start_byte = NSamples * (int(SliceN) - 1)
    vis_end_byte = NSamples * (int(SliceN) )
    print(f"\nVisualization start byte: {vis_start_byte} and end byte {vis_start_byte}")  # position in BYTES
    vis_Magnitude  = []
    vis_CorrelationValues = None

    with open(BinaryFile, "rb") as f:
        # ── SEEK to the beginning of the desired visualization slice ──
        f.seek(vis_start_byte)
        byte_offset = vis_start_byte

        # ── Read only the slice requested by the user, plus overlap if needed ──
        read_limit = vis_start_byte + NSamples
        
        while byte_offset < read_limit and byte_offset < file_size:

            raw = f.read(CHUNK_SAMPLES * 2)     # read 200k bytes
            if not raw:
                break

            # ── Convert bytes → magnitude (same formula as your original) ──
            chunk_mag = []
            I_val = []
            Q_val = []  
            for i in range(0, len(raw) - 1, 2):
                I_val.append(raw[i]     - 127.5)
                Q_val.append(raw[i + 1] - 127.5)
            """print(I_val)"""
            #I_val -= np.mean(I_val)
            #Q_val -= np.mean(Q_val)
            """print(I_val)"""
            for j in range(len(list(I_val))):
                chunk_mag.append(math.sqrt(I_val[j] * I_val[j] + Q_val[j] * Q_val[j]) - DC_Shift)

            # ── Prepend overlap from previous chunk ──
            signal = buffer + chunk_mag

            # ── Capture the slice the user wants for the visualiser ──
            # Now that we've seeked to vis_start_byte, the first chunk we read IS the start
            if len(vis_Magnitude) == 0 and byte_offset == vis_start_byte:
                # First chunk after seeking: extract the visualization
                vis_Magnitude = signal[0: NSamples // 2]
                vis_CorrelationValues = np.correlate(
                    vis_Magnitude, preamble, mode="valid"
                )
            
            # ── Run the 4-criterion detector on this chunk ──
            total_c1, total_c2, total_c3, total_c4,ExceedThreshold = process_chunk(
                signal, byte_offset, len(buffer),
                total_c1, total_c2, total_c3, total_c4
            )

            # ── Update running totals in results file ──
            all_results["total_c1"] = total_c1
            all_results["total_c2"] = total_c2
            all_results["total_c3"] = total_c3
            all_results["total_c4"] = total_c4

            # ── Carry overlap to next chunk ──
            if CHUNK_SAMPLES ==100_000 :
                buffer      = chunk_mag[-OVERLAP:]
                
            byte_offset += len(raw)
            print(f"  Progress: {byte_offset/1e6:.1f} MB / "
                  f"{NSamples/1e6:.0f} MB   "
                  f"confirmed={total_c4}    "
                   
                  , end="\r")
    print (byte_offset)
    print(f"\n\nDone. C1={total_c1} ,   C2={total_c2}  "
          f"C3={total_c3}  C4={total_c4}")
    print(f"\nExceedthreshold_C1 = {ExceedThreshold}")
    print(f"Results saved to {RESULTS_FILE}")

    # ── Use vis_Magnitude for the visualiser below (same as your original) ──
    Magnitude        = vis_Magnitude  if vis_Magnitude  else []
    CorrelationValues = vis_CorrelationValues if vis_CorrelationValues is not None \
                        else np.array([0])
    limit = len(Magnitude) - 17
    start_byte = vis_start_byte

    
    # Build msg from confirmed detections for decoding
    msg = {}
    for det in all_results["detections"]:
        if det.get("hex_message"):
            idx = len(msg)
            msg[idx] = {
                "hex": det["hex_message"],
                "icao": det.get("icao"),
                "typecode": det.get("typecode"),
                "crc_valid": det.get("crc_valid"),
                "snr": det.get("snr_db"),
                "message_offset": det.get("message_offset"),
                "callsign": det.get("callsign"),
                "altitude": det.get("altitude"),
                "latitude": det.get("latitude"),
                "longitude": det.get("longitude"),
                "groundspeed": det.get("groundspeed"),
                "track": det.get("track"),
                "vertical_rate": det.get("vertical_rate"),
                "cpr_even_odd": det.get("cpr_even_odd")
            }

    # Display the already-decoded messages
    if msg:
        print("\n" + "="*70)
        print("DECODED MESSAGES FROM DETECTIONS:")
        print("="*70)
        for idx, msg_data in msg.items():
            print(f"\n[Message {idx}]")
            print(f"  HEX:            {msg_data['hex']}")
            print(f"  ICAO:           {msg_data['icao']}")
            print(f"  TC:             {msg_data['typecode']}")
            print(f"  CRC:            {'✓ VALID' if msg_data['crc_valid'] else '✗ FAILED'}")
            print(f"  SNR:            {msg_data['snr']} dB")
            if msg_data.get('message_offset') is not None:
                print(f"  Message offset: {msg_data['message_offset']} samples after preamble start")
            if msg_data.get('callsign'):
                print(f"  Callsign:       {msg_data['callsign']}")
            if msg_data.get('altitude') is not None:
                print(f"  Altitude:       {msg_data['altitude']}")
            if msg_data.get('groundspeed') is not None:
                print(f"  Ground Speed:   {msg_data['groundspeed']} knots")
            if msg_data.get('track') is not None:
                print(f"  Track:          {msg_data['track']}°")
            if msg_data.get('vertical_rate') is not None:
                print(f"  Vertical Rate:  {msg_data['vertical_rate']}")
            if msg_data.get('cpr_even_odd') is not None:
                print(f"  CPR parity:     {msg_data['cpr_even_odd']}")
            if msg_data.get('latitude') is not None and msg_data.get('longitude') is not None:
                print(f"  Latitude:       {msg_data['latitude']}")
                print(f"  Longitude:      {msg_data['longitude']}")
    else:
        print("\nNo decoded messages available.")
    limit = NSamples//2
    if limit < 2001:
        print("hi")
        plt.style.use('_mpl-gallery')
        
        class SignalShifter:
            def __init__(self, stem_container, base_xx, base_yy):
                self.shift_amount = 0
                self.stem_container = stem_container
                self.base_xx = base_xx
                self.base_yy = base_yy
            def Update_position(self):
                #new X positions
                new_xx = self.base_xx + self.shift_amount
                
                #Update the stem markers (the dots)
                self.stem_container.markerline.set_xdata(new_xx)#the circle at the top of the stick
                
                #Update the stem lines (the vertical sticks)
                new_segments = [[[x, 0], [x, y]] for x, y in zip(new_xx, self.base_yy)] #[[x, 0], [x, y]] this represnet the coordinate 
                self.stem_container.stemlines.set_segments(new_segments)#of the starting and ending point of the vertical line stick
                #zip takes your new x positions and your original heights (y) and pairs them up like a zipper. 
                #If x=5 and y=0.5, they become a pair: (5, 0.5).
                
                # 5. Redraw the plot!
                plt.draw()

            def Shift_by_button(self, event):
                
                self.shift_amount += 1
                self.Update_position()
                #print(f"Shift amount: {self.shift_amount}")
                
                
            def Shift_by_TextBox(self, text):
                try:
                    self.shift_amount=int(text)
                    self.Update_position()
                except:
                    print("enter an integer")


        Samples = int(NSamples/2)
        x = np.arange(0, int(Samples))
        y = vis_Magnitude

        # the preamble pattern 
        xx = np.arange(0, 26)
        yy = np.zeros(26) 
        yy[0], yy[2], yy[7], yy[9],yy[16],yy[19],yy[21],yy[23],yy[24] = 3, 3, 3, 3, 3, 3, 3, 3, 3

        Last_index = len(CorrelationValues)
        Corr_x = range(0,Last_index)
        
        Corr_y = vis_CorrelationValues

        fig2 = plt.figure(figsize=(6,4))
        cx = fig2.add_axes([0.07, 0.1, 1, 1])

        fig = plt.figure(figsize=(6, 4))
        ax = fig.add_axes([0.07, 0.1, 1, 1])

        
        
        # Plot signal and stem
        ax.plot(x, y, label="Signal")
        line = ax.stem(xx, yy, linefmt='red', label="Preamble pulses")

        ax.set_xlabel(f"IQ SAMPLES (A sample in 0.5 micro sec) S:{int(start_byte/2)}")
        ax.set_ylabel("Magnitude ")

        ax.set(xlim=(0, Samples), xticks= scaler*np.arange(1, Samples/scaler),
               ylim=(0, 12), yticks=np.arange(1, 12))
        print("hola")
        #  Button
        # Pass the stem container (line) and base arrays into the class
        callback = SignalShifter(line, xx, yy)

        ax_button = plt.axes([0.04, 0.005, 0.1, 0.04]) # [left, bottom, width, height]
        btn = Button(ax_button, 'Shift', color='lightgray', hovercolor='white')
        btn.on_clicked(callback.Shift_by_button)
        box = plt.axes([0.87, 0.005, 0.1, 0.04])
        InputShift= TextBox(box, "jump to: ", initial = "0")
        InputShift.on_submit(callback.Shift_by_TextBox)
        cx.plot(Corr_x,Corr_y, color="red")
        cx.set(xlim=(0, Last_index), xticks= scaler*np.arange(1, Last_index/scaler),
               ylim=(0, 500), yticks= range(0,500,50)) 
        
        plt.grid(visible=True)
        plt.show()
        #correlation graph 


        
        
        #plt.grid(visible=True)
        #plt.show()

    else :
        print("\n Reduce the number of Samples in plot -must be lower than 2000 - in order to VISUALIZE!")
