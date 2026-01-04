# app/pipeline.py
import os
from datetime import datetime

from dotenv import load_dotenv


import pandas as pd
from sqlalchemy import create_engine, text


from app.main import run_etl

load_dotenv() 
DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    raise ValueError("DATABASE_URL is missing. Put it in .env")

# ===== paths =====
BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # project root
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

RAW_CSV = os.path.join(DATA_DIR, "merged_characters.csv")
CLEAN_CSV = os.path.join(DATA_DIR, "merged_characters_clean.csv")


# ===== DB config (CHANGE THIS) =====


def clean_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]

    # Ensure correct column name
    if "name" in df.columns and "character_name" not in df.columns:
        df = df.rename(columns={"name": "character_name"})

    # strip text columns
    text_cols = [
        "character_name", "url", "hair_color", "skin_color", "eye_color",
        "birth_year", "gender", "homeworld_name", "climate", "gravity", "terrain"
    ]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()

    # fill missing text
    for col in ["hair_color", "gender", "homeworld_name", "climate", "gravity", "terrain"]:
        if col in df.columns:
            df[col] = df[col].fillna("unknown")

    # normalize gender
    if "gender" in df.columns:
        df["gender"] = df["gender"].str.lower().replace({"n/a": "unknown", "none": "unknown"})

    # numeric columns -> convert (keep NaN as NULL for DB)
    num_cols = [
        "uid", "height", "mass", "rotation_period", "orbital_period",
        "diameter", "surface_water", "population"
    ]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # drop duplicates
    if "uid" in df.columns:
        df = df.drop_duplicates(subset=["uid"], keep="last")

    # drop meaningless rows (optional but useful)
    needed = {"population", "homeworld_name", "climate"}
    if needed.issubset(df.columns):
        df = df[~(
            (df["population"].fillna(0) == 0) &
            (df["homeworld_name"].fillna("unknown") == "unknown") &
            (df["climate"].fillna("unknown") == "unknown")
        )]

    return df


def save_csv_atomic(df: pd.DataFrame, path: str) -> None:
    tmp = path + ".tmp"
    df.to_csv(tmp, index=False, encoding="utf-8")
    os.replace(tmp, path)


def load_to_postgres(df: pd.DataFrame) -> None:
    engine = create_engine(DB_URL)

    cols = [
        "uid", "character_name", "url",
        "height", "mass", "hair_color", "skin_color", "eye_color", "birth_year", "gender",
        "homeworld_name", "rotation_period", "orbital_period", "diameter",
        "climate", "gravity", "terrain", "surface_water", "population"
    ]
    df2 = df[[c for c in cols if c in df.columns]].copy()

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE public.merged_characters;"))
        df2.to_sql("merged_characters", conn, schema="public", if_exists="append", index=False)


def run_pipeline(limit: int = 30) -> dict:
    merged_res = run_etl(limit=limit)

    # 1) collect data from whatever run_etl returned
    data = []

    if isinstance(merged_res, dict):
        data = merged_res.get("data") or []

    elif isinstance(merged_res, list):
        data = merged_res

    # 2) if still empty, try reading RAW_CSV (if run_etl only writes CSV)
    if not data:
        if os.path.exists(RAW_CSV):
            df_raw = pd.read_csv(RAW_CSV)
            data = df_raw.to_dict(orient="records")
        else:
            return {
                "ok": False,
                "message": "No merged data (run_etl returned nothing and RAW_CSV not found)",
                "count": 0
            }

    # 3) clean
    df = pd.DataFrame(data)
    df_clean = clean_df(df)

    # 4) save clean csv
    save_csv_atomic(df_clean, CLEAN_CSV)

    # 5) load to postgres
    load_to_postgres(df_clean)

    return {
        "ok": True,
        "count": len(df_clean),
        "clean_csv": CLEAN_CSV,
        "loaded_at": datetime.now().isoformat()
    }


if __name__ == "__main__":
    print(run_pipeline())
