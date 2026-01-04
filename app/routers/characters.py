from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.character import Character
from app.models.planet import Planet


router = APIRouter(prefix="/v1/swapi/characters", tags=["characters"])

@router.get("")
def get_characters(db: Session = Depends(get_db)):
    return db.query(Character).all()

@router.get("/{uid}")
def get_character(uid: int, db: Session = Depends(get_db)):
    character = db.query(Character).filter(Character.uid == uid).first()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    return character
