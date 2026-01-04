from sqlalchemy import Column, Integer, String, BigInteger
from app.db import Base

class Planet(Base):
    __tablename__ = "merged_planets"

    planet_id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String)

    rotation_period = Column(Integer)
    orbital_period = Column(Integer)
    diameter = Column(Integer)
    climate = Column(String)
    gravity = Column(String)
    terrain = Column(String)
    surface_water = Column(Integer)
    population = Column(BigInteger)
