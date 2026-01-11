from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.db import Base

class Planet(Base):
    __tablename__ = "planets"

    id = Column(Integer, primary_key=True, autoincrement=False, index=True)
    name = Column(String, nullable=True)
    rotation_period = Column(String, nullable=True)
    orbital_period = Column(String, nullable=True)
    diameter = Column(String, nullable=True)
    climate = Column(String, nullable=True)
    gravity = Column(String, nullable=True)
    terrain = Column(String, nullable=True)
    surface_water = Column(String, nullable=True)
    population = Column(String, nullable=True)
    url = Column(String, nullable=True)

    characters = relationship("Character", back_populates="planet")
