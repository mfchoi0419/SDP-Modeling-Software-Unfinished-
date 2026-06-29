"""
db_append_daily.py

Purpose:
    Example utility for inserting or updating one daily biodigester operating row in SQLite.

Notes:
    This file is part of the Senior Design biodigester/CHP modeling software.
    Comments were added to make the repository easier to review on GitHub.
"""

import sqlite3
from pathlib import Path
import datetime

DB_Path = Path("Data/biodigester.db")

def upsert_daily_row(row: dict):
    sql = """
    INSERT INTO daily_data  (
    date, digester_T_min_today, digester_T_max_today, ambient_T_avg_today, 
    CHP_runtime_today, biogas_prod_today, solar_rad_today, digester_T_min_tomorrow
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(date) DO UPDATE SET
        digester_T_min_today=excluded.digester_T_min_today,
        digester_T_max_today=excluded.digester_T_max_today,
        ambient_T_avg_today=excluded.ambient_T_avg_today,
        CHP_runtime_today=excluded.CHP_runtime_today,
        biogas_prod_today=excluded.biogas_prod_today,
        solar_rad_today=excluded.solar_rad_today,
        digester_T_min_tomorrow=excluded.digester_T_min_tomorrow;
    """

    vals = (
        row["date"],
        row["digester_T_min_today"],
        row["digester_T_max_today"],
        row["ambient_T_avg_today"],
        row["CHP_runtime_today"],
        row["biogas_prod_today"],
        row["solar_rad_today"],
        row["digester_T_min_tomorrow"],
    )

    print("USING DB:", DB_Path.resolve())
    print("SQL:\n", sql)
    print("VALS:\n", vals)

    with sqlite3.connect(DB_Path) as conn:
        conn.execute(sql, vals)
        conn.commit()

def main():
    date_str = datetime.date.today().isoformat()

    row = {
        "date": date_str,
        "digester_T_min_today": 34.5,
        "digester_T_max_today": 35.8,
        "ambient_T_avg_today": 6.1,
        "CHP_runtime_today": 2.5,
        "biogas_prod_today": 10.2,
        "solar_rad_today": 1.2,
        "digester_T_min_tomorrow": None,
    }

    upsert_daily_row(row)
    print(f"Upserted data for {date_str} into {DB_Path}")

if __name__ == "__main__":
    main()