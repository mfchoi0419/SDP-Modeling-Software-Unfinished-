"""
Initializers/add_heat_label.py

Purpose:
    Adds a binary needs_heat_tomorrow label to the daily CSV using a temperature threshold.

Notes:
    This file is part of the Senior Design biodigester/CHP modeling software.
    Comments were added to make the repository easier to review on GitHub.
"""

import pandas as pd
from pathlib import Path

THRESHOLD_TEMP = 35.0

DATA_PATH = Path("Data/Biodigester_daily_data.csv")

print(f"Loading data from:  {DATA_PATH.resolve()}")

if not DATA_PATH.exists():
    raise FileNotFoundError(f"Could not find {DATA_PATH}. Check the path and filename.")

data = pd.read_csv(DATA_PATH)

print("Columns BEFORE:", list(data.columns))

if "digester_T_min_tomorrow" not in data.columns:
    raise ValueError("Column 'digester_T_min_tomorrow' not found in CSV. " "Check your header row in biodigester_daily_data.csv")


data["needs_heat_tomorrow"] = (data["digester_T_min_tomorrow"] < THRESHOLD_TEMP).astype(int)

print("Columns AFTER:", list(data.columns))

data.to_csv(DATA_PATH, index=False)

print(f"Updated file saved to: {DATA_PATH.resolve()}")
