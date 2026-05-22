"""
Modelos ORM para la base de datos local (SQLite).
Estas tablas almacenan todo lo que NO vive en SAP:
corridas de forecast, items calculados, ajustes manuales, exclusiones y alertas.
"""

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, Boolean,
    ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from app.database import Base


# ── Enums ──────────────────────────────────────────────────────────

class RunStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    SENT = "sent"


class ExclusionType(str, enum.Enum):
    """Tipo de regla de exclusión."""
    CARD_CODE = "card_code"              # Excluir un cliente específico
    CARD_ITEM = "card_item"              # Excluir combinación cliente+producto
    CARD_NAME_CONTAINS = "card_name_contains"  # Excluir por texto en nombre
    CATEGORY = "category"                # Excluir categoría completa
    CUSTOMER_GROUP = "customer_group"    # Excluir por grupo de clientes


class AlertSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ── Forecast Run ───────────────────────────────────────────────────

class ForecastRun(Base):
    """Una corrida completa de forecast (ej. la del miércoles 14/may/2026)."""
    __tablename__ = "forecast_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    approved_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    status = Column(SAEnum(RunStatus), default=RunStatus.DRAFT)
    lookback_days = Column(Integer, default=28)
    target_stock_days = Column(Integer, default=15)
    notes = Column(Text, nullable=True)
    approved_by = Column(String(100), nullable=True)

    # Relación con items
    items = relationship("ForecastItem", back_populates="run", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ForecastRun #{self.id} [{self.status.value}] {self.created_at:%Y-%m-%d}>"


# ── Forecast Item ──────────────────────────────────────────────────

class ForecastItem(Base):
    """Detalle de un producto dentro de una corrida de forecast."""
    __tablename__ = "forecast_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("forecast_runs.id"), nullable=False)
    item_code = Column(String(50), nullable=False)
    item_name = Column(String(255), nullable=True)
    unit = Column(String(50), nullable=True)

    # Inventario actual (snapshot al momento del cálculo)
    stock_whs_01 = Column(Float, default=0)
    stock_whs_03 = Column(Float, default=0)

    # Consumo y forecast calculados
    avg_daily_consumption = Column(Float, default=0)
    days_of_inventory = Column(Float, nullable=True)
    target_inventory_consumption = Column(Float, default=0)
    committed_qty = Column(Float, default=0)
    calculated_need = Column(Float, default=0)       # Lo que el modelo sugiere producir
    general_adjustment = Column(Float, default=0)     # Ajuste total del usuario a nivel general
    final_need = Column(Float, default=0)             # Suma de (clientes.final_need) + general_adjustment

    # Metadata del modelo
    model_used = Column(String(50), default="simple_avg")  # simple_avg, wma, ses, holt_winters
    confidence_score = Column(Float, nullable=True)

    # Dimensiones de análisis (Opcional a nivel padre)
    channel = Column(String(100), nullable=True)      # Canal de venta

    # Relación
    run = relationship("ForecastRun", back_populates="items")
    clients = relationship("ForecastItemClient", back_populates="item", cascade="all, delete-orphan")
    adjustments = relationship("ManualAdjustment", back_populates="item", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ForecastItem {self.item_code} need={self.final_need}>"


# ── Forecast Item Client (Hijo) ────────────────────────────────────

class ForecastItemClient(Base):
    """Desglose de la necesidad de producción por cliente para un producto."""
    __tablename__ = "forecast_item_clients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(Integer, ForeignKey("forecast_items.id"), nullable=False)
    
    card_code = Column(String(50), nullable=False)
    card_name = Column(String(255), nullable=True)
    
    avg_daily_consumption = Column(Float, default=0)
    committed_qty = Column(Float, default=0)
    calculated_need = Column(Float, default=0)
    adjusted_need = Column(Float, nullable=True)
    final_need = Column(Float, default=0)

    # Relación
    item = relationship("ForecastItem", back_populates="clients")
    adjustments = relationship("ManualAdjustment", back_populates="client", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ForecastItemClient {self.card_code} need={self.final_need}>"


# ── Manual Adjustment (Auditoría) ──────────────────────────────────

class ManualAdjustment(Base):
    """
    Registro de auditoría cada vez que un usuario modifica manualmente
    un valor calculado por el sistema.
    """
    __tablename__ = "manual_adjustments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(Integer, ForeignKey("forecast_items.id"), nullable=True)
    client_id = Column(Integer, ForeignKey("forecast_item_clients.id"), nullable=True)
    adjusted_by = Column(String(100), default="usuario")
    adjusted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    previous_value = Column(Float, nullable=False)
    new_value = Column(Float, nullable=False)
    reason = Column(Text, nullable=True)

    # Relación
    item = relationship("ForecastItem", back_populates="adjustments")
    client = relationship("ForecastItemClient", back_populates="adjustments")


# ── Exclusiones Dinámicas ──────────────────────────────────────────

class Exclusion(Base):
    """
    Reglas de exclusión dinámicas para filtrar datos del forecast.
    Reemplazan las exclusiones fijas del código M de Power Query.
    """
    __tablename__ = "exclusions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    exclusion_type = Column(SAEnum(ExclusionType), nullable=False)
    value = Column(String(255), nullable=False)           # Valor a filtrar (ej. "C056")
    secondary_value = Column(String(255), nullable=True)  # Segundo valor (ej. ItemCode para card_item)
    case_sensitive = Column(Boolean, default=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Exclusion [{self.exclusion_type.value}] {self.value}>"


# ── Alert Log ──────────────────────────────────────────────────────

class AlertLog(Base):
    """Registro de alertas de inventario detectadas por el sistema."""
    __tablename__ = "alert_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    item_code = Column(String(50), nullable=False)
    item_name = Column(String(255), nullable=True)
    alert_type = Column(String(50), nullable=False)       # "low_stock", "overstock", "anomaly"
    severity = Column(SAEnum(AlertSeverity), default=AlertSeverity.MEDIUM)
    message = Column(Text, nullable=False)
    current_stock = Column(Float, nullable=True)
    threshold = Column(Float, nullable=True)
    acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(String(100), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
