from io import TextIOWrapper
import requests
from fastapi import FastAPI
import csv



old_url = "https://swapi.tech/api/people"
new_url = "https://swapi.info/api/people"
home_world= "https://swapi.info/api/planets/1"

app =FastAPI()

@app.get("/characters/old")
def fetch_first30_old(limit= 29):
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


@app.get("/characters/merged")
def fetch_merged_characters():
    old_30 = fetch_first30_old()
    new_30 = fetch_first30_new()
    homeworld_list = get_homeworld_first30()

    merged = []

    homeworld_by_name = {hw["character"]: hw for hw in homeworld_list["data"]}

    for old, new in zip(old_30, new_30):
        person = old.copy()
        person.update(new)
        person["homeworld"] = homeworld_by_name.get(person["name"])
        merged.append(person)

    file = open("merged_characters.csv", "w", newline="", encoding="utf-8")
    writer = csv.DictWriter(file, merged[0].keys())
    writer.writeheader()
    writer.writerows(merged)
    file.close()

    return merged




    


if __name__ == "__main__":

    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
    



