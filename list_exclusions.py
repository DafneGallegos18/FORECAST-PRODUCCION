from app.database import SessionLocal
from app.models.db_models import Exclusion

db = SessionLocal()
try:
    exclusions = db.query(Exclusion).all()
    print(f"Total Exclusions: {len(exclusions)}")
    for exc in exclusions:
        print(f"ID: {exc.id} | Tipo: {exc.exclusion_type.value} | Valor: {exc.value} | Secundario: {exc.secondary_value} | Activo: {exc.is_active} | Desc: {exc.description}")
finally:
    db.close()
