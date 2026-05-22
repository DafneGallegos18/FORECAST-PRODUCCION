"""
Rutas API para el módulo de Exclusiones Dinámicas.
CRUD completo para gestionar reglas de filtrado.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.db_models import Exclusion
from app.models.schemas import ExclusionCreate, ExclusionOut

router = APIRouter(prefix="/api/exclusions", tags=["Exclusiones"])


@router.get("/", response_model=List[ExclusionOut])
def list_exclusions(active_only: bool = True, db: Session = Depends(get_db)):
    """Lista todas las exclusiones. Por defecto, solo las activas."""
    query = db.query(Exclusion)
    if active_only:
        query = query.filter(Exclusion.is_active == True)
    return query.order_by(Exclusion.created_at.desc()).all()


@router.post("/", response_model=ExclusionOut, status_code=201)
def create_exclusion(data: ExclusionCreate, db: Session = Depends(get_db)):
    """Crea una nueva regla de exclusión."""
    exclusion = Exclusion(**data.model_dump())
    db.add(exclusion)
    db.commit()
    db.refresh(exclusion)
    return exclusion


@router.patch("/{exclusion_id}/toggle", response_model=ExclusionOut)
def toggle_exclusion(exclusion_id: int, db: Session = Depends(get_db)):
    """Activa/desactiva una regla de exclusión."""
    exc = db.query(Exclusion).filter(Exclusion.id == exclusion_id).first()
    if not exc:
        raise HTTPException(status_code=404, detail="Exclusión no encontrada")

    exc.is_active = not exc.is_active
    db.commit()
    db.refresh(exc)
    return exc


@router.delete("/{exclusion_id}", status_code=204)
def delete_exclusion(exclusion_id: int, db: Session = Depends(get_db)):
    """Elimina permanentemente una regla de exclusión."""
    exc = db.query(Exclusion).filter(Exclusion.id == exclusion_id).first()
    if not exc:
        raise HTTPException(status_code=404, detail="Exclusión no encontrada")

    db.delete(exc)
    db.commit()
