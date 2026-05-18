"""
run_controller.py

Purpose:
    Loads trained models, estimates whether heat is needed, and sends a CHP runtime command over serial.

Notes:
    This file is part of the Senior Design biodigester/CHP modeling software.
    Comments were added to make the repository easier to review on GitHub.
"""

import pandas as pd
import joblib
import serial
import time

CLASSIFIER_PATH = "heat_classifier_model.pkl"
MODEL_PATH = 'digester_temp_model.pkl'

THRESHOLD_TEMP = 35.0
TEMP_GAIN = 1.5
BAUD_RATE = 9600

SERIAL_PORT = '/dev/tty.usbmodem1101'

def compute_required_runtime(predicted_min_temp, threshold=THRESHOLD_TEMP, gain=TEMP_GAIN):
    temp_deficit = threshold - predicted_min_temp
    if temp_deficit <= 0:
        return 0.0
    hours_needed = temp_deficit / gain
    return max(0.0, hours_needed)

def main():
    clf = joblib.load(CLASSIFIER_PATH)
    model = joblib.load(MODEL_PATH)

    today_data = pd.read_csv("Todays_features.csv")
    
    clf_cols = ["ambient_T_avg_today"]
    model_cols = ["digester_T_min_today",
            "digester_T_avg_today",
            "ambient_T_avg_today",
            "CHP_runtime_today",
            "biogas_prod_today",
            "solar_rad_today",
    ]
    
    X_today = today_data[model_cols]
    X_clf = today_data[clf_cols]

    proba = clf.predict_proba(X_clf)[0][1]
    needs_heat_pred = proba >= 0.5
    
    print(f"Predicted probability of needing heat: {proba:.2f}")
    
    if not needs_heat_pred:
        print("Classifier says NO heat needed. Exiting without running CHP.")
        return
    
    print("Classifier says heat IS needed. Computing runtime...")

    predicted_min_temp = model.predict(X_today)[0]
    print(f"Predicted minimum digester temp tomorrow: {predicted_min_temp:.2f} °C")

    runtime_hours = compute_required_runtime(predicted_min_temp)
    runtime_seconds = int(runtime_hours * 3600)

    if runtime_seconds <= 0:
        print("No CHP runtime needed.")
        return
    
    print(f"Commanding CHP runtime: {runtime_hours:.2f} hours ({runtime_seconds} seconds)")

    try:
        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2) as ser:
            command = f"{runtime_seconds}\n"
            ser.write(command.encode("utf-8"))
            time.sleep(0.5)

            if ser.in_waiting:
                response = ser.readline().decode("utf-8", errors="ignore").strip()
                print("Arduino response:", response)

    except Exception as e:
        print("Error talking to Arduino:", e)

if __name__ == "__main__":
    main()

