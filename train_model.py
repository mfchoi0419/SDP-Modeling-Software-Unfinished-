"""
train_model.py

Purpose:
    Trains a Random Forest temperature model using historical NOAA weather data from SQLite.

Notes:
    This file is part of the Senior Design biodigester/CHP modeling software.
    Comments were added to make the repository easier to review on GitHub.
"""

import sqlite3
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
import joblib
from data_loader import load_noaa_labeled_dataframe, add_noaa_lag_features



DB_PATH = Path("Data/biodigester.db")
MODEL_OUT = "digester_temp_model_noaa_only.pkl"
MIN_ROWS = 10

def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"DB not found: {DB_PATH.resolve()}")
    
    df = load_noaa_labeled_dataframe(
        DB_PATH,
        start_date="2020-01-01",
        target_field="temp_avg_c",
        horizon_days=1
    )
    print("Columns:", df.columns.tolist())
    print("Rows returned from label query:", len(df))

    if len(df) == 0:
        raise RuntimeError("no weather rows found in weather_history for the requested date range.")
    
    df = add_noaa_lag_features(df)

    feature_columns = [
        "temp_min_c",
        "temp_max_c",
        "temp_avg_c",
        "temp_avg_c_lag1",
        "temp_avg_c_lag2",
        "temp_avg_c_3day_mean"
    ]

    df = df.dropna(subset=feature_columns + ["target"])
    print("Rows after lag/dropna:", len(df))

    if len(df) < MIN_ROWS:
        raise RuntimeError(f"Not enough usable rows to train after lag features ({len(df)} rows.)\n"
                           f"Collect more days or temporarily remove lag features.\n"
                           f"Tip: set MIN_ROWS lower or comment out lag features.")
    
    X = df[feature_columns]
    y = df["target"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
    model = RandomForestRegressor(n_estimators=300, random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred) if len(y_test) >= 2 else float("nan")

    print(f"MAE: {mae:.2f} °C")
    print(f"R²: {r2:.3f}")

    joblib.dump(model, MODEL_OUT)
    print(f"Model saved to {MODEL_OUT}")

if __name__ == "__main__":
    main()