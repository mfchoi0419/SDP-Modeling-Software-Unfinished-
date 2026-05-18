"""
Initializers/update_yesterday_label.py

Purpose:
    Uses today's measured minimum temperature to label yesterday's target value in SQLite.

Notes:
    This file is part of the Senior Design biodigester/CHP modeling software.
    Comments were added to make the repository easier to review on GitHub.
"""

import argparse
import sqlite3
from pathlib import Path
from datetime import date, timedelta

DB_PATH = Path("data/biodigester.db")
DAILY_TABLE = "daily_data"

def label_yesterday(conn: sqlite3.Connection, today_date: str, today_min_temp: float):
    """
    Sets yesterday's digester_T_min_tomorrow = today's digester min temp.
    """
    yday = (date.fromisoformat(today_date) - timedelta(days=1)).isoformat()

    conn.execute(
        f"""
        INSERT OR IGNORE INTO {DAILY_TABLE} (date)
        VALUES (?);
        """,
        (yday,)
    )

    conn.execute(
        f"""
        UPDATE {DAILY_TABLE}
        SET digester_T_min_tomorrow = ?
        WHERE date = ?;
        """,
        (today_min_temp, yday)
    )

    conn.commit()
    return yday

def main():
    parser = argparse.ArgumentParser(description="Update yesterday's label using today's measured digester minimum.")
    parser.add_argument("--today", default=date.today().isoformat(),
                        help="Today's date in YYYY-MM-DD. Default: today.")
    parser.add_argument("--temp", type=float, required=True,
                        help="Today's measured digester minimum temperature (°C).")
    args = parser.parse_args()

    if not DB_PATH.exists():
        raise FileNotFoundError(f"DB not found: {DB_PATH.resolve()} (run db_init.py first)")

    with sqlite3.connect(DB_PATH) as conn:
        yday = label_yesterday(conn, args.today, args.temp)

    print(f"Labeled {yday} digester_T_min_tomorrow = {args.temp:.2f} °C (from {args.today})")

if __name__ == "__main__":
    main()
