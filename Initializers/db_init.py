"""
Initializers/db_init.py

Purpose:
    Creates the local SQLite database tables used by the modeling pipeline.

Notes:
    This file is part of the Senior Design biodigester/CHP modeling software.
    Comments were added to make the repository easier to review on GitHub.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("Data/biodigester.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

print("USING DB:", DB_PATH.resolve())

schema = """
CREATE TABLE IF NOT EXISTS daily_data (
    date TEXT PRIMARY KEY,
    digester_T_min_today REAL,
    digester_T_max_today REAL,
    ambient_T_avg_today REAL,
    CHP_runtime_today REAL,
    biogas_prod_today REAL,
    solar_rad_today REAL,
    digester_T_min_tomorrow REAL
    created_at TEXT DEFAULT (datetime('now'))
    );
    """

schema_weather = """
CREATE TABLE IF NOT EXISTS weather_history (
    date TEXT PRIMARY KEY,
    temp_min_c REAL,
    temp_max_c REAL,
    temp_avg_c REAL,
    temp_obs_c REAL,
    created_at TEXT DEFAULT (datetime('now'))
    );
    """
try:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(schema)
        conn.execute(schema_weather)
        conn.commit()
    print("Created/verified table: daily_data")
    print(f"Initialized DB at: {DB_PATH.resolve()}")
except Exception as e:
    print(f"Error initializing DB: {e}")
    raise