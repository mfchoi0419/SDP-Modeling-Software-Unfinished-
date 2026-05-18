"""
run_pipeline.py

Purpose:
    End-to-end pipeline for optional data ingestion, weather backfill, model training, evaluation, and artifact saving.

Notes:
    This file is part of the Senior Design biodigester/CHP modeling software.
    Comments were added to make the repository easier to review on GitHub.
"""

from __future__ import annotations

from pathlib import Path
import argparse
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

from ingest import ingest
from forecast_ingest import append_forecast_to_db
from open_meteo_history_ingest import backfill_weather_history_from_open_meteo
from evaluate_model_health import evaluate_heat_loss_model
from data_loader import (
    load_heat_loss_forecast_labeled_dataframe,
    load_heat_loss_history_labeled_dataframe,
    add_heat_loss_lag_features,
)

recency_weighting_enabled = True
recency_half_life_days = 60.0
recency_w_max = 4.0
recency_w_min = 1.0
min_forecast_rows = 30

@dataclass
class PipelineParams:
    db_path: str = "Data/biodigester.db"
    start_date: str = "2020-01-01"
    horizon_days: int = 1

    test_size: float = 0.2
    n_estimators: int = 300
    random_state: int = 42
    max_depth: int | None = None
    n_recent_days_eval: int = 60
    
def _setup_run_dir(base: Path) -> Path:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = base / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir

def _setup_logging(run_dir: Path) -> None:
    log_path = run_dir / "run.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler()],
    )

def make_recency_weights(dates, half_life_days=60.0, w_min=1.0, w_max=4.0) -> np.ndarray:
    d = pd.to_datetime(dates).dt.tz_localize(None)
    newest = d.max()
    age_days = (newest - d).dt.days.clip(lower=0).astype(float)
    raw = 2.0 ** (-age_days / float(half_life_days))
    weights = w_min + (w_max - w_min) * raw
    return weights.to_numpy()

def main() -> None:
    # Command-line arguments make the pipeline flexible without editing source code.
    parser = argparse.ArgumentParser(description="SDP clean pipeline runner")

    # ingestion (optional)
    parser.add_argument("--ingest-source", default=None, help="Optional:source name from sources.json")
    parser.add_argument("--ingest-file", default=None, help="Optional: path to input CSV/XLSX")
    
    # forecast fetching (optional)
    parser.add_argument("--fetch-forecast", action="store_true", help="Fetch forecast and append to DB")
    parser.add_argument("--forecast-days", type=int, default=7, help="Daily forecast horizon (1...16)")
    parser.add_argument("--lat", type=float, default=42.39135, help="Forecast latitude (default Amherst area)")
    parser.add_argument("--lon", type=float, default=-72.52327, help="Forecast longitude (default Amherst area)")

    # training mode preference
    parser.add_argument("--mode", choices=["noaa", "forecast"], default="noaa", help="noaa = observed_history + lags, forecast = forecast features -> actual label")
    
    # gating
    parser.add_argument("--gate", action="store_true", help="If set, only promote model if it beats baseline")
    
    args = parser.parse_args()
    params = PipelineParams()

    run_dir = _setup_run_dir(Path("artifacts"))
    _setup_logging(run_dir)

    logging.info("Run dir: %s", run_dir)
    (run_dir / "params.json").write_text(json.dumps(asdict(params),indent=2))

    # 1. ingest (optional)
    if args.ingest_source and args.ingest_file:
        logging.info("Ingesting source=%s file=%s", args.ingest_source, args.ingest_file)
        ingest(args.ingest_source, args.ingest_file)
    else:
        logging.info("Skipping ingestion")

    # 2. fetch (optional)
    if args.fetch_forecast:
        logging.info("Fetching forecast: days=%d, lat=%.5f, lon=%.5f", args.forecast_days,
                     args.lat, args.lon)
        out = append_forecast_to_db(
            db_path=params.db_path,
            lat=args.lat,
            lon=args.lon,
            days=args.forecast_days,
        )
        if out.status == "ok":
            logging.info("Forecast appended: issued_at=%s, n_rows=%d", out.issued_at, out.n_rows)
        else:
            logging.warning("Forecast fetch failed: %s", out.reason)
    else:
        logging.info("Skipping forecast fetch")

    # 3. backfill observed actuals
    logging.info("Backfilling weather_history from Open_meteo archive (through yesterday)")
    hist = backfill_weather_history_from_open_meteo(
        db_path = params.db_path,
        lat = args.lat,
        lon = args.lon,
    )
    if hist.status == "ok":
        logging.info("Backfill ok: inserted/updated %d rows (%s..%s)", hist.n_rows, hist.start_date, hist.end_date)
    else:
        logging.warning("Backfill failed: %s", hist.reason)

    # 4. Load dataset
    chosen_mode = args.mode

    if chosen_mode == "forecast":
        df_f = load_heat_loss_forecast_labeled_dataframe(
            db_path=Path(params.db_path),
            start_date=params.start_date,
            horizon_days=params.horizon_days,
        )
        if df_f is None or df_f.empty or len(df_f) < min_forecast_rows:
            logging.warning(
                "Forecast-labeled dataset too small (n=%d). Falling back to NOAA mode.",
                0 if df_f is None else len(df_f),
            )
            chosen_mode = "noaa"
        else:
            df = df_f
            feature_columns = ["temp_min_c", "temp_max_c", "temp_avg_c"]
            weight_date_col = "issued_date"

    if chosen_mode == "noaa":
        df = load_heat_loss_history_labeled_dataframe(
            db_path=Path(params.db_path),
            start_date=params.start_date,
            horizon_days=params.horizon_days,
        )
        df = add_heat_loss_lag_features(df)

        feature_columns = [
            "ambient_c",
            "digester_c",
            "delta_setpoint_ambient_f",
            "heat_loss_w_lag1",
            "heat_loss_w_lag2",
            "heat_loss_w_3day_mean",
            "ambient_c_lag1",
            "digester_c_lag1",
        ]
        weight_date_col = "date"
    
    if df is None or df.empty:
        raise RuntimeError("No rows loaded after training mode selection")
    
    df = df.dropna(subset=feature_columns + ["target"])
    if df.empty:
        raise RuntimeError("No usable rows after dropna")
    
    logging.info("Mode=%s usable rows=%d", args.mode, len(df))


    # 5. Time split 80/20. shuffle=False preserves chronological order, which is important for forecasting.
    X = df[feature_columns]
    y = df["target"].to_numpy()
    dates_for_weighting = df[weight_date_col]

    X_train, X_test, y_train, y_test, d_train, d_test = train_test_split(
        X, y,dates_for_weighting, test_size=params.test_size, shuffle=False
    )

    # 6. Recency weighting 
    sample_weight = None
    if recency_weighting_enabled:
        sample_weight = make_recency_weights(
            d_train,
            half_life_days=recency_half_life_days,
            w_min=recency_w_min,
            w_max=recency_w_max,
        )
        logging.info(
            "Recency weighting enabled: half_life_days=%.1f w_min=%.2f w_max=%.2f",
            recency_half_life_days, recency_w_min, recency_w_max
        )

    # 7. Training. Random Forest is used because it can model nonlinear weather/heat-loss relationships.
    model = RandomForestRegressor(
        n_estimators=params.n_estimators,
        random_state=params.random_state,
        max_depth=params.max_depth,
        n_jobs=-1
    )
    model.fit(X_train, y_train, sample_weight=sample_weight)
    logging.info("Model trained")

    model_payload = {
        "model": model,
        "feature_cols": feature_columns,
        "trained_at": datetime.now().isoformat(),
        "params": asdict(params),
        "mode": chosen_mode,
        "target_name": "heat_loss_w",
        "heat_loss_model": {
            "Volume_m3": 6.0,
            "AssumedDiameter_m": 3.0,
            "SetpointF": 95.0,
            "R_shell": 14.0,
            "R_ground": 14.0,
            "R_film_in": 0.68,
            "R_film_out_air": 0.17,
            "R_film_out_ground": 0.0,
            "GroundTempF": 50.0,
        },
    }

    model_path = run_dir / "weather_model.pkl"
    joblib.dump(model_payload, model_path)
    logging.info("Model saved to %s", model_path)

    # 8. Evaluate (NOAA-based currently)
    metrics = evaluate_heat_loss_model(
        model_path=model_path,
        db_path=params.db_path,
        start_date=params.start_date,
        n_recent_days=params.n_recent_days_eval
    )

    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    logging.info("Saved metrics to %s", run_dir / "metrics.json")

    if metrics.get("status") == "ok":
        logging.info(
            "Eval: RMSE=%.3f (baseline %.3f), MAE=%.3f (baseline %.3f), R2=%.3f",
            metrics["rmse"], metrics["baseline_rmse"],
            metrics["mae"], metrics["baseline_mae"],
            metrics["r2"]
        )
    else:
        logging.warning("Evaluation failed: %s", metrics)
    
    # 9. Gate/promote
    if args.gate and metrics.get("status") == "ok":
        if metrics["beats_baseline_rmse"] and metrics["beats_baseline_mae"]:
            best_path = Path("best_model.pkl")
            joblib.dump(model_payload, best_path)
            logging.info("Promoted model to %s (beats baseline)", best_path)
        else:
            logging.info("Model not promoted (does not beat baseline)")

if __name__ == "__main__":
    main()