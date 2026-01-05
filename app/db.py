from sqlalchemy.orm import sessionmaker
from app.database import engine, Base

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
