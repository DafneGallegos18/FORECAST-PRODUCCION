"""
Rutas API para gestionar incrementos de demandas especiales (excepciones).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.db_models import SpecialDemand
from app.models.schemas import SpecialDemandCreate, SpecialDemandUpdate, SpecialDemandOut
from app.services.special_demand_service import sync_special_demands_with_sap

router = APIRouter(prefix="/api/special-demands", tags=["Demandas Especiales"])


@router.get("/sap-products")
def get_sap_products(db: Session = Depends(get_db)):
    """Obtiene el catálogo de productos activos de venta (excluyendo insumos) desde SAP B1 o fallback de la BD."""
    try:
        from app.services.sap_connector import sap_connector
        df = sap_connector.query("SELECT DISTINCT ItemCode, ItemName FROM OITM WHERE SellItem = 'Y' AND ISNULL(frozenFor, 'N') = 'N' AND (validFor = 'Y' OR validFor IS NULL) ORDER BY ItemCode")
        if not df.empty:
            df["ItemCode"] = df["ItemCode"].astype(str).str.strip()
            df["ItemName"] = df["ItemName"].fillna("").astype(str).str.strip()
            return df.to_dict(orient="records")
    except Exception as e:
        print(f"⚠️ Error al consultar productos de SAP: {e}")
    
    from app.models.db_models import ForecastItem
    items = db.query(ForecastItem.item_code, ForecastItem.item_name).distinct().all()
    return [{"ItemCode": i.item_code, "ItemName": i.item_name or ""} for i in items]


@router.get("/sap-clients")
def get_sap_clients(db: Session = Depends(get_db)):
    """Obtiene el catálogo de clientes activos desde SAP B1 o fallback de la BD."""
    try:
        from app.services.sap_connector import sap_connector
        df = sap_connector.query("SELECT DISTINCT CardCode, CardName FROM OCRD WHERE CardType = 'C' AND ISNULL(frozenFor, 'N') = 'N' AND (validFor = 'Y' OR validFor IS NULL) ORDER BY CardCode")
        if not df.empty:
            df["CardCode"] = df["CardCode"].astype(str).str.strip()
            df["CardName"] = df["CardName"].fillna("").astype(str).str.strip()
            return df.to_dict(orient="records")
    except Exception as e:
        print(f"⚠️ Error al consultar clientes de SAP: {e}")
    
    from app.models.db_models import ForecastItemClient
    clients = db.query(ForecastItemClient.card_code, ForecastItemClient.card_name).distinct().all()
    return [{"CardCode": c.card_code, "CardName": c.card_name or ""} for c in clients]


@router.get("/", response_model=List[SpecialDemandOut])
def list_special_demands(active_only: bool = False, db: Session = Depends(get_db)):
    """Lista todos los incrementos programados de demandas especiales."""
    # Sincronizar consumos en cada consulta para tener datos frescos
    try:
        sync_special_demands_with_sap(db)
    except Exception as e:
        print(f"⚠️ Error al sincronizar con SAP: {e}")

    query = db.query(SpecialDemand)
    if active_only:
        query = query.filter(SpecialDemand.is_active == True)
    return query.order_by(SpecialDemand.created_at.desc()).all()


@router.post("/", response_model=SpecialDemandOut, status_code=201)
def create_special_demand(data: SpecialDemandCreate, db: Session = Depends(get_db)):
    """Crea un nuevo registro de demanda especial."""
    demand = SpecialDemand(**data.model_dump())
    db.add(demand)
    db.commit()
    db.refresh(demand)
    return demand


@router.put("/{demand_id}", response_model=SpecialDemandOut)
def update_special_demand(demand_id: int, data: SpecialDemandUpdate, db: Session = Depends(get_db)):
    """Modifica una demanda especial existente."""
    demand = db.query(SpecialDemand).filter(SpecialDemand.id == demand_id).first()
    if not demand:
        raise HTTPException(status_code=404, detail="Demanda especial no encontrada")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(demand, field, value)

    db.commit()
    try:
        sync_special_demands_with_sap(db)
    except Exception as e:
        print(f"⚠️ Error al sincronizar con SAP tras edición: {e}")

    db.refresh(demand)
    return demand


@router.patch("/{demand_id}/toggle", response_model=SpecialDemandOut)
def toggle_special_demand(demand_id: int, db: Session = Depends(get_db)):
    """Activa o desactiva una demanda especial."""
    demand = db.query(SpecialDemand).filter(SpecialDemand.id == demand_id).first()
    if not demand:
        raise HTTPException(status_code=404, detail="Demanda especial no encontrada")

    demand.is_active = not demand.is_active
    db.commit()
    db.refresh(demand)
    return demand


@router.delete("/{demand_id}", status_code=204)
def delete_special_demand(demand_id: int, db: Session = Depends(get_db)):
    """Elimina permanentemente un registro de demanda especial."""
    demand = db.query(SpecialDemand).filter(SpecialDemand.id == demand_id).first()
    if not demand:
        raise HTTPException(status_code=404, detail="Demanda especial no encontrada")

    db.delete(demand)
    db.commit()

