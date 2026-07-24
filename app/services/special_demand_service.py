"""
Servicio para gestionar y sincronizar demandas especiales con SAP.
Cruza la cantidad programada contra las ventas reales registradas en SAP
desde la fecha de inicio del evento para evitar duplicados en el forecast.
"""

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.db_models import SpecialDemand
from app.services.sap_connector import sap_connector
from app.services.data_pipeline import UNIT_CONVERSIONS

def sync_special_demands_with_sap(db: Session):
    """
    Actualiza la cantidad consumida de todas las demandas especiales activas.
    Busca facturas reales en SAP B1 desde la fecha de inicio del evento especial.
    """
    now = datetime.now()
    
    # Obtener demandas especiales activas en la fecha actual
    active_demands = db.query(SpecialDemand).filter(
        SpecialDemand.is_active == True,
        SpecialDemand.start_date <= now,
        SpecialDemand.end_date >= now
    ).all()
    
    if not active_demands:
        return
        
    print(f"🔄 Sincronizando {len(active_demands)} demanda(s) especial(es) con SAP B1...")
    
    for demand in active_demands:
        start_str = demand.start_date.strftime("%Y%m%d")
        end_str = now.strftime("%Y%m%d")
        
        # Filtro de cliente opcional
        client_filter = ""
        if demand.card_code:
            client_filter = f"AND T0.CardCode = '{demand.card_code}'"
            
        # Determinar el factor de conversión de unidad si existe
        factor = 1.0
        if demand.item_code in UNIT_CONVERSIONS:
            factor = UNIT_CONVERSIONS[demand.item_code][0]
            
        query = f"""
            SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;
            SELECT CAST(SUM(T1.Quantity) AS FLOAT) AS TotalQty
            FROM INV1 T1
            INNER JOIN OINV T0 ON T1.DocEntry = T0.DocEntry
            WHERE T1.ItemCode = '{demand.item_code}'
              AND T0.DocDate BETWEEN '{start_str}' AND '{end_str}'
              {client_filter}
        """
        
        try:
            df = sap_connector.query(query)
            if not df.empty and df.iloc[0]["TotalQty"] is not None:
                # Aplicar conversión de unidades y guardar
                total_sold = float(df.iloc[0]["TotalQty"]) * factor
                # Consumido no puede superar la cantidad programada originalmente
                demand.consumed_qty = min(demand.quantity, total_sold)
                print(f"   → SKU {demand.item_code} (Cliente: {demand.card_code or 'Todos'}): Programado={demand.quantity}, Consumido={demand.consumed_qty}, Pendiente={demand.remaining_qty}")
            else:
                demand.consumed_qty = 0.0
        except Exception as e:
            print(f"   ⚠️ Error al sincronizar SKU {demand.item_code}: {e}")
            
    db.commit()
