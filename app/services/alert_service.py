"""
Servicio de alertas de inventario.
Monitorea niveles de stock y detecta situaciones críticas:
- Producto por debajo del stock de seguridad.
- Sobre-stock (más del doble del objetivo).
- Consumo cero (producto sin movimiento).
"""

from datetime import datetime, timezone
from sqlalchemy.orm import Session
import pandas as pd

from app.models.db_models import AlertLog, AlertSeverity
from config.settings import forecast_settings


def evaluate_alerts(df: pd.DataFrame, db: Session) -> int:
    """
    Evalúa el DataFrame del pipeline y genera alertas de inventario.

    Args:
        df: DataFrame del pipeline con columnas Stock01, ConsumoPromedio, DiasInventario.
        db: Sesión SQLAlchemy para persistir las alertas.

    Returns:
        Número de alertas generadas.
    """
    target_days = forecast_settings.target_stock_days
    alerts_created = 0

    for _, row in df.iterrows():
        item_code = str(row.get("ItemCode", ""))
        item_name = str(row.get("ItemName", ""))
        stock = float(row.get("Stock01", 0))
        consumption = float(row.get("ConsumoPromedio", 0))
        days_inv = row.get("DiasInventario", None)

        # --- Alerta: Stock bajo (menos de 5 días) ---
        if days_inv is not None and 0 < days_inv < 5:
            alert = AlertLog(
                item_code=item_code,
                item_name=item_name,
                alert_type="low_stock",
                severity=AlertSeverity.HIGH if days_inv < 2 else AlertSeverity.MEDIUM,
                message=(
                    f"Stock crítico: {days_inv:.1f} días de inventario "
                    f"(objetivo: {target_days} días). "
                    f"Stock actual: {stock:.0f}, Consumo diario: {consumption:.1f}"
                ),
                current_stock=stock,
                threshold=consumption * 5,
            )
            db.add(alert)
            alerts_created += 1

        # --- Alerta: Sobre-stock (más del doble del objetivo) ---
        elif days_inv is not None and days_inv > target_days * 2:
            alert = AlertLog(
                item_code=item_code,
                item_name=item_name,
                alert_type="overstock",
                severity=AlertSeverity.LOW,
                message=(
                    f"Sobre-stock: {days_inv:.0f} días de inventario "
                    f"(objetivo: {target_days} días). "
                    f"Stock actual: {stock:.0f}"
                ),
                current_stock=stock,
                threshold=consumption * target_days * 2,
            )
            db.add(alert)
            alerts_created += 1

        # --- Alerta: Sin movimiento ---
        elif consumption == 0 and stock > 0:
            alert = AlertLog(
                item_code=item_code,
                item_name=item_name,
                alert_type="no_movement",
                severity=AlertSeverity.LOW,
                message=(
                    f"Sin consumo en el período analizado. "
                    f"Stock actual: {stock:.0f}"
                ),
                current_stock=stock,
                threshold=0,
            )
            db.add(alert)
            alerts_created += 1

    if alerts_created > 0:
        db.commit()
        print(f"🔔 {alerts_created} alertas de inventario generadas")

    return alerts_created
