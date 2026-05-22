"""
Motor de Cálculo de Forecast.

Implementa múltiples modelos matemáticos para reemplazar el promedio
simple de 28 días del Excel actual:

1. simple_avg   — Promedio simple (réplica del Excel, para validación).
2. wma          — Promedio Móvil Ponderado (más peso a días recientes).
3. ses          — Suavizado Exponencial Simple (reacciona a cambios de tendencia).
4. holt_winters — Holt-Winters (captura tendencia + estacionalidad semanal).

Incluye detección de anomalías (Z-Score) para suavizar picos atípicos
antes de alimentar los modelos.
"""

import pandas as pd
import numpy as np
from typing import Optional, Tuple
from statsmodels.tsa.holtwinters import ExponentialSmoothing, SimpleExpSmoothing


# ── Detección de Anomalías ─────────────────────────────────────────

def detect_anomalies_zscore(
    series: pd.Series,
    threshold: float = 2.5
) -> pd.Series:
    """
    Detecta valores atípicos usando Z-Score.
    Los valores fuera del umbral se reemplazan por la mediana.

    Args:
        series: Serie temporal de consumos diarios.
        threshold: Umbral de Z-Score (default 2.5 = ~99% de confianza).

    Returns:
        Serie limpia con anomalías suavizadas.
    """
    if len(series) < 3 or series.std() == 0:
        return series

    z_scores = np.abs((series - series.mean()) / series.std())
    cleaned = series.copy()
    median_val = series.median()
    cleaned[z_scores > threshold] = median_val

    anomaly_count = (z_scores > threshold).sum()
    if anomaly_count > 0:
        print(f"      ⚠️  {anomaly_count} anomalía(s) detectada(s) y suavizada(s)")

    return cleaned


def detect_anomalies_iqr(
    series: pd.Series,
    factor: float = 1.5
) -> pd.Series:
    """
    Detecta valores atípicos usando el Rango Intercuartílico (IQR).
    Más robusto que Z-Score para distribuciones no normales.
    """
    if len(series) < 4:
        return series

    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - factor * iqr
    upper = q3 + factor * iqr

    cleaned = series.copy()
    median_val = series.median()
    mask = (cleaned < lower) | (cleaned > upper)
    cleaned[mask] = median_val

    return cleaned


# ── Modelos de Forecast ────────────────────────────────────────────

def forecast_simple_avg(
    daily_series: pd.Series,
    lookback_days: int = 28
) -> Tuple[float, Optional[float]]:
    """
    Promedio simple — réplica exacta del Excel actual.
    Útil para validación cruzada.

    Returns:
        (consumo_promedio_diario, confidence_score)
    """
    recent = daily_series.tail(lookback_days)
    avg = recent.mean() if len(recent) > 0 else 0.0
    return float(avg), None


def forecast_wma(
    daily_series: pd.Series,
    lookback_days: int = 28,
    recent_weight: float = 0.6
) -> Tuple[float, Optional[float]]:
    """
    Promedio Móvil Ponderado (Weighted Moving Average).
    Divide el período en dos: la mitad reciente recibe más peso.

    Args:
        recent_weight: Peso de la mitad más reciente (0.6 = 60%).

    Returns:
        (consumo_promedio_diario, confidence_score)
    """
    recent = daily_series.tail(lookback_days)
    if len(recent) < 4:
        return forecast_simple_avg(daily_series, lookback_days)

    mid = len(recent) // 2
    old_half = recent.iloc[:mid]
    new_half = recent.iloc[mid:]

    old_weight = 1 - recent_weight
    weighted_avg = (
        old_half.mean() * old_weight + new_half.mean() * recent_weight
    )

    # Confidence: qué tan estable es la demanda semanal (1 - coeficiente de variación semanal)
    if isinstance(recent.index, pd.DatetimeIndex):
        weekly_series = recent.resample('7D').sum()
    else:
        weekly_series = recent.groupby(np.arange(len(recent)) // 7).sum()

    weekly_mean = weekly_series.mean()
    if weekly_mean > 0:
        weekly_std = weekly_series.std()
        if pd.isna(weekly_std):
            weekly_std = 0.0
        cv = weekly_std / weekly_mean
    else:
        cv = 1.0

    confidence = max(0.0, min(1.0, 1.0 - cv))
    if pd.isna(confidence):
        confidence = 0.0

    return float(weighted_avg), float(confidence)


def forecast_ses(
    daily_series: pd.Series,
    lookback_days: int = 28,
    alpha: Optional[float] = None
) -> Tuple[float, Optional[float]]:
    """
    Suavizado Exponencial Simple (SES).
    Da más peso exponencial a las observaciones recientes.

    Args:
        alpha: Factor de suavizado (0-1). Si None, se optimiza automáticamente.

    Returns:
        (consumo_promedio_diario, confidence_score)
    """
    recent = daily_series.tail(lookback_days)
    if len(recent) < 4:
        return forecast_simple_avg(daily_series, lookback_days)

    try:
        if alpha:
            model = SimpleExpSmoothing(recent.values).fit(
                smoothing_level=alpha, optimized=False
            )
        else:
            model = SimpleExpSmoothing(recent.values).fit(optimized=True)

        forecast_value = model.forecast(1)[0]

        # Confidence basada en el error residual acumulado semanalmente
        residuals = model.resid
        if isinstance(recent, pd.Series):
            res_series = pd.Series(residuals, index=recent.index)
        else:
            res_series = pd.Series(residuals)

        if isinstance(recent.index, pd.DatetimeIndex):
            weekly_recent = recent.resample('7D').sum()
            weekly_mae = res_series.abs().resample('7D').sum()
        else:
            group_idx = np.arange(len(recent)) // 7
            weekly_recent = recent.groupby(group_idx).sum()
            weekly_mae = res_series.abs().groupby(group_idx).sum()

        mean_weekly = weekly_recent.mean()
        mae_weekly = weekly_mae.mean()

        if pd.isna(mean_weekly) or pd.isna(mae_weekly) or mean_weekly <= 0:
            confidence = 0.0
        else:
            confidence = max(0.0, min(1.0, 1.0 - (mae_weekly / mean_weekly)))
            if pd.isna(confidence):
                confidence = 0.0

        return float(max(0, forecast_value)), float(confidence)
    except Exception:
        return forecast_wma(daily_series, lookback_days)


def forecast_holt_winters(
    daily_series: pd.Series,
    lookback_days: int = 28,
    seasonal_periods: int = 7
) -> Tuple[float, Optional[float]]:
    """
    Holt-Winters con estacionalidad semanal.
    Captura tendencia y patrones cíclicos (ej. más consumo los lunes).

    Args:
        seasonal_periods: Ciclo estacional (7 = semanal).

    Returns:
        (consumo_promedio_diario, confidence_score)
    """
    recent = daily_series.tail(max(lookback_days, seasonal_periods * 3))
    if len(recent) < seasonal_periods * 2:
        return forecast_ses(daily_series, lookback_days)

    try:
        model = ExponentialSmoothing(
            recent.values,
            trend="add",
            seasonal="add",
            seasonal_periods=seasonal_periods,
        ).fit(optimized=True)

        forecast_value = model.forecast(1)[0]

        # Confidence basada en el error residual acumulado semanalmente
        residuals = model.resid
        if isinstance(recent, pd.Series):
            res_series = pd.Series(residuals, index=recent.index)
        else:
            res_series = pd.Series(residuals)

        if isinstance(recent.index, pd.DatetimeIndex):
            weekly_recent = recent.resample('7D').sum()
            weekly_mae = res_series.abs().resample('7D').sum()
        else:
            group_idx = np.arange(len(recent)) // 7
            weekly_recent = recent.groupby(group_idx).sum()
            weekly_mae = res_series.abs().groupby(group_idx).sum()

        mean_weekly = weekly_recent.mean()
        mae_weekly = weekly_mae.mean()

        if pd.isna(mean_weekly) or pd.isna(mae_weekly) or mean_weekly <= 0:
            confidence = 0.0
        else:
            confidence = max(0.0, min(1.0, 1.0 - (mae_weekly / mean_weekly)))
            if pd.isna(confidence):
                confidence = 0.0

        return float(max(0, forecast_value)), float(confidence)
    except Exception:
        return forecast_ses(daily_series, lookback_days)


# ── Dispatcher ─────────────────────────────────────────────────────

MODELS = {
    "simple_avg": forecast_simple_avg,
    "wma": forecast_wma,
    "ses": forecast_ses,
    "holt_winters": forecast_holt_winters,
}


def calculate_forecast(
    daily_series: pd.Series,
    model_name: str = "ses",
    lookback_days: int = 28,
    clean_anomalies: bool = True,
) -> Tuple[float, Optional[float], str]:
    """
    Punto de entrada principal del motor de forecast.
    Limpia anomalías y ejecuta el modelo seleccionado.

    Args:
        daily_series: Serie temporal de consumo diario de un producto.
        model_name: Nombre del modelo a usar.
        lookback_days: Días de histórico.
        clean_anomalies: Si True, suaviza picos atípicos antes del cálculo.

    Returns:
        (consumo_promedio_diario, confidence_score, model_name_used)
    """
    if clean_anomalies and len(daily_series) > 5:
        daily_series = detect_anomalies_zscore(daily_series)

    model_fn = MODELS.get(model_name, forecast_ses)

    try:
        avg_consumption, confidence = model_fn(daily_series, lookback_days)
        return avg_consumption, confidence, model_name
    except Exception as e:
        print(f"      ⚠️  Modelo '{model_name}' falló, usando simple_avg: {e}")
        avg, conf = forecast_simple_avg(daily_series, lookback_days)
        return avg, conf, "simple_avg"
