"""
data_loader.py

Purpose:
    Shared feature engineering and SQLite loading utilities for heat-loss and NOAA weather models.

Notes:
    This file is part of the Senior Design biodigester/CHP modeling software.
    Comments were added to make the repository easier to review on GitHub.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd

volume_m3 = 6.0
assumed_diameter_m = 3.0

setpoint_f = 95.0

R_shell = 14.0
R_ground = 14.0

R_film_in = 0.68
R_film_out_air = 0.17
R_film_out_ground = 0.00

ground_temp_f = 50.0

m_to_ft = 3.280839895
btu_per_hr_to_w = 0.29307107
btu_per_day_to_w = btu_per_hr_to_w / 24.0

# Tank geometry and heat-transfer helper functions are separated from SQL loading
# so the same assumptions are reused during training and evaluation.
def tank_geometry_areas_ft2(volume_m3: float = volume_m3, 
diameter_m: float = assumed_diameter_m) -> dict:
    V = float(volume_m3)
    D = float(diameter_m)
    H = V / (np.pi * (D / 2.0) ** 2)

    A_side_m2 = np.pi * D * H
    A_top_m2 = np.pi * (D / 2.0) ** 2
    A_bottom_m2 = A_top_m2

    A_side_ft2 = A_side_m2 * (m_to_ft ** 2)
    A_top_ft2 = A_top_m2 * (m_to_ft ** 2)
    A_bottom_ft2 = A_bottom_m2 * (m_to_ft ** 2)

    A_total = A_side_ft2 + A_top_ft2 + A_bottom_ft2
    A_ground = A_bottom_ft2
    A_air = max(A_total - A_ground, 0.0)

    return {
        "A_side_ft2": A_side_ft2,
        "A_top_ft2": A_top_ft2,
        "A_bottom_ft2": A_bottom_ft2,
        "A_total_ft2": A_total,
        "A_air_ft2": A_air,
        "A_ground_ft2": A_ground,
        "H_m": H,
    }

def c_to_f(x: pd.Series) -> pd.Series:
    return (x * 9.0 / 5.0) + 32.0

def heat_loss_w_daily(
        digester_c: pd.Series,
        ambient_c: pd.Series,
        setpoint_f: float = setpoint_f,
        ground_temp_f: float = ground_temp_f
) -> pd.Series:
    areas = tank_geometry_areas_ft2()
    A_air = areas["A_air_ft2"]
    A_ground = areas["A_ground_ft2"]

    U_air = 1.0 / (R_film_in + R_shell + R_film_out_air)
    U_ground = 1.0 / (R_film_in + R_ground + R_film_out_ground)

    TambF = c_to_f(ambient_c)

    dT_air = (setpoint_f - TambF).clip(lower=0.0)
    dT_ground = pd.Series(setpoint_f - float(ground_temp_f), index=dT_air.index).clip(lower=0.0)

    Qday_air_btu = 24.0 * U_air * A_air * dT_air
    Qday_ground_btu = 24.0 * U_ground * A_ground * dT_ground

    Qday_total_btu = Qday_air_btu + Qday_ground_btu

    Q_watts = Qday_total_btu * btu_per_day_to_w
    return Q_watts

def add_noaa_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add lagged NOAA weather features for next-day weather prediction.

    These features allow the model to use the recent temperature trend instead of
    only the current day's min/max/average temperature values.
    """
    df = df.sort_values("date").reset_index(drop=True).copy()
    df["temp_avg_c_lag1"] = df["temp_avg_c"].shift(1)
    df["temp_avg_c_lag2"] = df["temp_avg_c"].shift(2)
    df["temp_avg_c_3day_mean"] = df["temp_avg_c"].rolling(3).mean()
    return df


def load_noaa_labeled_dataframe(
    db_path: Path,
    start_date: str = "2020-01-01",
    target_field: str = "temp_avg_c",
    horizon_days: int = 1,
    weather_table: str = "weather_history",
) -> pd.DataFrame:
    """Load historical weather rows and create a future target column.

    target is shifted upward by horizon_days, so each row's features are used to
    predict the selected weather field on a future day.
    """
    query = f"""
    SELECT
      date(substr(date, 1, 10)) AS date,
      temp_min_c,
      temp_max_c,
      COALESCE(temp_avg_c, (temp_min_c + temp_max_c) / 2.0) AS temp_avg_c
    FROM {weather_table}
    WHERE date(substr(date, 1, 10)) >= date(?)
    ORDER BY date(substr(date, 1, 10));
    """
    with sqlite3.connect(str(db_path)) as conn:
        df = pd.read_sql_query(query, conn, params=[start_date])

    if df.empty:
        return df

    df = df.sort_values("date").reset_index(drop=True)
    df["target"] = df[target_field].shift(-horizon_days)
    return df


def add_heat_loss_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("date").reset_index(drop=True)

    df["heat_loss_w_lag1"] = df["heat_loss_w"].shift(1)
    df["heat_loss_w_lag2"] = df["heat_loss_w"].shift(2)
    df["heat_loss_w_3day_mean"] = df["heat_loss_w"].rolling(3).mean()

    df["ambient_c_lag1"] = df["ambient_c"].shift(1)
    df["digester_c_lag1"] = df["digester_c"].shift(1)

    df["delta_setpoint_ambient_f"] = (setpoint_f - c_to_f(df["ambient_c"])).clip(lower=0.0)

    return df

def load_heat_loss_history_labeled_dataframe(
        db_path: Path,
        start_date: str = "2020-01-01",
        horizon_days: int = 1,
        weather_table: str = "weather_history",
        daily_table: str = "daily_data",
        digester_temp_col: str = "digester_temp_c",
) -> pd.DataFrame:
    query = f"""
    SELECT
      date(substr(w.date, 1, 10)) AS date,
      COALESCE(w.temp_avg_c, (w.temp_min_c + w.temp_max_c) / 2.0) AS ambient_c,
      d.{digester_temp_col} AS digester_c
    FROM {weather_table} w
    JOIN {daily_table} d
      ON date(substr(d.date, 1, 10)) = date(substr(w.date, 1, 10))
    WHERE date(substr(w.date, 1, 10)) >= date(?)
    ORDER BY date(substr(w.date, 1, 10));
    """

    with sqlite3.connect(str(db_path)) as conn:
        df = pd.read_sql_query(query, conn, params=[start_date])
    
    if df.empty:
        return df
    
    df["heat_loss_w"] = heat_loss_w_daily(df["digester_c"], df["ambient_c"])

    df = df.sort_values("date").reset_index(drop=True)
    df["target"] = df["heat_loss_w"].shift(-horizon_days)
    return df

def load_heat_loss_forecast_labeled_dataframe(
        db_path: Path,
        start_date: str = "2020-01-01",
        horizon_days: int = 1,
        weather_table: str = "weather_history",
        forecast_table: str = "weather_forecast_daily",
        daily_table: str = "daily_data",
        digester_temp_col: str = "digester_temp_c",
) -> pd.DataFrame:
    query = f"""
    WITH latest_issue AS (
      SELECT
        date(substr(issued_at, 1, 10)) AS issued_date,
        MAX(issued_at) AS issued_at
      FROM {forecast_table}
      GROUP BY date(substr(issued_at, 1, 10))
    )
    SELECT
      date(substr(f.forecast_date, 1, 10)) AS date,

      -- forecast ambient as features
      f.temp_avg_c AS forecast_ambient_c,
      f.temp_min_c AS forecast_tmin_c,
      f.temp_max_c AS forecast_tmax_c,

      -- digester temp (measured)
      d.{digester_temp_col} AS digester_c,

      -- actual ambient for label computation
      COALESCE(w.temp_avg_c, (w.temp_min_c + w.temp_max_c) / 2.0) AS actual_ambient_c,

      -- weighting/debug
      date(substr(f.issued_at, 1, 10)) AS issued_date,
      f.issued_at AS issued_at,
      f.horizon_days AS horizon_days
    
    FROM {forecast_table} f
    JOIN latest_issue li
      ON li.issued_at = f.issued_at
    JOIN {weather_table} w
      ON date(substr(w.date, 1, 10)) = date(substr(f.forecast_date, 1, 10))
    JOIN {daily_table} d
      ON date(substr(d.date, 1, 10)) = date(substr(f.forecast_date, 1, 10))
    
    WHERE date(substr(f.forecast_date, 1, 10)) >= date(?)
      AND f.horizon_days = ?
      AND date(substr(f.forecast_date, 1, 10)) <= date('now', '-1 day')
    
    ORDER BY date(substr(f.forecast_date, 1, 10));
    """

    with sqlite3.connect(str(db_path)) as conn:
        df = pd.read_sql_query(query, conn, params=[start_date, horizon_days])
    
    if df.empty:
        return df
    
    df["heat_loss_w"] = heat_loss_w_daily(df["digester_c"], df["actual_ambient_c"])
    df["target"] = df["heat_loss_w"]
    return df



