"""
Configuración de la base de datos local (SQLite).
Se usa SQLAlchemy para ORM y migraciones.
La base de datos local almacena: corridas de forecast, ajustes manuales,
exclusiones dinámicas y log de alertas. Nunca escribe en SAP.
"""

from sqlalchemy import create_engine, text
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
    """Crear todas las tablas definidas en los modelos y aplicar columnas faltantes."""
    from app.models.db_models import (
        ForecastRun,
        ForecastItem,
        ForecastItemClient,
        ManualAdjustment,
        Exclusion,
        AlertLog,
        SpecialDemand,
        ProductShelfLife,
    )
    Base.metadata.create_all(bind=engine)

    # Migraciones automáticas para columnas agregadas a tablas SQLite existentes
    with engine.connect() as conn:
        migrations = [
            ("forecast_runs", "shelf_life_safety_pct", "FLOAT DEFAULT 50.0"),
            ("forecast_items", "shelf_life_days", "FLOAT"),
            ("forecast_items", "max_safe_days", "FLOAT"),
            ("forecast_items", "effective_target_days", "FLOAT"),
            ("forecast_items", "is_batch_optimized", "BOOLEAN DEFAULT 0"),
            ("forecast_items", "has_expiration_risk", "BOOLEAN DEFAULT 0"),
        ]
        for table, col, col_type in migrations:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                conn.commit()
            except Exception:
                pass

    print("[OK] Base de datos local inicializada (forecast.db)")
