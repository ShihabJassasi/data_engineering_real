from sqlalchemy import BigInteger, Column, Integer, String
from app.db import Base

class Character(Base):
    __tablename__ = "merged_characters"

    id = Column(BigInteger, primary_key=True, index=True)
    uid = Column(Integer, index=True)
    character_name = Column(String)
    url = Column(String)
    height = Column(Integer)
    mass = Column(Integer)
    hair_color = Column(String)
    skin_color = Column(String)
    eye_color = Column(String)
    birth_year = Column(String)
    planet_id = Column(Integer)

