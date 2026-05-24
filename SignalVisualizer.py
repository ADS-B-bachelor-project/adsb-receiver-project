# import math
# import matplotlib.pyplot as plt
# import numpy as np
# import time
# from matplotlib.widgets import Button,TextBox
# import threading 
# import json
# import pyModeS as pms
# from pyModeS.util import bin2hex,crc

# #f1 = open("FoundMsg.txt", "r+")
# #binmsg = f1.readline()
# # A script to visualize the sample(or time) versus magnitude signal from SDR tunned to 1090 MHz 
# # WITH SDR Sampling Frequency set to 2 Million Sample Per Second

# condition = True
# while condition:
#     s=0
#     print("=====================>>>>>>>><<<<<<<==================")
#     print("\nWelcome to ADS-B Visualizer >>>")
#     print("\nPress 0 to exit ")
    
#     NSamples = int(input("Enter the number of samples in plot : 20,100,2000 :"))*2
#     timeOfPlot = (NSamples/2)*0.5
#     SliceN = input(f"Select the slice you want to visulaulize by entering the X multiple integer of the {timeOfPlot} micro sec: ")

#     if int(SliceN)==0:
#         break
#     if NSamples<= 50:
#         scaler=1
#     elif NSamples> 50 and NSamples<200:
#         scaler=2
#     elif NSamples>= 200 and NSamples<1000:
#         scaler=50
#     else:
#         scaler = 100
        
#     BinaryFile = "captures/capture_Stah1090MHZ.bin"

#     start_byte = 0# Where to start reading
    

#     with open(BinaryFile, "rb") as f:
#         #  Move the pointer to the start of your slice
#         start_byte= (NSamples)*(int(SliceN)-1)
#         f.seek(start_byte)
        		 	
#         chunk = f.read(NSamples)
#         I = []
#         Q = []
#         Magnitude = []
#         DC_Shift = 0.7
#         def GetMagnitude(I,Q): 
#             mag = math.sqrt(I*I + Q*Q) #calculate Magnitude 
#             return round(mag, 2)
        
        
#         for i in range(0,NSamples) : # To create two lists for I and Q samples and a list for Magnitudes

#             if (i%2)==0 :
#                 I.append(chunk[i]-127.5)
#                 if i==2:
#                         Magnitude.append(GetMagnitude(I[0],Q[0])- DC_Shift)
                    
#                 elif i>3:
#                     k = int((i/2)-1)
#                     Magnitude.append(GetMagnitude(I[k],Q[k])- DC_Shift)
#             else:
#                 Q.append(chunk[i]-127.5)
            

        
#     # preamble pulses
#     #print(len(Magnitude))
#     preamble = np.zeros(26) #To create a list of 16 items that are zeros 
#     PeaksIndex = [0,2,7,9,16,19,21,23,24]
#     #print(preamble)
    
#     f = []
#     for r in range(0,26):
#         for indx in PeaksIndex :
            
            
#             a = r==int(indx)
#             f.append(a)
#             if len(f)==len(PeaksIndex):
#                 if sum(f)==1:
#                     preamble[r]=1
#                     f=[]
#                 else:
                    
#                     preamble[r] = 0
#                     f=[] # to write preamble pulses 
                

              

#     #print(preamble)
#     Pcounter=0
#     PreambleStart = []
#     limit = int(NSamples/2)-17
#     #EstimtedTime = (limit/10000)*37
#     #print(f"Time Estimation is {EstimtedTime} in Second")

#     lock = threading.Lock() # used to enable multiple threads to print or append list without corrupting the data
#     Pcounter=0
#     PreambleStart = []
    
#     signal = Magnitude[0:int(NSamples/2)]

#     # CRITERION 1 : CFAR Detection 
#     CorrelationValues = np.correlate(signal, preamble, mode= "valid")
#     Static_Ratios = []
#     Threshold = 8
#     ExceedThreshold ={}
#     for maximum in range(20,len(CorrelationValues)):
#         Static_Ratio = 0
#         valleyAvg = 0.2*(CorrelationValues[maximum-6]+CorrelationValues[maximum-11]+
#             CorrelationValues[maximum-13]+CorrelationValues[maximum-18]+CorrelationValues[maximum-20])
#         PeakValue = CorrelationValues[maximum]

#         Static_Ratio = PeakValue/valleyAvg
#         #if valleyAvg <1 :
#         #    Static_Ratio= PeakValue/9
#         Static_Ratios.append(Static_Ratio)
#         if Static_Ratio>Threshold:
#             if ExceedThreshold:
#                 # To ignore the peaks of correlation of the ppm
                
                    
#                 if maximum-list(ExceedThreshold)[-1] < 240 :
#                     if Static_Ratio>list(ExceedThreshold.values())[-1]:
#                         ExceedThreshold.popitem()#delete last iem of dic
#                         ExceedThreshold[maximum] = Static_Ratio
#                 else:    
#                         ExceedThreshold[maximum] = Static_Ratio 
#             else :    
#                 ExceedThreshold[maximum] = Static_Ratio

#     def Bit_Slicer(message, Msg_length=224):
        
#         for key,value in message.items():
#             #print(f"key is {key}")
#             decoded=[]

#             for k in range(0,Msg_length,2):
                
#                 #print(f"\nlen value : {len(value)} string index : {k} and the value is {value}")
#                 if value[k] >= value[k+1]:
#                     decoded.append(1) 
#                 elif value[k] < value[k+1]:
#                     decoded.append(0)
#                 else:
#                     #del message[key]
#                     #print(f"Value 1 :{value[k]} and value2 : {value[k+1]} ")
#                     decoded[:] = "Rejected"
#                     break
#             #print(len(decoded))
#             message[key]="".join(map(str,decoded))
#             #print()
#     #Plotting the data using Matplotlib
#     Indices_2nd_criterion =[]
#     u =[]
#     Theta_2nd_criterion = {}
#     Theta = {}
    

#         #print(f"\nnumber of exceed C1: {len(ExceedThreshold)} \nthe indices  {key:15} , correlation: {value} ")
        
#     # Criterion 2 : DETERMINISTIC SYMBOL MATCH
        
        
#     for key, value in ExceedThreshold.items():
#         # 2. Logic to extract segments (Magnitude is likely your signal array)
#         e = Magnitude[key:key+26]
#         ref="110010001"
#         # We create a temporary dict for this specific key to pass to Bit_Slicer
#         temp_theta = {}
#         temp_theta[key] = e[0:4] + e[6:10] + e[-10:] # 18 samples total

#         # 3. Slice bits (18 samples / 2 = 9 bits)
#         Bit_Slicer(temp_theta, Msg_length=18)

#         # 4. Check for a match
#         # Since temp_theta only has one key, this loop is fast
#         for k, v in temp_theta.items():   
#             if v == ref:
#                 # Save the match to our master dictionary
#                 Theta_2nd_criterion[k] = v

# # Now, after the loop is done, you can see how many passed:
#     print(f"Total signals passing Criterion 2: {len(Theta_2nd_criterion)}")

#     max_idx = np.argmax(CorrelationValues)
#     #print(f"max value : {max(CorrelationValues)} index :{max_idx} ")
#     print(f"\nCriterion 1 : {len(ExceedThreshold)} success at {list(ExceedThreshold.keys())} ")
#     print(f"\nCriterion 2 : {len(Theta_2nd_criterion)} Success at {list(Theta_2nd_criterion.keys())}")
    


#     #Criterion 3: Consistent Power Test
#     ThetaD ={}
#     h=[]
#     Thershold3 = 6.656
#     ThetaD_3rd_criterion = {}
#     for index in Theta_2nd_criterion.keys():
#         k=0
#         Initial_Magnitudes = Magnitude[index:index+26]
#         # 0,2,5,7,8,11,13,15,16
#         k = [Initial_Magnitudes[0],Initial_Magnitudes[2],Initial_Magnitudes[7],Initial_Magnitudes[9]
#         ,Initial_Magnitudes[16],Initial_Magnitudes[19],Initial_Magnitudes[21],Initial_Magnitudes[23],Initial_Magnitudes[24]]
#         ThetaD[index] = k
#         #print(f"\nkey is {index} k is {k}")
#         PowerRatio = max(k)/min(k)
#         #print(f" \nPowerRatio is : {(PowerRatio)},")
#         if PowerRatio<Thershold3 :
#             ThetaD_3rd_criterion[index] =   PowerRatio 
#             h.append(index)
#     print(f"\ncriterion 3 : {len(ThetaD_3rd_criterion)} success , shifts {list(ThetaD_3rd_criterion.keys())}")

    
#     #criterion 4 :
#     Crit4 = {}
#     Success_4th_criterion = {}
#     for index in ThetaD_3rd_criterion.keys():
                
#         Initial_Magnitudes= Magnitude[index:index+26]   
#         Pulses = [Initial_Magnitudes[0],Initial_Magnitudes[2],Initial_Magnitudes[7],Initial_Magnitudes[9]
#         ,Initial_Magnitudes[16],Initial_Magnitudes[19],Initial_Magnitudes[21],Initial_Magnitudes[23],Initial_Magnitudes[24]]
        


#         sigma = sum(Pulses)/len(Pulses)        
        
#         X =  [Initial_Magnitudes[4],Initial_Magnitudes[5]]+ Initial_Magnitudes[10:16]
#         for r in range(0,8,2):
#             if (X[r] and X[r+1]) <=(sigma/2):
#                 Crit4[int(r/2)] = "Empty"
#         if len(Crit4)>=2:
#             Success_4th_criterion[index] = len(Crit4)
#     print(f"\ncriterion 4 : {len(Success_4th_criterion)} success , shifts {list(Success_4th_criterion.keys())}")
                







#     msg ={}
#     for start in Success_4th_criterion.keys():
#             msg[start]= Magnitude[start + 16:start+ 240]
#     #print(msg)
        
    

#     def Decoding(binmsg):
#     # Ensure binmsg is a dictionary of binary strings
#         for key, value in binmsg.items():
#             print(f"\n{'='*50}")
#             print(f"REPORT FOR INDEX: {key}")
            
#             try:
#                 # 1. Convert binary string to Hex 
#                 bin_str = str(value)
#                 hex_msg = pms.util.bin2hex(bin_str)
                
#                 # 2. Decode the message 
#                 decoded = pms.decode(hex_msg)
                
#                 # 3. Handle base validation
#                 is_valid = decoded.get("crc_valid", False)
#                 tc = decoded.get("typecode")
#                 icao = decoded.get("icao")

#                 print(f"Hex Message:  {hex_msg}")
#                 print(f"CRC Result:   {'Valid' if is_valid else 'Corrupted'}")
#                 print(f"ICAO Address: {icao}")
#                 print(f"Typecode:     {tc}")
#                 print(f"{'-'*50}")

#                 if not is_valid or tc is None:
#                     print("Skipping detailed parse (Invalid CRC or Unknown Typecode).")
#                     continue

#                 # 4. Detailed Parsing Logic

#                 # IDENTIFICATION (Typecodes 1-4)
#                 if 1 <= tc <= 4:
#                     print(f"[IDENTIFICATION]")
#                     print(f"Callsign: {decoded.get('callsign', 'N/A')}")

#                 # SURFACE POSITION (Typecodes 5-8)
#                 elif 5 <= tc <= 8:
#                     print(f"[SURFACE POSITION]")
                    
#                     # Ground Speed Math
#                     gs = decoded.get('groundspeed')
#                     if gs is not None:
#                         gs_kmh = round(gs * 1.852, 2)
#                         print(f"Ground Speed: {gs} knots ({gs_kmh} km/h)")
                    
#                     # Position & CPR Logic
#                     lat = decoded.get('latitude')
#                     lon = decoded.get('longitude')
                    
#                     if lat is not None and lon is not None:
#                         print(f"Global Latitude:  {lat}")
#                         print(f"Global Longitude: {lon}")
#                     else:
#                         # Manually slice the Raw CPR values from the 112-bit binary string
#                         if len(bin_str) >= 88:
#                             raw_lat = int(bin_str[54:71], 2)
#                             raw_lon = int(bin_str[71:88], 2)
#                             print(f"Raw CPR Lat: {raw_lat} (Need reference to decode Global Lat)")
#                             print(f"Raw CPR Lon: {raw_lon} (Need reference to decode Global Lon)")
                    
#                     # Get CPR Type (Fallback to checking bit 54 manually if missing)
#                     cpr = decoded.get("cpr_format")
#                     if cpr is None and len(bin_str) >= 54:
#                         cpr = int(bin_str[53])
#                     print(f"CPR Type: {'Odd' if cpr == 1 else 'Even'}")

#                 # AIRBORNE POSITION (Typecodes 9-18)
#                 elif 9 <= tc <= 18:
#                     print(f"[AIRBORNE POSITION]")
#                     print(f"Altitude:  {decoded.get('altitude', 'N/A')} ft")
                    
#                     lat = decoded.get('latitude')
#                     lon = decoded.get('longitude')
                    
#                     if lat is not None and lon is not None:
#                         print(f"Global Latitude:  {lat}")
#                         print(f"Global Longitude: {lon}")
#                     else:
#                         # Manually slice the Raw CPR values from the 112-bit binary string
#                         # Message Bit 55-71 (Lat) and 72-88 (Lon)
#                         if len(bin_str) >= 88:
#                             raw_lat = int(bin_str[54:71], 2)
#                             raw_lon = int(bin_str[71:88], 2)
#                             print(f"Raw CPR Lat: {raw_lat} (Need Odd/Even Pair to decode)")
#                             print(f"Raw CPR Lon: {raw_lon} (Need Odd/Even Pair to decode)")

#                     # Get CPR Type
#                     cpr = decoded.get("cpr_format")
#                     if cpr is None and len(bin_str) >= 54:
#                         cpr = int(bin_str[53])
#                     print(f"CPR Type: {'Odd' if cpr == 1 else 'Even'}")


#                 # AIRBORNE VELOCITY (Typecode 19)
#                 elif tc == 19:
#                     print(f"[AIRBORNE VELOCITY]")
                    
#                     # Ground Speed Math (Knots to km/h)
#                     gs = decoded.get('groundspeed')
#                     if gs is not None:
#                         gs_kmh = round(gs * 1.852, 2)
#                         print(f"Ground Speed: {gs} knots ({gs_kmh} km/h)")
#                         print(f"Track Angle:  {decoded.get('track')}°")
                    
#                     # Airspeed Math (Knots to km/h)
#                     airspeed = decoded.get('airspeed')
#                     if airspeed is not None:
#                         as_kmh = round(airspeed * 1.852, 2)
#                         print(f"Air Speed:    {airspeed} knots ({as_kmh} km/h)")
#                         print(f"Heading:      {decoded.get('heading')}°")
                    
#                     # Vertical Rate Math (fpm to km/min and m/s)
#                     vrate_fpm = decoded.get('vertical_rate')
#                     if vrate_fpm is not None:
#                         # Convert to Kilometers per minute
#                         vrate_km_min = round((vrate_fpm * 0.3048) / 1000, 4)
#                         # Convert to Meters per second (Commonly used in engineering)
#                         vrate_ms = round((vrate_fpm * 0.3048) / 60, 2)
                        
#                         status = "Climbing" if vrate_fpm > 0 else "Descending"
#                         print(f"Vertical Rate: {vrate_fpm} fpm ({status})")
#                         print(f"            -> {abs(vrate_km_min)} km/min")
#                         print(f"            -> {abs(vrate_ms)} m/s")

#                 # OPERATIONAL STATUS (Typecode 31)
#                 elif tc == 31:
#                     print(f"[OPERATIONAL STATUS]")
#                     print(f"Capability: {decoded.get('capability', 'N/A')}")

#             except Exception as e:
#                 print(f"Detailed Error at index {key}: {e}")
#     def SNR_Calculation(indices):
#         for index in indices :        


#             l = Magnitude[index:index+224]
#             x = (sum(l))*(sum(l))/224#SignalPower
            
#             p = Magnitude[index-225:index-1]
        
#             w = (sum(p))*(sum(p))/224 #noisePower
#             n = 10*math.log10(x/w)
#             print(f"\nthe SNR at {index} is {n}")
#     SNR_Calculation(Indices_2nd_criterion)
    
#     Bit_Slicer(msg)
#     print(msg)
#     Decoding(msg)
    
#     from adsb_to_firebase import decode_to_json, add_criterion_counts, save_json, push_to_firebase

#     result = decode_to_json(msg, Magnitude, capture_file=BinaryFile, start_byte=start_byte)

#     add_criterion_counts(result, c1=ExceedThreshold, c2=Theta_2nd_criterion,
#                      c3=ThetaD_3rd_criterion, c4=Success_4th_criterion)
#     save_json(result)
#     push_to_firebase(result)
    
#     if limit < 2000:
#         plt.style.use('_mpl-gallery')
        
#         class SignalShifter:
#             def __init__(self, stem_container, base_xx, base_yy):
#                 self.shift_amount = 0
#                 self.stem_container = stem_container
#                 self.base_xx = base_xx
#                 self.base_yy = base_yy
#             def Update_position(self):
#                 #new X positions
#                 new_xx = self.base_xx + self.shift_amount
                
#                 #Update the stem markers (the dots)
#                 self.stem_container.markerline.set_xdata(new_xx)#the circle at the top of the stick
                
#                 #Update the stem lines (the vertical sticks)
#                 new_segments = [[[x, 0], [x, y]] for x, y in zip(new_xx, self.base_yy)] #[[x, 0], [x, y]] this represnet the coordinate 
#                 self.stem_container.stemlines.set_segments(new_segments)#of the starting and ending point of the vertical line stick
#                 #zip takes your new x positions and your original heights (y) and pairs them up like a zipper. 
#                 #If x=5 and y=0.5, they become a pair: (5, 0.5).
                
#                 # 5. Redraw the plot!
#                 plt.draw()

#             def Shift_by_button(self, event):
                
#                 self.shift_amount += 1
#                 self.Update_position()
#                 #print(f"Shift amount: {self.shift_amount}")
                
                
#             def Shift_by_TextBox(self, text):
#                 try:
#                     self.shift_amount=int(text)
#                     self.Update_position()
#                 except:
#                     print("enter an integer")


#         Samples = int(NSamples/2)-1
#         x = np.arange(0, int(Samples))
#         y = Magnitude

#         # the preamble pattern 
#         xx = np.arange(0, 26)
#         yy = np.zeros(26) 
#         yy[0], yy[2], yy[7], yy[9],yy[16],yy[19],yy[21],yy[23],yy[24] = 3, 3, 3, 3, 3, 3, 3, 3, 3

#         Last_index = len(CorrelationValues)
#         Corr_x = range(0,Last_index)
        
#         Corr_y = CorrelationValues

#         fig2 = plt.figure(figsize=(6,4))
#         cx = fig2.add_axes([0.07, 0.1, 1, 1])

#         fig = plt.figure(figsize=(6, 4))
#         ax = fig.add_axes([0.07, 0.1, 1, 1])

        
        
#         # Plot signal and stem
#         ax.plot(x, y, label="Signal")
#         line = ax.stem(xx, yy, linefmt='red', label="Preamble pulses")

#         ax.set_xlabel(f"IQ SAMPLES (A sample in 0.5 micro sec) S:{int(start_byte/2)}")
#         ax.set_ylabel("Magnitude ")

#         ax.set(xlim=(0, Samples), xticks= scaler*np.arange(1, Samples/scaler),
#                ylim=(0, 12), yticks=np.arange(1, 12))

#         #  Button
#         # Pass the stem container (line) and base arrays into the class
#         callback = SignalShifter(line, xx, yy)

#         ax_button = plt.axes([0.04, 0.005, 0.1, 0.04]) # [left, bottom, width, height]
#         btn = Button(ax_button, 'Shift', color='lightgray', hovercolor='white')
#         btn.on_clicked(callback.Shift_by_button)
#         box = plt.axes([0.87, 0.005, 0.1, 0.04])
#         InputShift= TextBox(box, "jump to: ", initial = "0")
#         InputShift.on_submit(callback.Shift_by_TextBox)
#         cx.plot(Corr_x,Corr_y, color="red")
#         cx.set(xlim=(0, Last_index), xticks= scaler*np.arange(1, Last_index/scaler),
#                ylim=(0, 500), yticks= range(0,500,50)) 
        
#         plt.grid(visible=True)
#         plt.show()
#         #correlation graph 


        
        
#         #plt.grid(visible=True)
#         #plt.show()

#     else :
#         print("\n Reduce the number of Samples in plot -must be lower than 2000 - in order to VISUALIZE!")


import math
import os
import matplotlib.pyplot as plt
import numpy as np
import time
from matplotlib.widgets import Button,TextBox
import threading 
import json
import os                        # ← NEW
import datetime                  # ← NEW
import pyModeS as pms
from pyModeS.util import bin2hex,crc
from aircraft_lookup import lookup, load_database

# ── output folder (adsb_to_firebase.py watches this) ──────────────────────
OUTPUT_DIR = "output"            # ← NEW
os.makedirs(OUTPUT_DIR, exist_ok=True)  # ← NEW
# Aircraft database path
AIRCRAFT_DB_PATH = "aircraft-database.csv"

# Load database once at startup
load_database(AIRCRAFT_DB_PATH)

# ================================================================
#  PASTE THIS BLOCK AT THE TOP OF SignalVisualizer.py
#  (replace the existing import block and export_message function)
# ================================================================

import math
import os
import matplotlib.pyplot as plt
import numpy as np
import time
import threading
import json
import datetime
import pyModeS as pms
from pyModeS.util import bin2hex, crc

# ── NEW imports ───────────────────────────────────────────────────────────
from aircraft_lookup import lookup, load_database
from cpr_position_buffer import attempt_position_decode, get_buffer_status

# ── Output folder (adsb_to_firebase.py watches this) ─────────────────────
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Load aircraft database once at startup ────────────────────────────────
AIRCRAFT_DB_PATH = "aircraft-database.csv"
load_database(AIRCRAFT_DB_PATH)


# ================================================================
#  export_message()   ← FULL REPLACEMENT
#
#  WHAT CHANGED vs the old version:
#  1. For AIRBORNE_POSITION (TC 9-18):
#       - Does NOT write a JSON file immediately.
#       - Passes the message to cpr_position_buffer.attempt_position_decode()
#       - Only writes JSON when a valid EVEN+ODD pair is decoded.
#  2. For all other message types:
#       - Behaviour unchanged — JSON written immediately.
#  3. Aircraft DB lookup now fills ALL 27 columns from the CSV.
# ================================================================

# ================================================================
#  PASTE THIS BLOCK AT THE TOP OF SignalVisualizer.py
#  (replace the existing import block and export_message function)
# ================================================================

import math
import os
import matplotlib.pyplot as plt
import numpy as np
import time
import threading
import json
import datetime
import pyModeS as pms
from pyModeS.util import bin2hex, crc

# ── NEW imports ───────────────────────────────────────────────────────────
from aircraft_lookup import lookup, load_database
from cpr_position_buffer import attempt_position_decode, get_buffer_status

# ── Output folder (adsb_to_firebase.py watches this) ─────────────────────
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Load aircraft database once at startup ────────────────────────────────
AIRCRAFT_DB_PATH = "aircraft-database.csv"
load_database(AIRCRAFT_DB_PATH)


# ================================================================
#  export_message()   ← FULL REPLACEMENT
#
#  WHAT CHANGED vs the old version:
#  1. For AIRBORNE_POSITION (TC 9-18):
#       - Does NOT write a JSON file immediately.
#       - Passes the message to cpr_position_buffer.attempt_position_decode()
#       - Only writes JSON when a valid EVEN+ODD pair is decoded.
#  2. For all other message types:
#       - Behaviour unchanged — JSON written immediately.
#  3. Aircraft DB lookup now fills ALL 27 columns from the CSV.
# ================================================================

def export_message(shift_index, bin_str, magnitude,
                   capture_file, start_byte,
                   c1_ratio=None, c3_power_ratio=None, c4_null_count=None):
    """
    Called once per detected frame immediately after bit-slicing.

    For position messages (TC 9-18): stores the CPR frame and waits
    for its pair (even↔odd). Only writes JSON when both are available
    and the real lat/lon has been decoded.

    For all other message types: decodes and writes JSON immediately.
    """

    # ── Step 1: Decode the binary string ─────────────────────────────────
    record = _build_base_record(
        shift_index, bin_str, magnitude,
        capture_file, start_byte,
        c1_ratio, c3_power_ratio, c4_null_count
    )

    # ── Step 2: Route based on message type ──────────────────────────────
    msg_type = record.get("message_type", "UNKNOWN")
    tc        = record.get("typecode")

    is_position_msg = (
        record.get("crc_valid") and
        tc is not None and
        (9 <= tc <= 18 or 5 <= tc <= 8)   # airborne OR surface position
    )

    if is_position_msg:
        # ── POSITION: hand off to CPR buffer — DO NOT write JSON yet ─────
        icao       = record.get("icao")
        cpr_format = record.get("cpr_format")   # "Even" or "Odd"
        hex_msg    = record.get("hex_message")

        if icao and cpr_format and hex_msg:
            print(f"[CPR] Position message received — ICAO:{icao.upper()}  "
                  f"Format:{cpr_format}  TC:{tc}")
            print(f"[CPR] Buffer status: {get_buffer_status()}")

            # attempt_position_decode() returns:
            #   None  → still waiting for the other CPR format
            #   dict  → both formats received, real position decoded
            completed = attempt_position_decode(
                icao, cpr_format, hex_msg, record
            )

            if completed is None:
                # Waiting for the pair — print status and return without writing
                print(f"[CPR] ⏳ Waiting for "
                      f"{'ODD' if cpr_format == 'Even' else 'EVEN'} "
                      f"message from ICAO {icao.upper()}")
                return   # ← JSON NOT written yet

            # ── Pair complete — use the completed (position-filled) record
            record = completed
            print(f"[CPR] ✅ Writing position JSON for ICAO {icao.upper()}")
        else:
            print(f"[CPR] Missing ICAO/format/hex — skipping CPR buffer")
            return

    # ── Step 3: Write JSON (for non-position, or completed position pair) ─
    _write_json(record)


# ================================================================
#  _build_base_record()
#  Decodes the 112-bit binary string and builds the full record dict.
#  Does everything the OLD export_message() did, minus the file write.
# ================================================================

def _build_base_record(shift_index, bin_str, magnitude,
                       capture_file, start_byte,
                       c1_ratio, c3_power_ratio, c4_null_count):
    """
    Decode one ADS-B frame and return a dict with all fields.
    Does NOT write any file — that is _write_json()'s job.
    """

    record = {
        # ── Signal / capture metadata ─────────────────────────────────────
        "shift_index":        shift_index,
        "captured_at":        datetime.datetime.utcnow().isoformat() + "Z",
        "capture_file":       capture_file,
        "slice_start_byte":   start_byte,
        "sample_rate_msps":   2,
        "final_decision":     True,
        "c1_ratio":           round(c1_ratio, 3)       if c1_ratio       is not None else None,
        "c2_match":           True,
        "c3_power_ratio":     round(c3_power_ratio, 4) if c3_power_ratio is not None else None,
        "c4_null_count":      int(c4_null_count)        if c4_null_count  is not None else None,
        "snr_db":             _snr(shift_index, magnitude),

        # ── Aircraft database fields (filled after DB lookup) ─────────────
        "registration":       None,
        "manufacturericao":   None,
        "manufacturername":   None,
        "model":              None,
        "typecode_db":        None,
        "serialnumber":       None,
        "linenumber":         None,
        "icaoaircrafttype":   None,
        "operator":           None,
        "operatorcallsign":   None,
        "operatoricao":       None,
        "operatoriata":       None,
        "owner":              None,
        "testreg":            None,
        "registered":         None,
        "reguntil":           None,
        "status":             None,
        "built":              None,
        "firstflightdate":    None,
        "seatconfiguration":  None,
        "engines":            None,
        "modes":              None,
        "adsb_equipped":      None,
        "acars":              None,
        "notes":              None,
        "categoryDescription": None,

        # ── Decoded ADS-B fields ──────────────────────────────────────────
        "hex_message":        None,
        "crc_valid":          False,
        "icao":               None,
        "typecode":           None,
        "df":                 None,
        "message_type":       "UNKNOWN",

        # ── Position fields ───────────────────────────────────────────────
        "altitude_ft":        None,
        "altitude_m":         None,
        "latitude":           None,
        "longitude":          None,
        "raw_cpr_lat":        None,
        "raw_cpr_lon":        None,
        "cpr_format":         None,
        "position_source":    None,
        "cpr_even_hex":       None,
        "cpr_odd_hex":        None,
        "cpr_gap_samples":    None,   # gap in samples between even and odd
        "cpr_gap_rf_s":       None,   # gap converted to RF seconds (gap/2MSPS)

        # ── Identification ────────────────────────────────────────────────
        "callsign":           None,

        # ── Velocity ─────────────────────────────────────────────────────
        "groundspeed_kt":     None,
        "groundspeed_kmh":    None,
        "track_angle_deg":    None,
        "airspeed_kt":        None,
        "airspeed_kmh":       None,
        "heading_deg":        None,
        "vertical_rate_fpm":  None,
        "vertical_rate_ms":   None,
        "vertical_status":    None,
    }

    # ── Decode the message ────────────────────────────────────────────────
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

            # IDENTIFICATION (TC 1-4)
            if 1 <= tc <= 4:
                record["message_type"] = "IDENTIFICATION"
                record["callsign"]     = decoded.get("callsign")

            # SURFACE POSITION (TC 5-8)
            elif 5 <= tc <= 8:
                record["message_type"] = "SURFACE_POSITION"
                gs = decoded.get("groundspeed")
                if gs is not None:
                    record["groundspeed_kt"]  = round(gs, 2)
                    record["groundspeed_kmh"] = round(gs * 1.852, 2)
                # Raw CPR — real position decoded later via CPR buffer
                if len(bin_str) >= 88:
                    record["raw_cpr_lat"] = int(bin_str[54:71], 2)
                    record["raw_cpr_lon"] = int(bin_str[71:88], 2)
                cpr = decoded.get("cpr_format")
                if cpr is None and len(bin_str) >= 54:
                    cpr = int(bin_str[53])
                record["cpr_format"] = "Odd" if cpr == 1 else "Even"

            # AIRBORNE POSITION (TC 9-18)
            elif 9 <= tc <= 18:
                record["message_type"] = "AIRBORNE_POSITION"
                alt_ft = decoded.get("altitude")
                if alt_ft is not None:
                    record["altitude_ft"] = alt_ft
                    record["altitude_m"]  = round(alt_ft * 0.3048, 1)
                # Raw CPR — real position decoded later via CPR buffer
                if len(bin_str) >= 88:
                    record["raw_cpr_lat"] = int(bin_str[54:71], 2)
                    record["raw_cpr_lon"] = int(bin_str[71:88], 2)
                cpr = decoded.get("cpr_format")
                if cpr is None and len(bin_str) >= 54:
                    cpr = int(bin_str[53])
                record["cpr_format"] = "Odd" if cpr == 1 else "Even"

            # AIRBORNE VELOCITY (TC 19)
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
                    record["vertical_rate_ms"]  = round((vrate * 0.3048) / 60, 2)
                    record["vertical_status"]   = "Climbing" if vrate > 0 else "Descending"

            # OPERATIONAL STATUS (TC 31)
            elif tc == 31:
                record["message_type"] = "OPERATIONAL_STATUS"
                record["callsign"]     = str(decoded.get("capability", "N/A"))

            else:
                record["message_type"] = f"RESERVED_TC{tc}"

        else:
            record["message_type"] = "INVALID_CRC" if not is_valid else "UNKNOWN_TC"

    except Exception as e:
        record["message_type"] = f"DECODE_ERROR: {e}"

    # ── Aircraft database lookup ──────────────────────────────────────────
    _db_lookup(record)

    return record


def _db_lookup(record):
    """
    Fill all aircraft-database fields into record in-place.
    Called for every message type — ICAO is always available.
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


def _write_json(record):
    """
    Atomically write one JSON file to output/<shift_index>.json.
    Using os.replace() ensures adsb_to_firebase.py never reads a
    half-written file.
    """
    shift_index = record.get("shift_index", "unknown")
    out_path    = os.path.join(OUTPUT_DIR, f"{shift_index}.json")
    tmp_path    = out_path + ".tmp"

    with open(tmp_path, "w") as f:
        json.dump(record, f, indent=2)
    os.replace(tmp_path, out_path)

    print(f"  [export] → {out_path}  "
          f"ICAO:{record.get('icao')}  "
          f"type:{record.get('message_type')}  "
          f"lat:{record.get('latitude')}  "
          f"lon:{record.get('longitude')}")


def _snr(index, magnitude):
    """SNR calculation (same formula as original SignalVisualizer)."""
    sig   = magnitude[index: index + 224]
    noise = magnitude[max(0, index - 225): max(0, index - 1)]
    if len(sig) < 10 or len(noise) < 10:
        return None
    sp  = (sum(sig)   ** 2) / len(sig)
    np_ = (sum(noise) ** 2) / len(noise)
    if np_ <= 0:
        return None
    return round(10 * math.log10(sp / np_), 2)

# # ── helper: write one JSON file per detected frame ─────────────────────────
# def export_message(shift_index, bin_str, magnitude,   # ← NEW FUNCTION
#                    capture_file, start_byte,
#                    c1_ratio=None, c3_power_ratio=None, c4_null_count=None):
#     """
#     Called once per detected frame immediately after bit-slicing.
#     Decodes the 112-bit binary string, builds a record, and writes it to
#     output/<shift_index>.json so that adsb_to_firebase.py picks it up
#     in real time via file-system watching.
#     """
#     record = {
#         "shift_index":    shift_index,
#         "captured_at":    datetime.datetime.utcnow().isoformat() + "Z",
#         "capture_file":   capture_file,
#         "slice_start_byte": start_byte,
#         "sample_rate_msps": 2,
#         "final_decision": True,
#         "c1_ratio":       round(c1_ratio, 3)       if c1_ratio       is not None else None,
#         "c2_match":       True,
#         "c3_power_ratio": round(c3_power_ratio, 4) if c3_power_ratio is not None else None,
#         "c4_null_count":  int(c4_null_count)        if c4_null_count  is not None else None,
#         "snr_db":         _snr(shift_index, magnitude),
#         "registration": None,
#         "manufacturername": None,
#         "model": None,
#         "serialnumber": None,
#         "linenumber": None,
#         "operator": None,
#         "operatorcallsign": None,
#         "operatoricao": None,
#         "owner": None,
#         "built": None,
#         "status": None,
#         "registered": None,
#         "typecode_db": None,
#         "hex_message":    None,
#         "crc_valid":      False,
#         "icao":           None,
#         "typecode":       None,
#         "df":             None,
#         "message_type":   "UNKNOWN",
#         "altitude_ft":    None,
#         "altitude_m":     None,
#         "latitude":       None,
#         "longitude":      None,
#         "raw_cpr_lat":    None,
#         "raw_cpr_lon":    None,
#         "cpr_format":     None,
#         "callsign":       None,
#         "groundspeed_kt":    None,
#         "groundspeed_kmh":   None,
#         "track_angle_deg":   None,
#         "airspeed_kt":       None,
#         "airspeed_kmh":      None,
#         "heading_deg":       None,
#         "vertical_rate_fpm": None,
#         "vertical_rate_ms":  None,
#         "vertical_status":   None,
#     }

#     try:
#         hex_msg  = bin2hex(bin_str)
#         decoded  = pms.decode(hex_msg)
#         is_valid = decoded.get("crc_valid", False)
#         tc       = decoded.get("typecode")

#         record["hex_message"] = hex_msg
#         record["crc_valid"]   = bool(is_valid)
#         record["icao"]        = decoded.get("icao")
#         record["typecode"]    = tc
#         record["df"]          = decoded.get("df")

#         if is_valid and tc is not None:

#             if 1 <= tc <= 4:
#                 record["message_type"] = "IDENTIFICATION"
#                 record["callsign"]     = decoded.get("callsign")

#             elif 5 <= tc <= 8:
#                 record["message_type"] = "SURFACE_POSITION"
#                 gs = decoded.get("groundspeed")
#                 if gs is not None:
#                     record["groundspeed_kt"]  = round(gs, 2)
#                     record["groundspeed_kmh"] = round(gs * 1.852, 2)
#                 lat = decoded.get("latitude")
#                 lon = decoded.get("longitude")
#                 if lat is not None:
#                     record["latitude"]  = lat
#                     record["longitude"] = lon
#                 else:
#                     if len(bin_str) >= 88:
#                         record["raw_cpr_lat"] = int(bin_str[54:71], 2)
#                         record["raw_cpr_lon"] = int(bin_str[71:88], 2)
#                 cpr = decoded.get("cpr_format")
#                 if cpr is None and len(bin_str) >= 54:
#                     cpr = int(bin_str[53])
#                 record["cpr_format"] = "Odd" if cpr == 1 else "Even"

#             elif 9 <= tc <= 18:
#                 record["message_type"] = "AIRBORNE_POSITION"
#                 alt_ft = decoded.get("altitude")
#                 if alt_ft is not None:
#                     record["altitude_ft"] = alt_ft
#                     record["altitude_m"]  = round(alt_ft * 0.3048, 1)
#                 lat = decoded.get("latitude")
#                 lon = decoded.get("longitude")
#                 if lat is not None:
#                     record["latitude"]  = lat
#                     record["longitude"] = lon
#                 else:
#                     if len(bin_str) >= 88:
#                         record["raw_cpr_lat"] = int(bin_str[54:71], 2)
#                         record["raw_cpr_lon"] = int(bin_str[71:88], 2)
#                 cpr = decoded.get("cpr_format")
#                 if cpr is None and len(bin_str) >= 54:
#                     cpr = int(bin_str[53])
#                 record["cpr_format"] = "Odd" if cpr == 1 else "Even"

#             elif tc == 19:
#                 record["message_type"] = "AIRBORNE_VELOCITY"
#                 gs = decoded.get("groundspeed")
#                 if gs is not None:
#                     record["groundspeed_kt"]  = round(gs, 2)
#                     record["groundspeed_kmh"] = round(gs * 1.852, 2)
#                     record["track_angle_deg"] = decoded.get("track")
#                 airspeed = decoded.get("airspeed")
#                 if airspeed is not None:
#                     record["airspeed_kt"]  = round(airspeed, 2)
#                     record["airspeed_kmh"] = round(airspeed * 1.852, 2)
#                     record["heading_deg"]  = decoded.get("heading")
#                 vrate = decoded.get("vertical_rate")
#                 if vrate is not None:
#                     record["vertical_rate_fpm"] = vrate
#                     record["vertical_rate_ms"]  = round((vrate * 0.3048) / 60, 2)
#                     record["vertical_status"]   = "Climbing" if vrate > 0 else "Descending"

#             elif tc == 31:
#                 record["message_type"] = "OPERATIONAL_STATUS"
#                 record["callsign"]     = str(decoded.get("capability", "N/A"))

#             else:
#                 record["message_type"] = f"RESERVED_TC{tc}"

#         else:
#             record["message_type"] = "INVALID_CRC" if not is_valid else "UNKNOWN_TC"

#             # ==========================================================
#         # AIRCRAFT DATABASE LOOKUP
#         # ==========================================================

#         icao_hex = record["icao"]

#         if icao_hex:
#             try:
#                 label, aircraft_info = lookup(icao_hex)

#                 if aircraft_info:

#                     record["registration"]     = aircraft_info.get("registration")
#                     record["manufacturername"] = aircraft_info.get("manufacturername")
#                     record["model"]            = aircraft_info.get("model")
#                     record["serialnumber"]     = aircraft_info.get("serialnumber")
#                     record["linenumber"]       = aircraft_info.get("linenumber")
#                     record["operator"]         = aircraft_info.get("operator")
#                     record["operatorcallsign"] = aircraft_info.get("operatorcallsign")
#                     record["operatoricao"]     = aircraft_info.get("operatoricao")
#                     record["owner"]            = aircraft_info.get("owner")
#                     record["built"]            = aircraft_info.get("built")
#                     record["status"]           = aircraft_info.get("status")
#                     record["registered"]       = aircraft_info.get("registered")
#                     record["typecode_db"]      = aircraft_info.get("typecode")

#                     print(f"[DB] {icao_hex} → {label}")

#                 else:
#                     print(f"[DB] No aircraft match for ICAO {icao_hex}")

#             except Exception as e:
#                 print(f"[DB] Lookup error: {e}")        

#     except Exception as e:
#         record["message_type"] = f"DECODE_ERROR: {e}"

#     # ── write atomically so the watcher never reads a half-written file ──
#     out_path = os.path.join(OUTPUT_DIR, f"{shift_index}.json")
#     tmp_path = out_path + ".tmp"
#     with open(tmp_path, "w") as f:
#         json.dump(record, f, indent=2)
#     os.replace(tmp_path, out_path)          # atomic on Linux & Windows
#     print(f"  [export] → {out_path}  ICAO:{record['icao']}  type:{record['message_type']}")


# def _snr(index, magnitude):
#     """Same formula as SNR_Calculation() in this file."""
#     sig   = magnitude[index: index + 224]
#     noise = magnitude[max(0, index - 225): max(0, index - 1)]
#     if len(sig) < 10 or len(noise) < 10:
#         return None
#     sp = (sum(sig)   ** 2) / len(sig)
#     np_ = (sum(noise) ** 2) / len(noise)
#     if np_ <= 0:
#         return None
#     return round(10 * math.log10(sp / np_), 2)


# ──────────────────────────────────────────────────────────────────────────
#  ORIGINAL SignalVisualizer CODE (unchanged below this line)
# ──────────────────────────────────────────────────────────────────────────

condition = True
while condition:
    s=0
    print("=====================>>>>>>>><<<<<<<==================")
    print("\nWelcome to ADS-B Visualizer >>>")
    print("\nPress 0 to exit ")
    
    NSamples = int(input("Enter the number of samples in plot : 20,100,2000 :"))*2
    timeOfPlot = (NSamples/2)*0.5
    SliceN = input(f"Select the slice you want to visulaulize by entering the X multiple integer of the {timeOfPlot} micro sec: ")

    if int(SliceN)==0:
        break
    if NSamples<= 50:
        scaler=1
    elif NSamples> 50 and NSamples<200:
        scaler=2
    elif NSamples>= 200 and NSamples<1000:
        scaler=50
    else:
        scaler = 100
        
    BinaryFile = "captures/capture_Stah1090MHZ.bin"

    start_byte = 0

    with open(BinaryFile, "rb") as f:
        start_byte= (NSamples)*(int(SliceN)-1)
        f.seek(start_byte)
        		 	
        chunk = f.read(NSamples)
        I = []
        Q = []
        Magnitude = []
        DC_Shift = 0.7
        def GetMagnitude(I,Q): 
            mag = math.sqrt(I*I + Q*Q)
            return round(mag, 2)
        
        for i in range(0,NSamples):
            if (i%2)==0 :
                I.append(chunk[i]-127.5)
                if i==2:
                        Magnitude.append(GetMagnitude(I[0],Q[0])- DC_Shift)
                elif i>3:
                    k = int((i/2)-1)
                    Magnitude.append(GetMagnitude(I[k],Q[k])- DC_Shift)
            else:
                Q.append(chunk[i]-127.5)

    preamble = np.zeros(26)
    PeaksIndex = [0,2,7,9,16,19,21,23,24]
    
    f = []
    for r in range(0,26):
        for indx in PeaksIndex:
            a = r==int(indx)
            f.append(a)
            if len(f)==len(PeaksIndex):
                if sum(f)==1:
                    preamble[r]=1
                    f=[]
                else:
                    preamble[r] = 0
                    f=[]

    Pcounter=0
    PreambleStart = []
    limit = int(NSamples/2)-17
    lock = threading.Lock()
    Pcounter=0
    PreambleStart = []
    
    signal = Magnitude[0:int(NSamples/2)]

    # CRITERION 1
    CorrelationValues = np.correlate(signal, preamble, mode= "valid")
    Static_Ratios = []
    Threshold = 8
    ExceedThreshold ={}
    for maximum in range(20,len(CorrelationValues)):
        Static_Ratio = 0
        valleyAvg = 0.2*(CorrelationValues[maximum-6]+CorrelationValues[maximum-11]+
            CorrelationValues[maximum-13]+CorrelationValues[maximum-18]+CorrelationValues[maximum-20])
        PeakValue = CorrelationValues[maximum]
        Static_Ratio = PeakValue/valleyAvg
        Static_Ratios.append(Static_Ratio)
        if Static_Ratio>Threshold:
            if ExceedThreshold:
                if maximum-list(ExceedThreshold)[-1] < 240 :
                    if Static_Ratio>list(ExceedThreshold.values())[-1]:
                        ExceedThreshold.popitem()
                        ExceedThreshold[maximum] = Static_Ratio
                else:    
                        ExceedThreshold[maximum] = Static_Ratio 
            else :    
                ExceedThreshold[maximum] = Static_Ratio

    def Bit_Slicer(message, Msg_length=224):
        for key,value in message.items():
            decoded=[]
            for k in range(0,Msg_length,2):
                if value[k] >= value[k+1]:
                    decoded.append(1) 
                elif value[k] < value[k+1]:
                    decoded.append(0)
                else:
                    decoded[:] = "Rejected"
                    break
            message[key]="".join(map(str,decoded))

    Indices_2nd_criterion =[]
    u =[]
    Theta_2nd_criterion = {}
    Theta = {}

    # CRITERION 2
    for key, value in ExceedThreshold.items():
        e = Magnitude[key:key+26]
        ref="110010001"
        temp_theta = {}
        temp_theta[key] = e[0:4] + e[6:10] + e[-10:]
        Bit_Slicer(temp_theta, Msg_length=18)
        for k, v in temp_theta.items():   
            if v == ref:
                Theta_2nd_criterion[k] = v

    print(f"Total signals passing Criterion 2: {len(Theta_2nd_criterion)}")
    max_idx = np.argmax(CorrelationValues)
    print(f"\nCriterion 1 : {len(ExceedThreshold)} success at {list(ExceedThreshold.keys())} ")
    print(f"\nCriterion 2 : {len(Theta_2nd_criterion)} Success at {list(Theta_2nd_criterion.keys())}")

    # CRITERION 3
    ThetaD ={}
    h=[]
    Thershold3 = 6.656
    ThetaD_3rd_criterion = {}
    for index in Theta_2nd_criterion.keys():
        k=0
        Initial_Magnitudes = Magnitude[index:index+26]
        k = [Initial_Magnitudes[0],Initial_Magnitudes[2],Initial_Magnitudes[7],Initial_Magnitudes[9]
        ,Initial_Magnitudes[16],Initial_Magnitudes[19],Initial_Magnitudes[21],Initial_Magnitudes[23],Initial_Magnitudes[24]]
        ThetaD[index] = k
        PowerRatio = max(k)/min(k)
        if PowerRatio<Thershold3 :
            ThetaD_3rd_criterion[index] = PowerRatio 
            h.append(index)
    print(f"\ncriterion 3 : {len(ThetaD_3rd_criterion)} success , shifts {list(ThetaD_3rd_criterion.keys())}")

    # CRITERION 4
    Crit4 = {}
    Success_4th_criterion = {}
    for index in ThetaD_3rd_criterion.keys():
        Initial_Magnitudes= Magnitude[index:index+26]   
        Pulses = [Initial_Magnitudes[0],Initial_Magnitudes[2],Initial_Magnitudes[7],Initial_Magnitudes[9]
        ,Initial_Magnitudes[16],Initial_Magnitudes[19],Initial_Magnitudes[21],Initial_Magnitudes[23],Initial_Magnitudes[24]]
        sigma = sum(Pulses)/len(Pulses)        
        X =  [Initial_Magnitudes[4],Initial_Magnitudes[5]]+ Initial_Magnitudes[10:16]
        for r in range(0,8,2):
            if (X[r] and X[r+1]) <=(sigma/2):
                Crit4[int(r/2)] = "Empty"
        if len(Crit4)>=2:
            Success_4th_criterion[index] = len(Crit4)
    print(f"\ncriterion 4 : {len(Success_4th_criterion)} success , shifts {list(Success_4th_criterion.keys())}")

    msg ={}
    for start in Success_4th_criterion.keys():
            msg[start]= Magnitude[start + 16:start+ 240]

    def Decoding(binmsg):
        for key, value in binmsg.items():
            print(f"\n{'='*50}")
            print(f"REPORT FOR INDEX: {key}")
            
            try:
                bin_str = str(value)
                hex_msg = pms.util.bin2hex(bin_str)
                decoded = pms.decode(hex_msg)
                is_valid = decoded.get("crc_valid", False)
                tc = decoded.get("typecode")
                icao = decoded.get("icao")

                print(f"Hex Message:  {hex_msg}")
                print(f"CRC Result:   {'Valid' if is_valid else 'Corrupted'}")
                print(f"ICAO Address: {icao}")
                print(f"Typecode:     {tc}")
                print(f"{'-'*50}")

                if not is_valid or tc is None:
                    print("Skipping detailed parse (Invalid CRC or Unknown Typecode).")
                    # ── export even invalid frames so the watcher sees them ──
                    export_message(                                  # ← NEW
                        key, bin_str, Magnitude,                    # ← NEW
                        capture_file=BinaryFile,                    # ← NEW
                        start_byte=start_byte,                      # ← NEW
                        c1_ratio=ExceedThreshold.get(key),          # ← NEW
                        c3_power_ratio=ThetaD_3rd_criterion.get(key), # ← NEW
                        c4_null_count=Success_4th_criterion.get(key)  # ← NEW
                    )                                               # ← NEW
                    continue

                # IDENTIFICATION (Typecodes 1-4)
                if 1 <= tc <= 4:
                    print(f"[IDENTIFICATION]")
                    print(f"Callsign: {decoded.get('callsign', 'N/A')}")

                # SURFACE POSITION (Typecodes 5-8)
                elif 5 <= tc <= 8:
                    print(f"[SURFACE POSITION]")
                    gs = decoded.get('groundspeed')
                    if gs is not None:
                        gs_kmh = round(gs * 1.852, 2)
                        print(f"Ground Speed: {gs} knots ({gs_kmh} km/h)")
                    lat = decoded.get('latitude')
                    lon = decoded.get('longitude')
                    if lat is not None and lon is not None:
                        print(f"Global Latitude:  {lat}")
                        print(f"Global Longitude: {lon}")
                    else:
                        if len(bin_str) >= 88:
                            raw_lat = int(bin_str[54:71], 2)
                            raw_lon = int(bin_str[71:88], 2)
                            print(f"Raw CPR Lat: {raw_lat} (Need reference to decode Global Lat)")
                            print(f"Raw CPR Lon: {raw_lon} (Need reference to decode Global Lon)")
                    cpr = decoded.get("cpr_format")
                    if cpr is None and len(bin_str) >= 54:
                        cpr = int(bin_str[53])
                    print(f"CPR Type: {'Odd' if cpr == 1 else 'Even'}")

                # AIRBORNE POSITION (Typecodes 9-18)
                elif 9 <= tc <= 18:
                    print(f"[AIRBORNE POSITION]")
                    print(f"Altitude:  {decoded.get('altitude', 'N/A')} ft")
                    lat = decoded.get('latitude')
                    lon = decoded.get('longitude')
                    if lat is not None and lon is not None:
                        print(f"Global Latitude:  {lat}")
                        print(f"Global Longitude: {lon}")
                    else:
                        if len(bin_str) >= 88:
                            raw_lat = int(bin_str[54:71], 2)
                            raw_lon = int(bin_str[71:88], 2)
                            print(f"Raw CPR Lat: {raw_lat} (Need Odd/Even Pair to decode)")
                            print(f"Raw CPR Lon: {raw_lon} (Need Odd/Even Pair to decode)")
                    cpr = decoded.get("cpr_format")
                    if cpr is None and len(bin_str) >= 54:
                        cpr = int(bin_str[53])
                    print(f"CPR Type: {'Odd' if cpr == 1 else 'Even'}")

                # AIRBORNE VELOCITY (Typecode 19)
                elif tc == 19:
                    print(f"[AIRBORNE VELOCITY]")
                    gs = decoded.get('groundspeed')
                    if gs is not None:
                        gs_kmh = round(gs * 1.852, 2)
                        print(f"Ground Speed: {gs} knots ({gs_kmh} km/h)")
                        print(f"Track Angle:  {decoded.get('track')}°")
                    airspeed = decoded.get('airspeed')
                    if airspeed is not None:
                        as_kmh = round(airspeed * 1.852, 2)
                        print(f"Air Speed:    {airspeed} knots ({as_kmh} km/h)")
                        print(f"Heading:      {decoded.get('heading')}°")
                    vrate_fpm = decoded.get('vertical_rate')
                    if vrate_fpm is not None:
                        vrate_km_min = round((vrate_fpm * 0.3048) / 1000, 4)
                        vrate_ms = round((vrate_fpm * 0.3048) / 60, 2)
                        status = "Climbing" if vrate_fpm > 0 else "Descending"
                        print(f"Vertical Rate: {vrate_fpm} fpm ({status})")
                        print(f"            -> {abs(vrate_km_min)} km/min")
                        print(f"            -> {abs(vrate_ms)} m/s")

                # OPERATIONAL STATUS (Typecode 31)
                elif tc == 31:
                    print(f"[OPERATIONAL STATUS]")
                    print(f"Capability: {decoded.get('capability', 'N/A')}")

                # ── export to output/ folder immediately after printing ──
                export_message(                                      # ← NEW
                    key, bin_str, Magnitude,                        # ← NEW
                    capture_file=BinaryFile,                        # ← NEW
                    start_byte=start_byte,                          # ← NEW
                    c1_ratio=ExceedThreshold.get(key),              # ← NEW
                    c3_power_ratio=ThetaD_3rd_criterion.get(key),   # ← NEW
                    c4_null_count=Success_4th_criterion.get(key)    # ← NEW
                )                                                   # ← NEW

            except Exception as e:
                print(f"Detailed Error at index {key}: {e}")

    def SNR_Calculation(indices):
        for index in indices:
            l = Magnitude[index:index+224]
            x = (sum(l))*(sum(l))/224
            p = Magnitude[index-225:index-1]
            w = (sum(p))*(sum(p))/224
            n = 10*math.log10(x/w)
            print(f"\nthe SNR at {index} is {n}")

    SNR_Calculation(Indices_2nd_criterion)
    
    Bit_Slicer(msg)
    print(msg)
    Decoding(msg)    # ← export_message() is now called inside here automatically

    if limit < 2000:
        plt.style.use('_mpl-gallery')
        
        class SignalShifter:
            def __init__(self, stem_container, base_xx, base_yy):
                self.shift_amount = 0
                self.stem_container = stem_container
                self.base_xx = base_xx
                self.base_yy = base_yy
            def Update_position(self):
                new_xx = self.base_xx + self.shift_amount
                self.stem_container.markerline.set_xdata(new_xx)
                new_segments = [[[x, 0], [x, y]] for x, y in zip(new_xx, self.base_yy)]
                self.stem_container.stemlines.set_segments(new_segments)
                plt.draw()

            def Shift_by_button(self, event):
                self.shift_amount += 1
                self.Update_position()
                
            def Shift_by_TextBox(self, text):
                try:
                    self.shift_amount=int(text)
                    self.Update_position()
                except:
                    print("enter an integer")

        Samples = int(NSamples/2)-1
        x = np.arange(0, int(Samples))
        y = Magnitude

        xx = np.arange(0, 26)
        yy = np.zeros(26) 
        yy[0], yy[2], yy[7], yy[9],yy[16],yy[19],yy[21],yy[23],yy[24] = 3, 3, 3, 3, 3, 3, 3, 3, 3

        Last_index = len(CorrelationValues)
        Corr_x = range(0,Last_index)
        Corr_y = CorrelationValues

        fig2 = plt.figure(figsize=(6,4))
        cx = fig2.add_axes([0.07, 0.1, 1, 1])

        fig = plt.figure(figsize=(6, 4))
        ax = fig.add_axes([0.07, 0.1, 1, 1])

        ax.plot(x, y, label="Signal")
        line = ax.stem(xx, yy, linefmt='red', label="Preamble pulses")

        ax.set_xlabel(f"IQ SAMPLES (A sample in 0.5 micro sec) S:{int(start_byte/2)}")
        ax.set_ylabel("Magnitude ")

        ax.set(xlim=(0, Samples), xticks= scaler*np.arange(1, Samples/scaler),
               ylim=(0, 12), yticks=np.arange(1, 12))

        callback = SignalShifter(line, xx, yy)

        ax_button = plt.axes([0.04, 0.005, 0.1, 0.04])
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

    else :
        print("\n Reduce the number of Samples in plot -must be lower than 2000 - in order to VISUALIZE!")