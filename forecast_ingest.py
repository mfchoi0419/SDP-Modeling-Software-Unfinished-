"""
forecast_ingest.py

Purpose:
    Fetches Open-Meteo daily forecasts and stores them in the SQLite forecast table.

Notes:
    This file is part of the Senior Design biodigester/CHP modeling software.
    Comments were added to make the repository easier to review on GitHub.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

@dataclass(frozen=True)
class ForecastAppendResults:
    status: str
    issued_at: str | None = None
    n_rows: int = 0
    days: int = 0
    source: str = "open-meteo"
    reason: str | None = None

def _fetch_open_meteo_daily(lat: float, lon: float, days: int,
                            timezone: str = "America/New_York",
                            timeout_s: int = 20,) -> dict[str, Any]:
    if not (1 <= days <= 16):
        raise ValueError("Open-Meteo forecast_days must be between 1 and 16.")
    
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_min,temperature_2m_max,temperature_2m_mean",
        "timezone": timezone,
        "forecast_days": days,
        "temperature_unit": "celsius",
        "timeformat": "iso8601",
        "past_days": 0,
    }

    url = f"{OPEN_METEO_URL}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": "SDP_CHP_Pipeline/1.0"})
    with urlopen(req, timeout=timeout_s) as resp:
        body = resp.read().decode("utf-8")
    
    return json.loads(body)

def _ensure_forecast_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS weather_forecast_daily (
            issued_at TEXT NOT NULL,
            forecast_date TEXT NOT NULL,
            horizon_days INTEGER NOT NULL,
            temp_min_c REAL,
            temp_max_c REAL,
            temp_avg_c REAL,
            source TEXT NOT NULL,
            raw_json TEXT,
            created_at TEXT NOT NULL,
            PRIMARY KEY (issued_at, forecast_date, source)
        );
    """)
    conn.commit()

def append_forecast_to_db(db_path: str, lat: float, lon: float, days: int = 7,
                          timezone: str = "America/New_York",
                          source: str = "open-meteo",
                          debug_print: bool = False,) -> ForecastAppendResults:
    # issued_at uniquely identifies one forecast run, so later evaluation can trace predictions back to the forecast issue time.
    issued_at = datetime.now().replace(microsecond=0).isoformat()
    created_at = issued_at

    try:
        raw = _fetch_open_meteo_daily(lat=lat, lon=lon, days=days, timezone=timezone)
    except Exception as e:
        return ForecastAppendResults(status="error", reason=f"fetch_failed: {e}")
    
    daily = raw.get("daily") or {}
    dates = daily.get("time") or []
    tmin = daily.get("temperature_2m_min") or []
    tmax = daily.get("temperature_2m_max") or []
    tavg = daily.get("temperature_2m_mean") or []

    if debug_print:
        print("DEBUG daily.time:", dates)
        print("DEBUG tmin:", tmin)
        print("DEBUG tmax:", tmax)
        print("DEBUG tmean:", tavg)

    if not dates:
        return ForecastAppendResults(status="error", reason="no_daily_forecast_returned")
    
    raw_json = json.dumps(raw)

    upsert_sql = """
        INSERT INTO weather_forecast_daily (
        issued_at, forecast_date, horizon_days,
        temp_min_c, temp_max_c, temp_avg_c,
        source, raw_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(issued_at, forecast_date, source)
        DO UPDATE SET
            horizon_days=excluded.horizon_days,
            temp_min_c=excluded.temp_min_c,
            temp_max_c=excluded.temp_max_c,
            temp_avg_c=excluded.temp_avg_c,
            raw_json=excluded.raw_json,
            created_at=excluded.created_at;
    """

    try:
        with sqlite3.connect(db_path) as conn:
            _ensure_forecast_table(conn)
            cur = conn.cursor()

            # Store each forecast date as one row with a horizon value: 1=today/tomorrow depending on API date ordering.
            for i, d in enumerate(dates):
                cur.execute(
                    upsert_sql,
                    (
                        issued_at,
                        d,
                        i + 1,
                        (tmin[i] if i < len(tmin) else None),
                        (tmax[i] if i < len(tmax) else None),
                        (tavg[i] if i < len(tavg) else None),
                        source,
                        raw_json,
                        created_at,
                    ),
                )
            
            conn.commit()
    except Exception as e:
        return ForecastAppendResults(status="error", reason=f"db_write_failed: {e}")
    
    return ForecastAppendResults(
        status="ok",
        issued_at=issued_at,
        n_rows=len(dates),
        days=days,
        source=source
    )

if __name__ == "__main__":
    result = append_forecast_to_db(
        db_path="Data/biodigester.db",
        lat=42.39135,
        lon=-72.52327,
        days=7,
        debug_print=True,
    )
    print(result)
    