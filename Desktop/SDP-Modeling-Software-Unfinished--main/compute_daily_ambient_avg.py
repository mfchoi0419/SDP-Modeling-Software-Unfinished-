"""
compute_daily_ambient_avg.py

Purpose:
    Reads raw ambient temperature logs and summarizes them into daily averages for the biodigester model.

Notes:
    This file is part of the Senior Design biodigester/CHP modeling software.
    Comments were added to make the repository easier to review on GitHub.
"""

import pandas as pd

INPUT_FILE = "ambient_log.csv"
OUTPUT_FILE = "daily_ambient_avg.csv"

def main():
    try:
        df = pd.read_csv(INPUT_FILE,
        header=None,
        names=["timestamp", "temperature_c"]
        )
    except FileNotFoundError:
        print(f"Error: {INPUT_FILE} not found.")
        return
    
    # Convert timestamp strings into pandas datetime values so rows can be grouped by calendar date.
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])
    df["date"] = df["timestamp"].dt.date

    daily = (
        df.groupby("date")["temperature_c"]
        .mean()
        .reset_index()
        .rename(columns={"temperature_c": "ambient_T_avg_today"})
    )

    daily.to_csv(OUTPUT_FILE, index=False)
    print(f"Daily averages written to {OUTPUT_FILE}")
    print(daily)

if __name__ == "__main__":
        main()
