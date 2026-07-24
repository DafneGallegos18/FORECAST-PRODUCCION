"""
Rutas API para el módulo de Forecast.
Endpoints para ejecutar el pipeline, listar corridas, ajustar items y aprobar.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional

from app.database import get_db
from app.models.db_models import (
    ForecastRun, ForecastItem, ForecastItemClient, ManualAdjustment, RunStatus, SpecialDemand, ProductShelfLife
)
from app.models.schemas import (
    ForecastRunOut, ForecastRunDetail, ForecastItemOut, ForecastItemClientOut,
    AdjustRequest, ApproveRequest, PipelineConfig,
)
from app.services.data_pipeline import run_pipeline, extract_daily_series
from app.services.forecast_engine import calculate_forecast
from app.services.alert_service import evaluate_alerts
from app.services.special_demand_service import sync_special_demands_with_sap
from config.settings import forecast_settings

router = APIRouter(prefix="/api/forecast", tags=["Forecast"])


from app.services.exclusion_service import apply_exclusions

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
    safety_pct = cfg.shelf_life_safety_pct
    now = datetime.now()

    # 0. Sincronizar consumos de demandas especiales con SAP
    try:
        sync_special_demands_with_sap(db)
    except Exception as e:
        print(f"⚠️ Error al sincronizar demandas especiales con SAP: {e}")

    # 1. Ejecutar pipeline de extracción (trae desglose por cliente)
    df = run_pipeline(db, lookback_days=lookback, target_stock_days=target)

    if df.empty:
        raise HTTPException(status_code=404, detail="No se obtuvieron datos de SAP.")

    # 2. Extraer serie diaria para modelos avanzados
    daily_df = None
    if model_name != "simple_avg":
        try:
            daily_df = extract_daily_series(db, lookback_days=max(lookback, 60))
        except Exception as e:
            print(f"⚠️  No se pudo extraer serie diaria, usando promedio simple: {e}")
            model_name = "simple_avg"

    # 2.5 Cargar catálogo de días de caducidad por producto
    shelf_life_map = {
        ps.item_code: ps.shelf_life_days for ps in db.query(ProductShelfLife).all()
    }

    # 3. Crear la corrida en DB
    run = ForecastRun(
        lookback_days=lookback,
        target_stock_days=target,
        shelf_life_safety_pct=safety_pct,
        status=RunStatus.DRAFT,
    )
    db.add(run)
    db.flush()

    # 4. Agrupar por Producto (ItemCode)
    grouped = df.groupby("ItemCode")
    items_added = 0
    processed_item_codes = set()

    for item_code_val, group in grouped:
        item_code = str(item_code_val)
        processed_item_codes.add(item_code)
        first_row = group.iloc[0]
        
        # Sumar consumos de todos los clientes de este producto
        total_historical_consumption = float(group["ConsumoPromedio"].sum())
        total_consumption = total_historical_consumption
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

        # Evaluación de caducidad y horizonte de cobertura seguro
        shelf_days = shelf_life_map.get(item_code)
        max_safe_days = None
        effective_target = float(target)
        is_batch_optimized = False
        has_expiration_risk = False

        if shelf_days is not None and shelf_days > 0:
            max_safe_days = shelf_days * (safety_pct / 100.0)
            if target > max_safe_days:
                effective_target = max_safe_days
                has_expiration_risk = True
            else:
                # Si el producto tiene buena vida útil (ej. >=60 días) y target es corto, consolidamos
                if shelf_days >= 60 and target < 30:
                    effective_target = min(max_safe_days, 30.0)
                    is_batch_optimized = True

        total_target_consumption = total_consumption * effective_target

        stock = float(first_row.get("Stock01", 0))
        if stock > 0 and total_consumption > 0 and max_safe_days is not None:
            if (stock / total_consumption) > max_safe_days:
                has_expiration_risk = True

        # Obtener demandas especiales activas para este SKU
        special_demands = db.query(SpecialDemand).filter(
            SpecialDemand.item_code == item_code,
            SpecialDemand.is_active == True,
            SpecialDemand.start_date <= now,
            SpecialDemand.end_date >= now
        ).all()
        
        # Sumar el volumen restante de demandas especiales generales (sin cliente)
        general_special_remaining = sum([sd.remaining_qty for sd in special_demands if not sd.card_code])
        client_special_remaining_total = sum([sd.remaining_qty for sd in special_demands if sd.card_code])

        # Necesidad a nivel Producto
        base_need = max(0, total_target_consumption - stock)
        
        # Necesidad total = necesidad base + demandas especiales (generales y de clientes)
        calculated_need_total = base_need + general_special_remaining + client_special_remaining_total

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
            shelf_life_days=shelf_days,
            max_safe_days=max_safe_days,
            effective_target_days=effective_target,
            is_batch_optimized=is_batch_optimized,
            has_expiration_risk=has_expiration_risk,
            model_used=used_model,
            confidence_score=confidence,
        )
        db.add(item)
        db.flush() # Para obtener item.id
        
        processed_clients = set()
        
        # Crear los Hijos (ForecastItemClient) - Clientes con historial
        for _, row in group.iterrows():
            card_code = str(row.get("CardCode", ""))
            if not card_code or card_code == "nan":
                card_code = "GENERAL"
                
            client_consumption_hist = float(row.get("ConsumoPromedio", 0))
            client_committed = float(row.get("Comprometido", 0))
            
            # Escalado proporcional de la necesidad base + demanda especial general
            base_and_general_need = base_need + general_special_remaining
            if total_historical_consumption > 0:
                client_ratio = client_consumption_hist / total_historical_consumption
                client_need = base_and_general_need * client_ratio
                client_consumption = client_consumption_hist * (total_consumption / total_historical_consumption)
            else:
                client_consumption = 0
                client_need = 0
            
            # Sumar demanda especial específica de este cliente
            client_specific_sd = sum([sd.remaining_qty for sd in special_demands if sd.card_code == card_code])
            client_need += client_specific_sd
            
            processed_clients.add(card_code)

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
            
        # Crear Hijos para clientes NUEVOS sin historial que tienen demandas especiales
        for sd in special_demands:
            if sd.card_code and sd.card_code not in processed_clients:
                client = ForecastItemClient(
                    item_id=item.id,
                    card_code=sd.card_code,
                    card_name=sd.card_name or "Cliente Nuevo (Especial)",
                    avg_daily_consumption=0.0,
                    committed_qty=0.0,
                    calculated_need=sd.remaining_qty,
                    final_need=sd.remaining_qty
                )
                db.add(client)
                processed_clients.add(sd.card_code)
            
        items_added += 1

    # 4.5 Procesar Demandas Especiales para PRODUCTOS NUEVOS (sin historial de ventas en SAP)
    all_active_special_demands = db.query(SpecialDemand).filter(
        SpecialDemand.is_active == True,
        SpecialDemand.start_date <= now,
        SpecialDemand.end_date >= now
    ).all()

    new_item_demands = {}
    for sd in all_active_special_demands:
        if sd.item_code not in processed_item_codes:
            if sd.item_code not in new_item_demands:
                new_item_demands[sd.item_code] = []
            new_item_demands[sd.item_code].append(sd)

    for new_item_code, sds in new_item_demands.items():
        stock01 = 0.0
        stock03 = 0.0
        item_name = sds[0].item_name or new_item_code
        unit = "Pza"
        
        try:
            from app.services.sap_connector import sap_connector
            sap_info = sap_connector.query(f"""
                SELECT 
                    T0.ItemCode, T0.ItemName, T0.InvntryUom,
                    CAST(ISNULL(A01.OnHand, 0) AS FLOAT) AS Stock01,
                    CAST(ISNULL(A03.OnHand, 0) AS FLOAT) AS Stock03
                FROM OITM T0
                LEFT JOIN OITW A01 ON T0.ItemCode = A01.ItemCode AND A01.WhsCode = '01'
                LEFT JOIN OITW A03 ON T0.ItemCode = A03.ItemCode AND A03.WhsCode = '03'
                WHERE T0.ItemCode = '{new_item_code}'
            """)
            if not sap_info.empty:
                r = sap_info.iloc[0]
                item_name = str(r.get("ItemName") or item_name)
                unit = str(r.get("InvntryUom") or unit)
                stock01 = float(r.get("Stock01", 0))
                stock03 = float(r.get("Stock03", 0))
        except Exception as e:
            print(f"⚠️ Error al consultar datos SAP para nuevo producto especial {new_item_code}: {e}")

        general_special_remaining = sum([sd.remaining_qty for sd in sds if not sd.card_code])
        client_special_remaining_total = sum([sd.remaining_qty for sd in sds if sd.card_code])
        calculated_need_total = max(0.0, general_special_remaining + client_special_remaining_total - stock01)

        shelf_days = shelf_life_map.get(new_item_code)
        max_safe_days = (shelf_days * (safety_pct / 100.0)) if shelf_days else None

        item = ForecastItem(
            run_id=run.id,
            item_code=new_item_code,
            item_name=item_name,
            unit=unit,
            stock_whs_01=stock01,
            stock_whs_03=stock03,
            avg_daily_consumption=0.0,
            days_of_inventory=None,
            target_inventory_consumption=0.0,
            committed_qty=0.0,
            calculated_need=calculated_need_total,
            general_adjustment=0,
            final_need=calculated_need_total,
            shelf_life_days=shelf_days,
            max_safe_days=max_safe_days,
            effective_target_days=float(target),
            is_batch_optimized=False,
            has_expiration_risk=False,
            model_used="special_demand_only",
            confidence_score=1.0,
        )
        db.add(item)
        db.flush()

        processed_clients = set()
        for sd in sds:
            card_code = sd.card_code or "GENERAL"
            card_name = sd.card_name or ("GENERAL (Todos)" if not sd.card_code else "Cliente Nuevo (Especial)")
            if card_code not in processed_clients:
                client = ForecastItemClient(
                    item_id=item.id,
                    card_code=card_code,
                    card_name=card_name,
                    avg_daily_consumption=0.0,
                    committed_qty=0.0,
                    calculated_need=sd.remaining_qty,
                    final_need=sd.remaining_qty
                )
                db.add(client)
                processed_clients.add(card_code)

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
        shelf_life_safety_pct=run.shelf_life_safety_pct,
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
