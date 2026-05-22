"""
Pipeline de datos: Traducción del código M (Power Query) a Python/Pandas.

Este módulo replica y mejora la lógica de extracción actual:
1. Consulta consumos diarios desde facturas SAP (OINV/INV1).
2. Cruza con inventario por almacén (OITW) y lista de materiales (OITT).
3. Aplica conversiones de unidad (ej. SKU 2115004: cajas → piezas x6).
4. Aplica exclusiones dinámicas (reemplaza las fijas del código M).
5. Calcula días de inventario y necesidades de producción.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session

from app.services.sap_connector import sap_connector
from app.services.exclusion_service import apply_exclusions
from config.settings import forecast_settings


# ── Conversiones de Unidad Especiales ──────────────────────────────
# SKUs donde la cantidad facturada necesita ser convertida.
# Formato: { "ItemCode": (factor_multiplicador, unidad_resultante) }
UNIT_CONVERSIONS = {
    "2115004": (6, "Pieza"),   # Cajas → Piezas (6 piezas por caja)
}


def _build_consumption_query(lookback_days: int) -> str:
    """
    Construye el query SQL que replica el CTE 'ConsumoDiario' del código M.
    Extrae consumos promedio diarios por producto y cliente desde facturas.

    Args:
        lookback_days: Número de días hacia atrás para calcular el promedio.

    Returns:
        Query SQL como string.
    """
    fecha_fin = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    fecha_inicio = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y%m%d")

    # Construir las cláusulas CASE para las conversiones de unidad
    qty_cases = []
    unit_cases = []
    for item_code, (factor, unit) in UNIT_CONVERSIONS.items():
        qty_cases.append(
            f"WHEN T1.ItemCode = '{item_code}' THEN T1.Quantity * {factor}"
        )
        unit_cases.append(
            f"WHEN T1.ItemCode = '{item_code}' THEN '{unit}'"
        )

    qty_case_sql = "\n                    ".join(qty_cases)
    unit_case_sql = "\n                    ".join(unit_cases)

    return f"""
        WITH ConsumoDiario AS (
            SELECT
                T1.ItemCode,
                CASE
                    {unit_case_sql}
                    ELSE T1.unitMsr
                END AS UnidadMedida,
                T0.CardCode,
                T0.CardName,
                CAST(T2.AliasName as nvarchar(max)) AS AliasName,
                T2.GroupCode,
                CAST(T3.GroupName as nvarchar(max)) AS GroupName,
                CAST(T4.SlpName as nvarchar(max)) AS SlpName,
                SUM(
                    CASE
                        {qty_case_sql}
                        ELSE T1.Quantity
                    END
                ) / {lookback_days} AS ConsumoPromedio
            FROM INV1 T1
            INNER JOIN OINV T0 ON T1.DocEntry = T0.DocEntry
            LEFT JOIN OCRD T2 ON T0.CardCode = T2.CardCode
            LEFT JOIN OCRG T3 ON T2.GroupCode = T3.GroupCode
            LEFT JOIN OSLP T4 ON T2.SlpCode = T4.SlpCode
            WHERE T0.DocDate BETWEEN '{fecha_inicio}' AND '{fecha_fin}'
            GROUP BY
                T1.ItemCode,
                CASE
                    {unit_case_sql}
                    ELSE T1.unitMsr
                END,
                T0.CardCode,
                T0.CardName,
                CAST(T2.AliasName as nvarchar(max)),
                T2.GroupCode,
                CAST(T3.GroupName as nvarchar(max)),
                CAST(T4.SlpName as nvarchar(max))
        )

        -- Productos con BOM (lista de materiales)
        SELECT
            OITM.ItemCode,
            OITM.ItemName,
            CD.UnidadMedida,
            ISNULL(Alm01.OnHand, 0) AS Stock01,
            ISNULL(Alm03.OnHand, 0) AS Stock03,
            CD.CardCode,
            CD.CardName,
            CD.AliasName,
            CD.GroupCode,
            CD.GroupName,
            CD.SlpName,
            CD.ConsumoPromedio,
            CASE
                WHEN CD.ConsumoPromedio = 0 THEN NULL
                ELSE ISNULL(Alm01.OnHand, 0) / CD.ConsumoPromedio
            END AS DiasInventario
        FROM OITM
        INNER JOIN OITT BOM ON OITM.ItemCode = BOM.Code
        INNER JOIN ConsumoDiario CD ON OITM.ItemCode = CD.ItemCode
        LEFT JOIN OITW Alm01 ON OITM.ItemCode = Alm01.ItemCode AND Alm01.WhsCode = '01'
        LEFT JOIN OITW Alm03 ON OITM.ItemCode = Alm03.ItemCode AND Alm03.WhsCode = '03'

        UNION ALL

        -- Excepción: SKU 2132004 sin BOM
        SELECT
            OITM.ItemCode,
            OITM.ItemName,
            OITM.InvntryUom AS UnidadMedida,
            ISNULL(Alm01.OnHand, 0) AS Stock01,
            ISNULL(Alm03.OnHand, 0) AS Stock03,
            CD.CardCode,
            CD.CardName,
            CD.AliasName,
            CD.GroupCode,
            CD.GroupName,
            CD.SlpName,
            CD.ConsumoPromedio,
            CASE
                WHEN CD.ConsumoPromedio = 0 THEN NULL
                ELSE ISNULL(Alm01.OnHand, 0) / CD.ConsumoPromedio
            END AS DiasInventario
        FROM OITM
        LEFT JOIN OITW Alm01 ON OITM.ItemCode = Alm01.ItemCode AND Alm01.WhsCode = '01'
        LEFT JOIN OITW Alm03 ON OITM.ItemCode = Alm03.ItemCode AND Alm03.WhsCode = '03'
        LEFT JOIN ConsumoDiario CD ON OITM.ItemCode = CD.ItemCode
        WHERE OITM.ItemCode = '2132004'
    """


def _build_daily_series_query(lookback_days: int) -> str:
    """
    Query para obtener la serie temporal diaria de consumos (para modelos
    avanzados como SES o Holt-Winters que necesitan datos día a día).

    Returns:
        Query SQL con consumos diarios desglosados por fecha y producto.
    """
    fecha_fin = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    fecha_inicio = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y%m%d")

    qty_cases = []
    for item_code, (factor, _) in UNIT_CONVERSIONS.items():
        qty_cases.append(
            f"WHEN T1.ItemCode = '{item_code}' THEN T1.Quantity * {factor}"
        )
    qty_case_sql = "\n                ".join(qty_cases)

    return f"""
        SELECT
            CAST(T0.DocDate AS DATE) AS Fecha,
            T1.ItemCode,
            T0.CardCode,
            T0.CardName,
            CAST(T2.AliasName as nvarchar(max)) AS AliasName,
            T2.GroupCode,
            CAST(T3.GroupName as nvarchar(max)) AS GroupName,
            CAST(T4.SlpName as nvarchar(max)) AS SlpName,
            SUM(
                CASE
                    {qty_case_sql}
                    ELSE T1.Quantity
                END
            ) AS ConsumoTotal
        FROM INV1 T1
        INNER JOIN OINV T0 ON T1.DocEntry = T0.DocEntry
        INNER JOIN OITM ON T1.ItemCode = OITM.ItemCode
        INNER JOIN OITT BOM ON OITM.ItemCode = BOM.Code
        LEFT JOIN OCRD T2 ON T0.CardCode = T2.CardCode
        LEFT JOIN OCRG T3 ON T2.GroupCode = T3.GroupCode
        LEFT JOIN OSLP T4 ON T2.SlpCode = T4.SlpCode
        WHERE T0.DocDate BETWEEN '{fecha_inicio}' AND '{fecha_fin}'
        GROUP BY CAST(T0.DocDate AS DATE), T1.ItemCode, T0.CardCode, T0.CardName, CAST(T2.AliasName as nvarchar(max)), T2.GroupCode, CAST(T3.GroupName as nvarchar(max)), CAST(T4.SlpName as nvarchar(max))
        ORDER BY T1.ItemCode, CAST(T0.DocDate AS DATE)
    """


def extract_sap_data(lookback_days: Optional[int] = None) -> pd.DataFrame:
    """
    Extrae y limpia los datos de SAP. Equivale al paso de extracción
    del código M de Power Query.

    Args:
        lookback_days: Días hacia atrás. Default: configuración .env.

    Returns:
        DataFrame con columnas: ItemCode, ItemName, UnidadMedida,
        Stock01, Stock03, CardCode, CardName, AliasName, GroupCode, GroupName, SlpName, ConsumoPromedio, DiasInventario.
    """
    days = lookback_days or forecast_settings.lookback_days
    query = _build_consumption_query(days)
    df = sap_connector.query(query)

    # Normalizar tipos (equivale al paso TipoCambiado del M code)
    numeric_cols = ["Stock01", "Stock03", "ConsumoPromedio", "DiasInventario"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["ItemCode"] = df["ItemCode"].astype(str).str.strip()
    df["CardCode"] = df["CardCode"].astype(str).str.strip()
    if "AliasName" in df.columns:
        df["AliasName"] = df["AliasName"].fillna("").astype(str).str.strip()
    if "GroupName" in df.columns:
        df["GroupName"] = df["GroupName"].fillna("").astype(str).str.strip()
    if "SlpName" in df.columns:
        df["SlpName"] = df["SlpName"].fillna("").astype(str).str.strip()
    if "GroupCode" in df.columns:
        df["GroupCode"] = pd.to_numeric(df["GroupCode"], errors="coerce").fillna(0).astype(int)

    return df


def extract_daily_series(lookback_days: Optional[int] = None) -> pd.DataFrame:
    """
    Extrae la serie temporal diaria de consumos para modelos avanzados.

    Returns:
        DataFrame con columnas: Fecha, ItemCode, CardCode, CardName, AliasName, GroupCode, GroupName, SlpName, ConsumoTotal.
    """
    days = lookback_days or forecast_settings.lookback_days
    query = _build_daily_series_query(days)
    df = sap_connector.query(query)

    df["Fecha"] = pd.to_datetime(df["Fecha"])
    df["ConsumoTotal"] = pd.to_numeric(df["ConsumoTotal"], errors="coerce").fillna(0)
    df["ItemCode"] = df["ItemCode"].astype(str).str.strip()
    if "AliasName" in df.columns:
        df["AliasName"] = df["AliasName"].fillna("").astype(str).str.strip()
    if "GroupName" in df.columns:
        df["GroupName"] = df["GroupName"].fillna("").astype(str).str.strip()
    if "SlpName" in df.columns:
        df["SlpName"] = df["SlpName"].fillna("").astype(str).str.strip()
    if "GroupCode" in df.columns:
        df["GroupCode"] = pd.to_numeric(df["GroupCode"], errors="coerce").fillna(0).astype(int)

    return df


def extract_committed_orders() -> pd.DataFrame:
    """
    Extrae los pedidos comprometidos (pendientes de entrega) desde SAP.
    """
    query = """
        SELECT
            T1.ItemCode,
            T0.CardCode,
            SUM(T1.OpenQty) AS Comprometido
        FROM RDR1 T1
        INNER JOIN ORDR T0 ON T1.DocEntry = T0.DocEntry
        WHERE T1.LineStatus = 'O'
        GROUP BY T1.ItemCode, T0.CardCode
    """
    df = sap_connector.query(query)
    if not df.empty:
        df["Comprometido"] = pd.to_numeric(df["Comprometido"], errors="coerce").fillna(0)
        df["ItemCode"] = df["ItemCode"].astype(str).str.strip()
        df["CardCode"] = df["CardCode"].astype(str).str.strip()
    return df


def run_pipeline(
    db: Session,
    lookback_days: Optional[int] = None,
    target_stock_days: Optional[int] = None,
) -> pd.DataFrame:
    """
    Pipeline completo: extrae datos de SAP, aplica exclusiones dinámicas
    y calcula necesidades de producción.

    Args:
        db: Sesión SQLAlchemy para leer las exclusiones dinámicas.
        lookback_days: Días de histórico para consumo.
        target_stock_days: Días de inventario objetivo.

    Returns:
        DataFrame final listo para el motor de forecast.
    """
    days = lookback_days or forecast_settings.lookback_days
    target = target_stock_days or forecast_settings.target_stock_days

    # 1. Extraer datos crudos de SAP
    print(f"📦 Extrayendo datos de SAP ({days} días de histórico)...")
    df = extract_sap_data(days)
    print(f"   → {len(df)} registros extraídos")

    # 2. Aplicar exclusiones dinámicas (reemplaza los filtros fijos del M code)
    df = apply_exclusions(df, db)
    print(f"   → {len(df)} registros después de exclusiones")

    # 3. Extraer pedidos comprometidos y unir
    committed_df = extract_committed_orders()
    if not committed_df.empty:
        df = pd.merge(df, committed_df, on=["ItemCode", "CardCode"], how="left")
        df["Comprometido"] = df["Comprometido"].fillna(0)
    else:
        df["Comprometido"] = 0

    # 4. Calcular necesidad de producción básica y Consumo Objetivo
    # NecesidadProduccion = ConsumoObjetivo - StockActual
    df["ConsumoObjetivo"] = df["ConsumoPromedio"] * target
    df["NecesidadCalculada"] = (
        df["ConsumoObjetivo"] - df["Stock01"]
    ).clip(lower=0)

    # 5. Agregar columnas de metadata
    df["ModeloUsado"] = "simple_avg"
    df["ConfianzaScore"] = None

    print(f"✅ Pipeline completado: {len(df)} productos procesados")
    return df
