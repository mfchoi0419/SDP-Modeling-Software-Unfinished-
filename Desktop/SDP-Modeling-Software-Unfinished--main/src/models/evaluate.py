"""
evaluate_model_health.py

Purpose:
    Evaluates a saved heat-loss model against recent labeled forecast/history rows and a persistence baseline.

Notes:
    This file is part of the Senior Design biodigester/CHP modeling software.
    Comments were added to make the repository easier to review on GitHub.
"""

from __future__ import annotations

from pathlib import Path
import joblib
import numpy as np

from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from data_loader import load_heat_loss_forecast_labeled_dataframe, add_heat_loss_lag_features

default_feature_cols = [
    "ambient_c",
    "digester_c",
    "delta_setpoint_ambient_f",
    "heat_loss_w_lag1",
    "heat_loss_w_lag2",
    "heat_loss_w_3day_mean",
    "ambient_c_lag1",
    "digester_c_lag1",
]

def evaluate_heat_loss_model(
        model_path: str | Path,
        db_path: str | Path,
        start_date: str = "2020-01-01",
        horizon_days: int = 1,
        n_recent_days: int = 60,
) -> dict:
    df = load_heat_loss_forecast_labeled_dataframe(
        Path(db_path),
        start_date=start_date,
        horizon_days=horizon_days
    )
    df = add_heat_loss_lag_features(df)

    payload = joblib.load(model_path)
    model = payload["model"] if isinstance(payload, dict) and "model" in payload else payload
    feature_cols = payload.get("feature_cols", default_feature_cols) if isinstance(payload, dict) else default_feature_cols

    df = df.dropna(subset=feature_cols + ["target", "heat_loss_w"])
    if df.empty:
        return {"status": "error", "reason": "no_usable_rows_after_dropna"}
    
    recent = df.tail(n_recent_days)
    if len(recent) < 5:
        return {"status": "error", "reason": "not_enough_recent_rows", "n_rows_eval": int(len(recent))}
    
    X = recent[feature_cols]
    y_true = recent["target"].to_numpy()
    y_pred = model.predict(X)

    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = float(r2_score(y_true, y_pred))

    baseline_pred = recent["heat_loss_w"].to_numpy()
    baseline_mae = float(mean_absolute_error(y_true, baseline_pred))
    baseline_rmse = float(np.sqrt(mean_squared_error(y_true, baseline_pred)))

    return {
        "status": "ok",
        "n_rows_eval": int(len(recent)),
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
        "baseline_mae": baseline_mae,
        "baseline_rmse": baseline_rmse,
        "beats_baseline_rmse": rmse < baseline_rmse,
        "beats_baseline_mae": mae < baseline_mae,
    }