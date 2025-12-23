import csv
import os
from datetime import datetime

import requests
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager



from app.scheduler import start_scheduler, stop_scheduler

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    start_scheduler(run_etl)
    yield
    # shutdown
    stop_scheduler()


old_url = "https://swapi.tech/api/people"
new_url = "https://swapi.info/api/people"
home_world= "https://swapi.info/api/planets/1"

app = FastAPI(lifespan=lifespan)


@app.get("/characters/old")
def fetch_first30_old(limit= 30):
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
            "name": person["name"],
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
            "name": person["name"],
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

def run_etl(limit: int =30):
    """
    Merge:
    - old API (uid, name, url)
    - new API (details)
    - homeworld data
    Then save to CSV.
    """
     
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

        hw = homeworld_by_name.get(person.get("name"), {}) or {}
        
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
        return {"count": 0, "data": [], "message": "No data merged"}

    
    
    filename = "merged_characters.csv"
    folder = os.path.dirname(__file__)
    file_path = os.path.join(folder, filename)

    tmp_path = file_path + ".tmp"

    # make sure folder exists
    os.makedirs(folder, exist_ok=True)

    try:
        with open(tmp_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(merged[0].keys()))
            writer.writeheader()
            writer.writerows(merged)

        # only replace if tmp file was created
        if os.path.exists(tmp_path):
            os.replace(tmp_path, file_path)

            print("TMP:", tmp_path)
            print("FILE:", file_path)
            print("TMP exists?", os.path.exists(tmp_path))

        else:
            return {"count": len(merged), "message": "TMP file not created", "file": file_path, "data": merged}

    except Exception as e:
        return {"count": 0, "error": str(e)}








@app.get("/characters/merged")
def fetch_merged_characters():
    return run_etl()




    


if __name__ == "__main__":

    
    uvicorn.run(app, host="0.0.0.0", port=8000)
    



