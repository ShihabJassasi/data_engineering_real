from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.planet import Planet
from app.models.character import Character

router = APIRouter(prefix="/v1/swapi/planets", tags=["planets"])

@router.get("")
def get_planets(db: Session = Depends(get_db)):
    return db.query(Planet).all()

@router.get("/{planet_id}")
def get_planet(planet_id: int, db: Session = Depends(get_db)):
    planet = db.query(Planet).filter(Planet.planet_id == planet_id).first()
    if not planet:
        raise HTTPException(status_code=404, detail="Planet not found")
    return planet

@router.get("/{planet_id}/characters")
def get_characters_by_planet(planet_id: int, db: Session = Depends(get_db)):
    return db.query(Character).filter(Character.planet_id == planet_id).all()
