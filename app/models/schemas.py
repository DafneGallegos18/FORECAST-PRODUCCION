"""
Schemas Pydantic para validación de requests/responses de la API.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.db_models import RunStatus, ExclusionType, AlertSeverity


# ── Exclusiones ────────────────────────────────────────────────────

class ExclusionCreate(BaseModel):
    exclusion_type: ExclusionType
    value: str
    secondary_value: Optional[str] = None
    case_sensitive: bool = False
    description: Optional[str] = None


class ExclusionOut(ExclusionCreate):
    id: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Forecast ───────────────────────────────────────────────────────

class ForecastItemClientOut(BaseModel):
    id: int
    card_code: str
    card_name: Optional[str]
    avg_daily_consumption: float
    committed_qty: float
    calculated_need: float
    adjusted_need: Optional[float]
    final_need: float

    model_config = {"from_attributes": True}


class ForecastItemOut(BaseModel):
    id: int
    item_code: str
    item_name: Optional[str]
    unit: Optional[str]
    stock_whs_01: float
    stock_whs_03: float
    avg_daily_consumption: float
    days_of_inventory: Optional[float]
    target_inventory_consumption: float
    committed_qty: float
    calculated_need: float
    general_adjustment: float
    final_need: float
    shelf_life_days: Optional[float] = None
    max_safe_days: Optional[float] = None
    effective_target_days: Optional[float] = None
    is_batch_optimized: bool = False
    has_expiration_risk: bool = False
    model_used: str
    confidence_score: Optional[float]
    channel: Optional[str]
    clients: List[ForecastItemClientOut] = []

    model_config = {"from_attributes": True}


class ForecastRunOut(BaseModel):
    id: int
    created_at: datetime
    status: RunStatus
    lookback_days: int
    target_stock_days: int
    shelf_life_safety_pct: float = 50.0
    notes: Optional[str]
    item_count: int = 0

    model_config = {"from_attributes": True}


class ForecastRunDetail(ForecastRunOut):
    items: List[ForecastItemOut]


class AdjustRequest(BaseModel):
    """Request para ajustar manualmente un item del forecast."""
    new_value: float = Field(ge=0)
    reason: Optional[str] = None


class ApproveRequest(BaseModel):
    """Request para aprobar una corrida de forecast."""
    approved_by: str = "usuario"
    notes: Optional[str] = None


# ── Alertas ────────────────────────────────────────────────────────

class AlertOut(BaseModel):
    id: int
    created_at: datetime
    item_code: str
    item_name: Optional[str]
    alert_type: str
    severity: AlertSeverity
    message: str
    current_stock: Optional[float]
    threshold: Optional[float]
    acknowledged: bool

    model_config = {"from_attributes": True}


# ── Pipeline Config ────────────────────────────────────────────────

class PipelineConfig(BaseModel):
    """Configuración para ejecutar el pipeline de datos."""
    lookback_days: int = Field(default=28, ge=7, le=365)
    target_stock_days: int = Field(default=15, ge=1, le=90)
    shelf_life_safety_pct: float = Field(default=50.0, ge=10.0, le=100.0)
    model: str = Field(default="ses", pattern="^(simple_avg|wma|ses|holt_winters)$")


# ── Demandas Especiales ────────────────────────────────────────────

class SpecialDemandCreate(BaseModel):
    item_code: str
    item_name: Optional[str] = None
    card_code: Optional[str] = None
    card_name: Optional[str] = None
    quantity: float
    start_date: datetime
    end_date: datetime
    reason: Optional[str] = None


class SpecialDemandUpdate(BaseModel):
    item_code: Optional[str] = None
    item_name: Optional[str] = None
    card_code: Optional[str] = None
    card_name: Optional[str] = None
    quantity: Optional[float] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    reason: Optional[str] = None
    is_active: Optional[bool] = None


class SpecialDemandOut(SpecialDemandCreate):
    id: int
    consumed_qty: float
    remaining_qty: float
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}

