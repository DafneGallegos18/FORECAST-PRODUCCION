"""
Rutas API para el módulo de Forecast.
Endpoints para ejecutar el pipeline, listar corridas, ajustar items y aprobar.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional

from app.database import get_db
from app.models.db_models import ForecastRun, ForecastItem, ForecastItemClient, ManualAdjustment, RunStatus
from app.models.schemas import (
    ForecastRunOut, ForecastRunDetail, ForecastItemOut, ForecastItemClientOut,
    AdjustRequest, ApproveRequest, PipelineConfig,
)
from app.services.data_pipeline import run_pipeline, extract_daily_series
from app.services.forecast_engine import calculate_forecast
from app.services.alert_service import evaluate_alerts
from config.settings import forecast_settings

router = APIRouter(prefix="/api/forecast", tags=["Forecast"])


@router.post("/run", response_model=ForecastRunOut)
def execute_forecast(
    config: Optional[PipelineConfig] = None,
    db: Session = Depends(get_db),
):
    """
    Ejecuta una corrida completa de forecast, estructurando padres (SKU) e hijos (Clientes).
    """
    cfg = config or PipelineConfig()
    model_name = cfg.model
    lookback = cfg.lookback_days
    target = cfg.target_stock_days

    # 1. Ejecutar pipeline de extracción (trae desglose por cliente)
    df = run_pipeline(db, lookback_days=lookback, target_stock_days=target)

    if df.empty:
        raise HTTPException(status_code=404, detail="No se obtuvieron datos de SAP.")

    # 2. Extraer serie diaria para modelos avanzados
    daily_df = None
    if model_name != "simple_avg":
        try:
            daily_df = extract_daily_series(lookback_days=max(lookback, 60))
            daily_df = apply_exclusions(daily_df, db)
        except Exception as e:
            print(f"⚠️  No se pudo extraer serie diaria, usando promedio simple: {e}")
            model_name = "simple_avg"

    # 3. Crear la corrida en DB
    run = ForecastRun(
        lookback_days=lookback,
        target_stock_days=target,
        status=RunStatus.DRAFT,
    )
    db.add(run)
    db.flush()

    # 4. Agrupar por Producto (ItemCode)
    grouped = df.groupby("ItemCode")
    items_added = 0

    for item_code_val, group in grouped:
        item_code = str(item_code_val)
        first_row = group.iloc[0]
        
        # Sumar consumos de todos los clientes de este producto
        total_historical_consumption = float(group["ConsumoPromedio"].sum())
        total_consumption = total_historical_consumption
        total_target_consumption = float(group["ConsumoObjetivo"].sum())
        total_committed = float(group["Comprometido"].sum())
        confidence = None
        used_model = model_name

        # Ejecutar modelo matemático a nivel Producto
        if daily_df is not None and not daily_df.empty:
            item_daily = daily_df[daily_df["ItemCode"] == item_code]
            if not item_daily.empty:
                # Agrupar por fecha sumando todos los clientes
                item_series = item_daily.groupby("Fecha")["ConsumoTotal"].sum()
                if len(item_series) >= 4:
                    total_consumption, confidence, used_model = calculate_forecast(
                        item_series, model_name=model_name, lookback_days=lookback
                    )

        # Si el modelo matemático modificó total_consumption, recalculamos total_target_consumption
        total_target_consumption = total_consumption * target

        # Necesidad a nivel Producto
        stock = float(first_row.get("Stock01", 0))
        calculated_need_total = max(0, total_target_consumption - stock)

        # Crear el Padre (ForecastItem)
        item = ForecastItem(
            run_id=run.id,
            item_code=item_code,
            item_name=str(first_row.get("ItemName", "")),
            unit=str(first_row.get("UnidadMedida", "")),
            stock_whs_01=stock,
            stock_whs_03=float(first_row.get("Stock03", 0)),
            avg_daily_consumption=total_consumption,
            days_of_inventory=float(first_row["DiasInventario"]) if first_row.get("DiasInventario") else None,
            target_inventory_consumption=total_target_consumption,
            committed_qty=total_committed,
            calculated_need=calculated_need_total,
            general_adjustment=0,
            final_need=calculated_need_total,
            model_used=used_model,
            confidence_score=confidence,
        )
        db.add(item)
        db.flush() # Para obtener item.id
        
        sum_clients_need = 0
        
        # Crear los Hijos (ForecastItemClient)
        for _, row in group.iterrows():
            card_code = str(row.get("CardCode", ""))
            if not card_code or card_code == "nan":
                card_code = "GENERAL"
                
            client_consumption_hist = float(row.get("ConsumoPromedio", 0))
            client_committed = float(row.get("Comprometido", 0))
            
            # Para mantener la coherencia con el total de consumo proyectado por el modelo,
            # escalamos el consumo promedio del cliente y su necesidad proporcionalmente.
            if total_historical_consumption > 0:
                client_ratio = client_consumption_hist / total_historical_consumption
                client_consumption = client_consumption_hist * (total_consumption / total_historical_consumption)
                client_need = calculated_need_total * client_ratio
            else:
                client_consumption = 0
                client_need = 0

            sum_clients_need += client_need

            client = ForecastItemClient(
                item_id=item.id,
                card_code=card_code,
                card_name=str(row.get("CardName", "Consumo General/No Identificado")),
                avg_daily_consumption=client_consumption,
                committed_qty=client_committed,
                calculated_need=client_need,
                final_need=client_need
            )
            db.add(client)
            
        items_added += 1

    # 5. Generar alertas
    evaluate_alerts(df, db)

    db.commit()
    db.refresh(run)

    print(f"✅ Corrida #{run.id} creada con {items_added} items únicos")
    return ForecastRunOut(
        id=run.id,
        created_at=run.created_at,
        status=run.status,
        lookback_days=run.lookback_days,
        target_stock_days=run.target_stock_days,
        notes=run.notes,
        item_count=items_added,
    )


@router.get("/runs", response_model=list[ForecastRunOut])
def list_runs(limit: int = 20, db: Session = Depends(get_db)):
    runs = db.query(ForecastRun).order_by(ForecastRun.created_at.desc()).limit(limit).all()
    return [
        ForecastRunOut(
            id=r.id,
            created_at=r.created_at,
            status=r.status,
            lookback_days=r.lookback_days,
            target_stock_days=r.target_stock_days,
            notes=r.notes,
            item_count=len(r.items),
        )
        for r in runs
    ]


@router.get("/runs/{run_id}", response_model=ForecastRunDetail)
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(ForecastRun).filter(ForecastRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Corrida no encontrada")
    return run


@router.patch("/items/{item_id}/adjust", response_model=ForecastItemOut)
def adjust_item_general(
    item_id: int,
    request: AdjustRequest,
    db: Session = Depends(get_db),
):
    """
    Ajusta el TOTAL del producto (Padre). 
    Se recalcula el 'general_adjustment' para que cuadre matemáticamente.
    """
    item = db.query(ForecastItem).filter(ForecastItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item no encontrado")

    if item.run.status != RunStatus.DRAFT:
        raise HTTPException(status_code=400, detail="No se pueden editar items de una corrida aprobada")

    adjustment = ManualAdjustment(
        item_id=item.id,
        previous_value=item.final_need,
        new_value=request.new_value,
        reason=request.reason,
    )
    db.add(adjustment)

    # El nuevo general_adjustment es lo que falta para llegar al new_value
    # desde la suma de los clientes.
    sum_clients = sum([c.final_need for c in item.clients])
    item.general_adjustment = request.new_value - sum_clients
    item.final_need = request.new_value

    db.commit()
    db.refresh(item)
    return item


@router.patch("/clients/{client_id}/adjust", response_model=ForecastItemOut)
def adjust_item_client(
    client_id: int,
    request: AdjustRequest,
    db: Session = Depends(get_db),
):
    """
    Ajusta un CLIENTE específico (Hijo).
    Al hacerlo, la necesidad total del producto (Padre) sube o baja en la misma proporción.
    Devuelve el item padre completo actualizado.
    """
    client = db.query(ForecastItemClient).filter(ForecastItemClient.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    item = client.item
    if item.run.status != RunStatus.DRAFT:
        raise HTTPException(status_code=400, detail="No se pueden editar clientes de una corrida aprobada")

    adjustment = ManualAdjustment(
        client_id=client.id,
        previous_value=client.final_need,
        new_value=request.new_value,
        reason=request.reason,
    )
    db.add(adjustment)

    client.adjusted_need = request.new_value
    client.final_need = request.new_value

    # Recalcular el padre
    sum_clients = sum([c.final_need for c in item.clients])
    item.final_need = sum_clients + item.general_adjustment

    db.commit()
    db.refresh(item)
    return item


@router.post("/runs/{run_id}/approve")
def approve_run(
    run_id: int,
    request: ApproveRequest,
    db: Session = Depends(get_db),
):
    run = db.query(ForecastRun).filter(ForecastRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Corrida no encontrada")
    if run.status != RunStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Solo se pueden aprobar corridas en estado 'draft'")

    run.status = RunStatus.APPROVED
    run.approved_at = datetime.now(timezone.utc)
    run.approved_by = request.approved_by
    run.notes = request.notes

    db.commit()
    return {"message": f"Corrida #{run.id} aprobada exitosamente", "status": "approved"}
