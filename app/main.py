import csv
import os
from datetime import datetime

import logging
from app.logging_config import setup_logging

import requests
import uvicorn
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager

import time

from app.scheduler import start_scheduler, stop_scheduler

from app.routers.characters import router as characters_router
from app.routers.planets import router as planets_router


setup_logging()
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SYSTEM_STARTUP: FastAPI starting...")
    start_scheduler(run_etl)
    logger.info("SCHEDULER_STARTED: ETL scheduler started")
    yield
    stop_scheduler()
    logger.info("SYSTEM_SHUTDOWN: FastAPI stopped")


old_url = "https://swapi.tech/api/people"
new_url = "https://swapi.info/api/people"
home_world = "https://swapi.info/api/planets/1"

app = FastAPI(lifespan=lifespan)

# ✅ log every API call + errors
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
def fetch_first30_old(limit=30):
    """
    Fetch first `limit` characters from swapi.tech (old API).
    """
    data = requests.get(
        f"https://swapi.tech/api/people?page=1&limit={limit}"
    ).json()
    results1 = data.get("results", [])
    characters_old = []

    for person in results1:
        characters_old.append({
            "uid": person["uid"],
            "character_name": person["name"],
            "url": person["url"]
        })

    return characters_old


@app.get("/characters/new")
def fetch_first30_new():
    """
    Fetch first `limit` characters from swapi.info (new API).
    """
    results2 = requests.get(new_url).json()
    characters_new = []

    for person in results2:
        characters_new.append({
            "character_name": person["name"],
            "height": person["height"],
            "mass": person["mass"],
            "hair_color": person["hair_color"],
            "skin_color": person["skin_color"],
            "eye_color": person["eye_color"],
            "birth_year": person["birth_year"],
            "gender": person["gender"]
        })

    return characters_new


def get_homeworld_first30():
    """
    For first `limit` people, fetch their homeworld data.
    """
    people_res = requests.get("https://swapi.info/api/people").json()

    if isinstance(people_res, dict):
        people = people_res.get("results", [])[:30]
    else:
        people = people_res[:30]

    homeworld_list = []

    for p in people:
        planet = requests.get(p["homeworld"]).json()

        homeworld_list.append({
            "character": p["name"],
            "name": planet.get("name"),
            "rotation_period": planet.get("rotation_period"),
            "orbital_period": planet.get("orbital_period"),
            "diameter": planet.get("diameter"),
            "climate": planet.get("climate"),
            "gravity": planet.get("gravity"),
            "terrain": planet.get("terrain"),
            "surface_water": planet.get("surface_water"),
            "population": planet.get("population"),
        })

    return {
        "count": len(homeworld_list),
        "data": homeworld_list
    }


def run_etl(limit: int = 30):
    """
    Merge:
    - old API (uid, name, url)
    - new API (details)
    - homeworld data
    Then save to CSV.
    """
    logger.info(f"ETL_START: limit={limit}")

    try:
        old_30 = fetch_first30_old(limit=30)
        new_30 = fetch_first30_new()
        homeworld_res = get_homeworld_first30()
        hw_list = homeworld_res.get("data", [])

        homeworld_by_name = {hw.get("character"): hw for hw in hw_list}

        merged = []
        for old, new in zip(old_30, new_30):
            person = {}
            person.update(old)
            person.update(new)

            hw = homeworld_by_name.get(person.get("character_name"), {}) or {}

            person.pop("homeworld", None)

            person["homeworld_name"] = hw.get("name")
            person["rotation_period"] = hw.get("rotation_period")
            person["orbital_period"] = hw.get("orbital_period")
            person["diameter"] = hw.get("diameter")
            person["climate"] = hw.get("climate")
            person["gravity"] = hw.get("gravity")
            person["terrain"] = hw.get("terrain")
            person["surface_water"] = hw.get("surface_water")
            person["population"] = hw.get("population")

            merged.append(person)

        if not merged:
            logger.warning("ETL_EMPTY: No data merged")
            return {"count": 0, "data": [], "message": "No data merged"}

        filename = "merged_characters.csv"

        BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # project root
        data_dir = os.path.join(BASE_DIR, "data")
        os.makedirs(data_dir, exist_ok=True)

        file_path = os.path.join(data_dir, filename)
        tmp_path = file_path + ".tmp"

        with open(tmp_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(merged[0].keys()))
            writer.writeheader()
            writer.writerows(merged)

        if os.path.exists(tmp_path):
            os.replace(tmp_path, file_path)
            logger.info(f"ETL_SUCCESS: rows={len(merged)} file={file_path}")
        else:
            logger.warning(f"ETL_WARN: TMP file not created file={file_path}")
            return {"count": len(merged), "message": "TMP file not created", "file": file_path, "data": merged}

        return {"count": len(merged), "file": file_path, "data": merged}

    except Exception as e:
        logger.exception(f"ETL_FAIL: error={e}")
        return {"count": 0, "error": str(e)}


@app.get("/characters/merged")
def fetch_merged_characters():
    return run_etl()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
