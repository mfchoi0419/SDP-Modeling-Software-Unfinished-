"""
read_ambient_temp.py

Purpose:
    Reads one ambient temperature value from Arduino serial output and appends a daily CSV record.

Notes:
    This file is part of the Senior Design biodigester/CHP modeling software.
    Comments were added to make the repository easier to review on GitHub.
"""

import serial
import time
import csv
import datetime
from pathlib import Path

SERIAL_PORT = "/dev/tty.usbmodem1101"
BAUD_RATE = 9600
READ_TIMEOUT_SECONDS = 15

DATA_PATH = Path("Data/Biodigester_daily_data.csv")

def read_one_temperature():
    with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as ser:
        print(f"Opened serial port {SERIAL_PORT} at {BAUD_RATE} baud.")
        start_time = time.time()
        last_temp = None
        
        while time.time() - start_time < READ_TIMEOUT_SECONDS:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            print("Received:", line)

            if line.startswith("TEMP_C:"):
                try:
                    temp_str = line.split("TEMP_C:")[1]
                    temp_c = float(temp_str)
                    last_temp = temp_c
                    print(f"Ambient temperature: {temp_c:.2f} °C")
                    return temp_c
                except ValueError:
                    continue
        print("No TEMP_C reading received within timeout.")
        return last_temp
    
def append_daily_row_to_central_csv(
        date_str,
        digester_T_min_today,
        digester_T_max_today,
        ambient_T_avg_today,
        CHP_runtime_today,
        biogas_prod_today,
        solar_rad_today,
        digester_T_min_tomorrow="",
):
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    file_exists = DATA_PATH.exists()

    row = {
        "date": date_str,
        "digester_T_min_today": digester_T_min_today,
        "digester_T_max_today": digester_T_max_today,
        "ambient_T_avg_today": ambient_T_avg_today,
        "CHP_runtime_today": CHP_runtime_today,
        "biogas_prod_today": biogas_prod_today,
        "solar_rad_today": solar_rad_today,
        "digester_T_min_tomorrow": digester_T_min_tomorrow,
    }

    with DATA_PATH.open(mode="a",newline="") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    print(f"\nSaved row to {DATA_PATH}")

def log_daily_data():
    print("=== Log one day of biodigester data (ambient from Arduino) ===")
    date_str = input("Date (YYYY-MM-DD) [today]: ").strip()
    if not date_str:
        date_str = datetime.date.today().isoformat()
    
    ambient_T_avg_today = read_one_temperature()
    if ambient_T_avg_today is None:
        print("Warning: no ambient temperature received; using 0.0 as a placeholder.")
        ambient_T_avg_today = 0.0
    digester_T_min_today = float(input("Digester MIN temp today (°C): "))
    digester_T_max_today = float(input("Digester MAX temp today (°C): "))
    CHP_runtime_today = float(input("CHP runtime today (hours): "))
    biogas_prod_today = float(input("Biogas production today (m³): "))
    solar_rad_today = float(input("Solar radiation today (MJ/m²): "))

    digester_T_min_tomorrow_str = input("Digester MIN temp tomorrow (°C) [optional]: ").strip()

    if digester_T_min_tomorrow_str == "":
        digester_T_min_tomorrow = ""
    else:
        digester_T_min_tomorrow = float(digester_T_min_tomorrow_str)

    append_daily_row_to_central_csv(
        date_str=date_str,
        digester_T_min_today=digester_T_min_today,
        digester_T_max_today=digester_T_max_today,
        ambient_T_avg_today=ambient_T_avg_today,
        CHP_runtime_today=CHP_runtime_today,
        biogas_prod_today=biogas_prod_today,
        solar_rad_today=solar_rad_today,
        digester_T_min_tomorrow=digester_T_min_tomorrow,
    )

if __name__ == "__main__":
    log_daily_data()