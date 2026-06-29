"""
ingest.py

Purpose:
    Generic configurable CSV/XLSX ingester that maps external data files into SQLite tables using sources.json.

Notes:
    This file is part of the Senior Design biodigester/CHP modeling software.
    Comments were added to make the repository easier to review on GitHub.
"""

import argparse
import json
import sqlite3
from pathlib import Path
import pandas as pd

DB_PATH = Path("Data/biodigester.db")
CONFIG_PATH = Path("sources.json")

def apply_transform(series: pd.Series, expr: str) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce")
    # Evaluate simple numeric transforms from sources.json while blocking Python builtins for safety.
    return eval(expr, {"__builtins__": {}}, {"x": x})

def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Could not find {CONFIG_PATH.resolve()}")
    return json.loads(CONFIG_PATH.read_text())

def read_input_file(file_path: Path) -> pd.DataFrame:
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(file_path)
    if suffix in [".xlsx", ".xls"]:
        return pd.read_excel(file_path)
    raise ValueError("Unsupported file format. Use .csv, .xlsx or .xls")

def upsert_dataframe(conn: sqlite3.Connection, table: str, df: pd.DataFrame, key_col: str):
    if df.empty:
        print("No rows to insert (dataframe is empty).")
        return
    
    if key_col not in df.columns:
        raise ValueError(f"key_col '{key_col}' not in dataframe columns: {df.columns.tolist()}")
    
    cols = df.columns.tolist()
    placeholders = ", ".join(["?"] * len(cols))
    col_list = ", ".join(cols)

    update_cols = [c for c in cols if c != key_col]
    if not update_cols:
        raise ValueError("No non-key columns to update; check your mapping/columns")
    
    update_stmt = ", ".join([f"{c}=excluded.{c}" for c in update_cols])

    sql = f"""
    INSERT INTO {table} ({col_list})
    VALUES ({placeholders})
    ON CONFLICT({key_col}) DO UPDATE SET
        {update_stmt};
    """

    conn.executemany(sql, df.itertuples(index=False, name=None))
    conn.commit()

def ingest(source_name: str, file_path_str: str) -> None:
    cfg = load_config()

    if source_name not in cfg:
        raise ValueError(f"Unknown source '{source_name}'. Available sources: {list(cfg.keys())}")
    
    source_cfg = cfg[source_name]
    table = source_cfg["table"]
    date_col_in = source_cfg["date_col"]
    date_format = source_cfg.get("date_format")
    mappings = source_cfg.get("mappings", {})
    transforms = source_cfg.get("transforms", {})
    compute = source_cfg.get("compute", {})

    file_path = Path(file_path_str)
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH.resolve()} Run db_init.py first.")
    
    print("Using DB:" , DB_PATH.resolve())
    print("Using config:,", CONFIG_PATH.resolve())
    print(f"Ingest source: {source_name}")
    print(f"Input file: {file_path.resolve()}")

    df = read_input_file(file_path)
    if df.empty:
        print("Input file has no rows.")
        return
    
    if date_col_in not in df.columns:
        raise ValueError(f"Expected date column '{date_col_in}' not found.\n"
                         f"Columns available: {list(df.columns)}")
    
    # Build a clean output dataframe whose columns match the SQLite target table.
    out = pd.DataFrame()
    dt = pd.to_datetime(df[date_col_in], format=date_format, errors="coerce")
    out["date"] = dt.dt.strftime("%Y-%m-%d")

    for in_col, out_col in mappings.items():
        if in_col not in df.columns:
            out[out_col] = None
            continue

        series = df[in_col]
        if in_col in transforms:
            series = apply_transform(series, transforms[in_col])
        out[out_col] = series
    
    for out_col, expr in compute.items():
        out[out_col] = out.eval(expr)
    
    out = out.dropna(subset=["date"])
    out = out.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    
    # Upsert rows so rerunning ingestion updates existing dates instead of duplicating them.
    with sqlite3.connect(DB_PATH) as conn:
        upsert_dataframe(conn, table=table, df=out, key_col="date")

    print(f"Upserted {len(out)} rows into '{table}'.")

def main():
    parser = argparse.ArgumentParser(description="Generalized file ingester into SQLite using sources.json")
    parser.add_argument("--source", required=True, help="Source name from sources.json (e.g., noaa_daily)")
    parser.add_argument("--file", required=True, help="Path to input CSV/XLSX")
    args = parser.parse_args()

    ingest(args.source, args.file)

if __name__ == "__main__":
    main()
    