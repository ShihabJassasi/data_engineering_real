from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models.character import Character

router = APIRouter(prefix="/v1/swapi/characters", tags=["characters"])


@router.get("/")
def get_characters(db: Session = Depends(get_db)):
    characters = (
        db.query(Character)
        .options(joinedload(Character.planet))
        .all()
    )

    result = []
    for c in characters:
        result.append({
            "uid": c.id,
            "character_name": c.character_name,
            "url": c.url,
            "height": c.height,
            "mass": c.mass,
            "hair_color": c.hair_color,
            "skin_color": c.skin_color,
            "eye_color": c.eye_color,
            "birth_year": c.birth_year,
            "planet_id": c.planet_id,
            "planet": None if not c.planet else {
                "planet_id": c.planet.id,
                "name": c.planet.name,
                "rotation_period": c.planet.rotation_period,
                "orbital_period": c.planet.orbital_period,
                "diameter": c.planet.diameter,
                "climate": c.planet.climate,
                "gravity": c.planet.gravity,
                "terrain": c.planet.terrain,
                "surface_water": c.planet.surface_water,
                "population": c.planet.population,
                "url": c.planet.url,
            }
        })

    return result


@router.get("/{uid}")
def get_character(uid: int, db: Session = Depends(get_db)):
    c = (
        db.query(Character)
        .options(joinedload(Character.planet))
        .filter(Character.uid == uid)
        .first()
    )

    if not c:
        raise HTTPException(status_code=404, detail="Character not found")

    return {
        "uid": c.id,
        "character_name": c.character_name,
        "url": c.url,
        "height": c.height,
        "mass": c.mass,
        "hair_color": c.hair_color,
        "skin_color": c.skin_color,
        "eye_color": c.eye_color,
        "birth_year": c.birth_year,
        "planet_id": c.planet_id,
        "planet": None if not c.planet else {
            "planet_id": c.planet.id,
            "name": c.planet.name,
            "rotation_period": c.planet.rotation_period,
            "orbital_period": c.planet.orbital_period,
            "diameter": c.planet.diameter,
            "climate": c.planet.climate,
            "gravity": c.planet.gravity,
            "terrain": c.planet.terrain,
            "surface_water": c.planet.surface_water,
            "population": c.planet.population,
            "url": c.planet.url,
        }
    }
