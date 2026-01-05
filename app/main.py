import time
import logging
from contextlib import asynccontextmanager

import requests
import uvicorn
from fastapi import FastAPI, Request
from sqlalchemy import text

from app.logging_config import setup_logging
from app.scheduler import start_scheduler, stop_scheduler
from app.routers.characters import router as characters_router
from app.routers.planets import router as planets_router
from app.db import Base, engine

setup_logging()
logger = logging.getLogger("app")

# API endpoints (using swapi.info)
OLD_URL = "https://swapi.tech/api/people"
NEW_URL = "https://swapi.info/api/people"

# ✅ NEW: planets base endpoint
PLANETS_URL = "https://swapi.info/api/planets"


def safe_get_json(url: str, timeout: int = 20):
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


def parse_people(data):
    """
    swapi.info may return a list directly, or a dict with results/result/people.
    """
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("results") or data.get("result") or data.get("people") or []
    return []


def extract_planet_id(homeworld_url: str) -> int | None:
    """
    Extracts the numeric planet id from a homeworld URL.
    Example: https://swapi.info/api/planets/1 -> 1
    """
    if not homeworld_url:
        return None
    try:
        return int(homeworld_url.rstrip("/").split("/")[-1])
    except Exception:
        return None


# ✅ NEW: fetch planet details by planet_id
def fetch_planet_by_id(planet_id: int) -> dict | None:
    try:
        url = f"{PLANETS_URL.rstrip('/')}/{planet_id}"
        data = safe_get_json(url, timeout=20)

        if isinstance(data, dict) and "result" in data and isinstance(data["result"], dict):
            data = data["result"]

        if not isinstance(data, dict):
            return None

        return {
            "id": planet_id,
            "name": data.get("name"),
            "rotation_period": data.get("rotation_period"),
            "orbital_period": data.get("orbital_period"),
            "diameter": data.get("diameter"),
            "climate": data.get("climate"),
            "gravity": data.get("gravity"),
            "terrain": data.get("terrain"),
            "surface_water": data.get("surface_water"),
            "population": data.get("population"),
            "url": url,
        }
    except Exception as e:
        logger.warning(f"PLANET_FETCH_FAIL: id={planet_id} error={e}")
        return None



# ✅ NEW: Upsert planets into DB so repeated planet_id stays same row (no duplicates)
def upsert_planets(planet_ids: set[int]):
    if not planet_ids:
        return

    planets_rows = []
    for pid in sorted(planet_ids):
        p = fetch_planet_by_id(pid)
        if p and p.get("name"):
            planets_rows.append(p)

    if not planets_rows:
        return

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO planets
                (id, name, rotation_period, orbital_period, diameter, climate, gravity, terrain, surface_water, population, url)
                VALUES
                (:id, :name, :rotation_period, :orbital_period, :diameter, :climate, :gravity, :terrain, :surface_water, :population, :url)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    rotation_period = EXCLUDED.rotation_period,
                    orbital_period = EXCLUDED.orbital_period,
                    diameter = EXCLUDED.diameter,
                    climate = EXCLUDED.climate,
                    gravity = EXCLUDED.gravity,
                    terrain = EXCLUDED.terrain,
                    surface_water = EXCLUDED.surface_water,
                    population = EXCLUDED.population,
                    url = EXCLUDED.url
                """
            ),
            planets_rows,
        )

    logger.info(f"PLANETS_UPSERT_DONE: rows={len(planets_rows)}")



@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SYSTEM_STARTUP: FastAPI starting...")

    # Ensure tables exist once at startup
    Base.metadata.create_all(bind=engine)
    logger.info("DB_READY: tables ensured")

    # Start ETL scheduler
    start_scheduler(run_etl)
    logger.info("SCHEDULER_STARTED: ETL scheduler started")

    yield

    # Stop scheduler on shutdown
    stop_scheduler()
    logger.info("SYSTEM_SHUTDOWN: FastAPI stopped")


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    try:
        response = await call_next(request)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(
            f"API_CALL: {request.method} {request.url.path} "
            f"status={response.status_code} duration_ms={duration_ms}"
        )
        return response
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        logger.exception(
            f"API_ERROR: {request.method} {request.url.path} "
            f"duration_ms={duration_ms} error={e}"
        )
        raise


app.include_router(characters_router)
app.include_router(planets_router)


@app.get("/characters/old")
def fetch_first_old(limit: int = 30):
    """
    Old endpoint: returns uid + name + url.
    swapi.info may not always provide uid, so we fallback to index.
    """
    try:
        data = safe_get_json(f"{OLD_URL}?page=1&limit={limit}")
        people = parse_people(data)
    except Exception as e:
        logger.exception(f"OLD_API_FAIL: {e}")
        return []

    rows = []
    for idx, p in enumerate(people, start=1):
        rows.append(
            {
                "uid": str(p.get("uid") or idx),
                "character_name": p.get("name"),
                "url": p.get("url") or f"{OLD_URL.rstrip('/')}/{idx}",
            }
        )
    return rows


@app.get("/characters/new")
def fetch_first_new(limit: int = 30):
    """
    New endpoint: returns details.
    """
    try:
        data = safe_get_json(NEW_URL)
        people = parse_people(data)[:limit]
    except Exception as e:
        logger.exception(f"NEW_API_FAIL: {e}")
        return []

    rows = []
    for p in people:
        rows.append(
            {
                "character_name": p.get("name"),
                "height": p.get("height"),
                "mass": p.get("mass"),
                "hair_color": p.get("hair_color"),
                "skin_color": p.get("skin_color"),
                "eye_color": p.get("eye_color"),
                "birth_year": p.get("birth_year"),
                "homeworld": p.get("homeworld"),
            }
        )
    return rows


def get_homeworld_for_people(people: list[dict]):
    """
    Returns a dict: normalized_name -> planet_id
    """
    out = {}
    for p in people:
        name = (p.get("character_name") or "").strip().lower()
        hw = p.get("homeworld")
        if name:
            out[name] = extract_planet_id(hw)
    return out


def load_to_db(rows: list[dict], truncate_first: bool = True):
    """
    Loads merged rows directly into merged_characters table.
    """
    if not rows:
        logger.warning("DB_LOAD_SKIPPED: rows=0")
        return

    logger.info(f"DB_LOAD_START: rows={len(rows)} truncate={truncate_first}")

    with engine.begin() as conn:
        if truncate_first:
            conn.execute(text("TRUNCATE TABLE merged_characters RESTART IDENTITY"))

        conn.execute(
            text(
                """
                INSERT INTO merged_characters
                (uid, character_name, url, height, mass, hair_color, skin_color, eye_color, birth_year, planet_id)
                VALUES
                (:uid, :character_name, :url, :height, :mass, :hair_color, :skin_color, :eye_color, :birth_year, :planet_id)
                """
            ),
            rows,
        )

        cnt = conn.execute(text("select count(*) from merged_characters")).scalar()
        logger.info(f"DB_LOAD_DONE: count_now={cnt}")


def to_int_or_none(value):
    """
    Convert values like '172' -> 172, and 'unknown'/'n/a'/None -> None.
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value

    s = str(value).strip().lower()
    if s in ("", "unknown", "n/a", "none", "null"):
        return None

    s = s.replace(",", "")
    try:
        return int(float(s))
    except Exception:
        return None


def run_etl(limit: int = 30):
    """
    ETL:
    - Fetch old + new
    - Merge by name
    - Extract planet_id from homeworld
    - Upsert planets table by planet_id (no duplicates)
    - Write merged_characters to PostgreSQL
    """
    logger.info(f"ETL_START: limit={limit}")

    try:
        old_rows = fetch_first_old(limit=limit)
        new_rows = fetch_first_new(limit=limit)

        if not old_rows:
            logger.warning("ETL_ABORT: old_rows=0 (skipping DB write)")
            return {"count": 0, "loaded_to_db": False, "message": "old API returned 0"}

        if not new_rows:
            logger.warning("ETL_ABORT: new_rows=0 (skipping DB write)")
            return {"count": 0, "loaded_to_db": False, "message": "new API returned 0"}

        # Map new rows by normalized name
        new_by_name = {}
        for r in new_rows:
            key = (r.get("character_name") or "").strip().lower()
            if key:
                new_by_name[key] = r

        # Planet id by normalized name
        planet_id_by_name = get_homeworld_for_people(new_rows)

        # ✅ NEW: collect unique planet ids then upsert planets table
        unique_planet_ids = {pid for pid in planet_id_by_name.values() if isinstance(pid, int)}
        upsert_planets(unique_planet_ids)

        merged = []
        for o in old_rows:
            name = o.get("character_name")
            key = (name or "").strip().lower()
            n = new_by_name.get(key, {}) or {}

            merged.append(
                {
                    "uid": o.get("uid"),
                    "character_name": name,
                    "url": o.get("url") or n.get("url"),
                    "height": to_int_or_none(n.get("height")),
                    "mass": to_int_or_none(n.get("mass")),
                    "hair_color": n.get("hair_color"),
                    "skin_color": n.get("skin_color"),
                    "eye_color": n.get("eye_color"),
                    "birth_year": n.get("birth_year"),
                    "planet_id": planet_id_by_name.get(key),
                }
            )

        if not merged:
            logger.warning("ETL_EMPTY: No data merged")
            return {"count": 0, "loaded_to_db": False, "message": "No data merged"}

        load_to_db(merged, truncate_first=True)

        logger.info(f"DB_LOAD_SUCCESS: rows={len(merged)}")
        return {"count": len(merged), "loaded_to_db": True}

    except Exception as e:
        logger.exception(f"ETL_FAIL: error={e}")
        return {"count": 0, "loaded_to_db": False, "error": str(e)}


@app.get("/characters/merged")
def fetch_merged_characters(limit: int = 30):
    """
    Manual ETL trigger (also writes to DB).
    """
    return run_etl(limit=limit)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
