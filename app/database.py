"""
Configuración de la base de datos local (SQLite).
Se usa SQLAlchemy para ORM y migraciones.
La base de datos local almacena: corridas de forecast, ajustes manuales,
exclusiones dinámicas y log de alertas. Nunca escribe en SAP.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import os

DATABASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATABASE_DIR, exist_ok=True)
DATABASE_URL = f"sqlite:///{os.path.join(DATABASE_DIR, 'forecast.db')}"

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    """Base declarativa para todos los modelos ORM."""
    pass


def get_db():
    """Dependency injection para FastAPI: abre y cierra sesión por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Crear todas las tablas definidas en los modelos."""
    from app.models.db_models import (
        ForecastRun,
        ForecastItem,
        ForecastItemClient,
        ManualAdjustment,
        Exclusion,
        AlertLog,
    )
    Base.metadata.create_all(bind=engine)
    print("✅ Base de datos local inicializada (forecast.db)")
