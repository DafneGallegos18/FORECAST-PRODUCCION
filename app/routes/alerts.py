"""
Rutas API para el módulo de Alertas de Inventario.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import List

from app.database import get_db
from app.models.db_models import AlertLog
from app.models.schemas import AlertOut

router = APIRouter(prefix="/api/alerts", tags=["Alertas"])


@router.get("/", response_model=List[AlertOut])
def list_alerts(
    unacknowledged_only: bool = False,
    alert_type: str = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """
    Lista las alertas de inventario más recientes.
    Filtrable por tipo y por estado (reconocida o no).
    """
    query = db.query(AlertLog)

    if unacknowledged_only:
        query = query.filter(AlertLog.acknowledged == False)
    if alert_type:
        query = query.filter(AlertLog.alert_type == alert_type)

    return query.order_by(AlertLog.created_at.desc()).limit(limit).all()


@router.patch("/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: int,
    acknowledged_by: str = "usuario",
    db: Session = Depends(get_db),
):
    """Marca una alerta como reconocida/revisada."""
    alert = db.query(AlertLog).filter(AlertLog.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")

    alert.acknowledged = True
    alert.acknowledged_by = acknowledged_by
    alert.acknowledged_at = datetime.now(timezone.utc)

    db.commit()
    return {"message": f"Alerta #{alert.id} reconocida"}
