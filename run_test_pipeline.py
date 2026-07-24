from dotenv import load_dotenv
load_dotenv()

from app.database import SessionLocal
from app.services.special_demand_service import sync_special_demands_with_sap
from app.services.data_pipeline import run_pipeline, extract_daily_series
from app.models.db_models import ForecastRun, ForecastItem, ForecastItemClient, SpecialDemand, RunStatus
from app.services.forecast_engine import calculate_forecast
from app.services.exclusion_service import apply_exclusions
from app.services.alert_service import evaluate_alerts
from datetime import datetime
import sys

print("🚀 Starting step-by-step manual route execution...")
try:
    db = SessionLocal()
    now = datetime.now()

    print("Step 1: Sincronizando demandas especiales con SAP...")
    sync_special_demands_with_sap(db)
    print("Step 1 completed.")

    print("Step 2: Ejecutando run_pipeline...")
    df = run_pipeline(db, lookback_days=28, target_stock_days=15)
    print(f"Step 2 completed. Dataframe shape: {df.shape}")

    print("Step 2b: Ejecutando extract_daily_series...")
    daily_df = extract_daily_series(db, lookback_days=60)
    print(f"Step 2b completed. Daily df shape: {daily_df.shape}")

    if df.empty:
        print("❌ Error: Dataframe is empty!")
        sys.exit(1)

    print("Step 3: Creando corrida en DB (ForecastRun)...")
    run = ForecastRun(
        lookback_days=28,
        target_stock_days=15,
        status=RunStatus.DRAFT,
    )
    db.add(run)
    db.flush()
    print(f"Step 3 completed. ForecastRun ID: {run.id}")

    print("Step 4: Procesando grupos e insertando ForecastItem y ForecastItemClient...")
    grouped = df.groupby("ItemCode")
    items_added = 0

    for item_code_val, group in grouped:
        item_code = str(item_code_val)
        first_row = group.iloc[0]
        
        total_historical_consumption = float(group["ConsumoPromedio"].sum())
        total_consumption = total_historical_consumption
        total_target_consumption = float(group["ConsumoObjetivo"].sum())
        total_committed = float(group["Comprometido"].sum())
        confidence = None
        used_model = "simple_avg"

        # Obtener demandas especiales activas para este SKU
        special_demands = db.query(SpecialDemand).filter(
            SpecialDemand.item_code == item_code,
            SpecialDemand.is_active == True,
            SpecialDemand.start_date <= now,
            SpecialDemand.end_date >= now
        ).all()
        
        general_special_remaining = sum([sd.remaining_qty for sd in special_demands if not sd.card_code])
        client_special_remaining_total = sum([sd.remaining_qty for sd in special_demands if sd.card_code])

        stock = float(first_row.get("Stock01", 0))
        base_need = max(0, total_target_consumption - stock)
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
            model_used=used_model,
            confidence_score=confidence,
        )
        db.add(item)
        db.flush()
        
        processed_clients = set()
        for _, row in group.iterrows():
            card_code = str(row.get("CardCode", ""))
            if not card_code or card_code == "nan":
                card_code = "GENERAL"
                
            client_consumption_hist = float(row.get("ConsumoPromedio", 0))
            client_committed = float(row.get("Comprometido", 0))
            
            base_and_general_need = base_need + general_special_remaining
            if total_historical_consumption > 0:
                client_ratio = client_consumption_hist / total_historical_consumption
                client_need = base_and_general_need * client_ratio
                client_consumption = client_consumption_hist * (total_consumption / total_historical_consumption)
            else:
                client_consumption = 0
                client_need = 0
            
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

    print(f"Step 4 completed. Processed {items_added} items.")

    print("Step 5: Evaluando alertas...")
    evaluate_alerts(df, db)
    print("Step 5 completed.")

    print("Step 6: Committing transaction...")
    db.commit()
    print("Step 6 completed.")
    print("🎉 Success! All steps completed successfully.")

except BaseException as e:
    print("❌ Error caught:")
    import traceback
    traceback.print_exc()
    sys.exit(1)
