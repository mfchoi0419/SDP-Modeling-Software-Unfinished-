"""
Initializers/db_export_training_csv.py

Purpose:
    Exports labeled rows from SQLite into a CSV file for model training or inspection.

Notes:
    This file is part of the Senior Design biodigester/CHP modeling software.
    Comments were added to make the repository easier to review on GitHub.
"""

import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path("Data/biodigester.db")
OUT_CSV = Path("Data/biodigester_training_data.csv")

query = """
SELECT
    date,
    digester_T_min_today,
    digester_T_max_today,
    ambient_T_avg_today,
    CHP_runtime_today,
    biogas_prod_today,
    solar_rad_today,
    digester_T_min_tomorrow
FROM daily_data
WHERE digester_T_min_tomorrow IS NOT NULL
ORDER BY date;
"""

with sqlite3.connect(DB_PATH) as conn:
    df = pd.read_sql_query(query, conn)

OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(OUT_CSV, index=False)
print(f"Exported training data to: {OUT_CSV.resolve()}")
