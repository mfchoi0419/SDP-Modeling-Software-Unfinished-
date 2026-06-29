"""
open_meteo_history_ingest.py

Purpose:
    Backfills historical daily weather observations from the Open-Meteo archive API into SQLite.

Notes:
    This file is part of the Senior Design biodigester/CHP modeling software.
    Comments were added to make the repository easier to review on GitHub.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

@dataclass(frozen=True)
class HistoryBackfillResult:
    status: str
    n_rows: int = 0
    start_date: str | None = None
    end_date: str | None = None
    reason: str | None = None

def _ensure_weather_history_table(conn: sqlite3.Connection, 
table: str = "weather_history") -> None:
    conn.execute(f"""
                 CREATE TABLE IF NOT EXISTS {table} (
                    date TEXT PRIMARY KEY,
                    temp_min_c REAL,
                    temp_max_c REAL,
                    temp_avg_c REAL,
                    source TEXT,
                    raw_json TEXT,
                    created_at TEXT
        );
    """)
    conn.commit()

def _fetch_open_meteo_archive_daily(
        lat: float,
        lon: float,
        start_date: str,
        end_date: str,
        timezone: str = "America/New_York",
        timeout_s: int = 25,
) -> dict[str, Any]:
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": "temperature_2m_min,temperature_2m_max,temperature_2m_mean",
        "timezone": timezone,
        "temperature_unit": "celsius",
        "timeformat":"iso8601"
    }
    url = f"{OPEN_METEO_ARCHIVE_URL}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": "SDP-CHP-Pipeline/1.0"})
    with urlopen(req, timeout=timeout_s) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body)

def _get_last_history_date(conn: sqlite3.Connection, 
table: str = "weather_history") -> str | None:
    row = conn.execute(f"SELECT MAX(date(substr(date,1,10))) FROM {table};").fetchone()
    if not row:
        return None
    return row[0]

def backfill_weather_history_from_open_meteo(
        db_path: str,
        lat: float,
        lon: float,
        table: str = "weather_history",
        timezone: str = "America/New_York",
        max_days_per_request: int = 365,
        debug_print: bool = False,
) -> HistoryBackfillResult:
    try:
        with sqlite3.connect(db_path) as conn:
            _ensure_weather_history_table(conn, table=table)
            last = _get_last_history_date(conn, table=table)
        
        # If the database has no history yet, start with a two-year backfill window.
        if last is None:
            start = (date.today() - timedelta(days=730))
        else:
            start = datetime.strptime(last, "%Y-%m-%d").date() + timedelta(days=1)
        
        end = date.today() - timedelta(days=1)

        if start > end:
            return HistoryBackfillResult(status="ok", n_rows=0, start_date=str(start), end_date=str(end))
        
        total_inserted = 0
        cur_start = start

        # Open-Meteo requests are chunked to avoid overly large API calls.
        while cur_start <= end:
            cur_end = min(cur_start + timedelta(days=max_days_per_request - 1), end)
            s = cur_start.isoformat()
            e = cur_end.isoformat()

            raw = _fetch_open_meteo_archive_daily(lat, lon, s, e, timezone=timezone)

            daily = raw.get("daily") or {}
            dates = daily.get("time") or []
            tmin = daily.get("temperature_2m_min") or []
            tmax = daily.get("temperature_2m_max") or []
            tmean = daily.get("temperature_2m_mean") or []

            if debug_print:
                print(f"DEBUG archive rang {s}..{e} n={len(dates)}")
            
            raw_json = json.dumps(raw)
            created_at = datetime.now().replace(microsecond=0).isoformat()

            upsert_sql = f"""
            INSERT INTO {table} (date, temp_min_c, temp_max_c, temp_avg_c, source, raw_json, created_at)
            VALUES (?, ? , ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
              temp_min_c=excluded.temp_min_c,
              temp_max_c=excluded.temp_max_c,
              temp_avg_c=excluded.temp_avg_c,
              source=excluded.source,
              raw_json=excluded.raw_json,
              created_at=excluded.created_at;
            """

            with sqlite3.connect(db_path) as conn:
                _ensure_weather_history_table(conn, table=table)
                cur = conn.cursor()

                for i, d in enumerate(dates):
                    day = str(d)[:10]
                    cur.execute(
                        upsert_sql,
                        (
                            day,
                            (tmin[i] if i < len(tmin) else None),
                            (tmax[i] if i < len(tmax) else None),
                            (tmean[i] if i < len(tmean) else None),
                            "open-meteo-archive",
                            raw_json,
                            created_at,
                        ),
                    )
                conn.commit()
            
            total_inserted += len(dates)
            cur_start = cur_end + timedelta(days=1)
        
        return HistoryBackfillResult(
            status="ok",
            n_rows=total_inserted,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
        )
    
    except Exception as e:
        return HistoryBackfillResult(status="error", reason=str(e))

if __name__ == "__main__":
    out = backfill_weather_history_from_open_meteo(
        db_path="Data/biodigester.db",
        lat=42.39135,
        lon=-72.52327,
        debug_print=True,
    )
    print(out)
    