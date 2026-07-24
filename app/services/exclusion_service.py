"""
Servicio de exclusiones dinámicas.
Reemplaza las exclusiones fijas del código M de Power Query por un sistema
flexible y administrable desde la interfaz web.

Tipos de exclusión soportados:
- card_code: Excluir todas las ventas de un cliente (ej. "C018-1")
- card_item: Excluir un producto para un cliente específico (ej. C056 + 2112028)
- card_name_contains: Excluir clientes cuyo nombre contenga un texto (ej. "EMPLEADO")
- category: Excluir una categoría completa de productos (futuro)
"""

import pandas as pd
from sqlalchemy.orm import Session
from typing import List

from app.models.db_models import Exclusion, ExclusionType


def get_active_exclusions(db: Session) -> List[Exclusion]:
    """Obtiene todas las exclusiones activas de la base de datos local."""
    return db.query(Exclusion).filter(Exclusion.is_active == True).all()


def apply_exclusions(df: pd.DataFrame, db: Session) -> pd.DataFrame:
    """
    Aplica todas las exclusiones activas al DataFrame de consumos de SAP.

    Cada tipo de exclusión genera una máscara booleana que filtra las filas
    que deben ser excluidas. Las máscaras se combinan con OR y se aplican
    de una sola vez para eficiencia.

    Args:
        df: DataFrame con columnas CardCode, CardName, ItemCode.
        db: Sesión SQLAlchemy.

    Returns:
        DataFrame filtrado.
    """
    exclusions = get_active_exclusions(db)

    if not exclusions:
        return df

    # Máscara acumulativa: True = EXCLUIR la fila
    exclude_mask = pd.Series(False, index=df.index)

    for exc in exclusions:
        if exc.exclusion_type == ExclusionType.CARD_CODE:
            # Excluir todas las filas de un CardCode específico
            exclude_mask |= df["CardCode"] == exc.value

        elif exc.exclusion_type == ExclusionType.CARD_ITEM:
            # Excluir combinación específica CardCode + ItemCode
            exclude_mask |= (
                (df["CardCode"] == exc.value)
                & (df["ItemCode"] == str(exc.secondary_value))
            )

        elif exc.exclusion_type == ExclusionType.CARD_NAME_CONTAINS:
            # Excluir clientes cuyo nombre o nombre comercial contiene un texto
            if exc.case_sensitive:
                mask = df["CardName"].str.contains(exc.value, case=True, na=False)
                if "AliasName" in df.columns:
                    mask |= df["AliasName"].str.contains(exc.value, case=True, na=False)
                if "GroupName" in df.columns:
                    mask |= df["GroupName"].str.contains(exc.value, case=True, na=False)
                if "SlpName" in df.columns:
                    mask |= df["SlpName"].str.contains(exc.value, case=True, na=False)
                exclude_mask |= mask
            else:
                mask = df["CardName"].str.contains(exc.value, case=False, na=False)
                if "AliasName" in df.columns:
                    mask |= df["AliasName"].str.contains(exc.value, case=False, na=False)
                if "GroupName" in df.columns:
                    mask |= df["GroupName"].str.contains(exc.value, case=False, na=False)
                if "SlpName" in df.columns:
                    mask |= df["SlpName"].str.contains(exc.value, case=False, na=False)
                exclude_mask |= mask

        elif exc.exclusion_type == ExclusionType.CUSTOMER_GROUP:
            # Excluir clientes por código de grupo
            if "GroupCode" in df.columns:
                try:
                    # El valor de exclusión podría ser un string numérico
                    group_val = int(exc.value)
                    exclude_mask |= df["GroupCode"] == group_val
                except ValueError:
                    pass

        elif exc.exclusion_type == ExclusionType.CATEGORY:
            # Excluir categoría de producto (requiere campo de categoría)
            if "Category" in df.columns:
                if exc.case_sensitive:
                    exclude_mask |= df["Category"] == exc.value
                else:
                    exclude_mask |= df["Category"].str.lower() == exc.value.lower()

        elif exc.exclusion_type == ExclusionType.ITEM_CODE:
            # Excluir todas las filas de un producto/SKU específico
            exclude_mask |= df["ItemCode"] == exc.value

    excluded_count = exclude_mask.sum()
    if excluded_count > 0:
        print(f"   🚫 {excluded_count} registros excluidos por {len(exclusions)} reglas activas")

    return df[~exclude_mask].reset_index(drop=True)


def seed_default_exclusions(db: Session):
    """
    Carga las exclusiones que estaban fijas en el código M de Power Query
    como reglas dinámicas en la base de datos. Solo las inserta si no existen.
    """
    defaults = [
        # Exclusiones por CardCode + ItemCode
        Exclusion(
            exclusion_type=ExclusionType.CARD_ITEM,
            value="C056", secondary_value="2112028",
            description="Exclusión heredada del Excel: C056 + SKU 2112028"
        ),
        Exclusion(
            exclusion_type=ExclusionType.CARD_ITEM,
            value="C093", secondary_value="2113006",
            description="Exclusión heredada del Excel: C093 + SKU 2113006"
        ),
        Exclusion(
            exclusion_type=ExclusionType.CARD_ITEM,
            value="C1329", secondary_value="2130012",
            description="Exclusión heredada del Excel: C1329 + SKU 2130012"
        ),
        # Exclusiones por CardCode completo
        Exclusion(
            exclusion_type=ExclusionType.CARD_CODE,
            value="C018-1",
            description="Exclusión heredada del Excel: Cliente C018-1 completo"
        ),
        Exclusion(
            exclusion_type=ExclusionType.CARD_CODE,
            value="C220",
            description="Exclusión heredada del Excel: Cliente C220 completo"
        ),
        Exclusion(
            exclusion_type=ExclusionType.CARD_CODE,
            value="C1444",
            description="Exclusión heredada del Excel: Cliente C1444 completo"
        ),
        Exclusion(
            exclusion_type=ExclusionType.CARD_CODE,
            value="C794",
            description="Exclusión heredada del Excel: Cliente C794 completo"
        ),
        # Exclusiones de empleados solicitadas por el usuario
        Exclusion(
            exclusion_type=ExclusionType.CARD_NAME_CONTAINS,
            value="empleado",
            case_sensitive=False,
            description="Exclusión de empleados por texto en nombre comercial ('empleado', 'empleados', etc.)"
        ),
        Exclusion(
            exclusion_type=ExclusionType.CUSTOMER_GROUP,
            value="132",
            description="Exclusión del grupo de clientes: Empleados LABEN (GroupCode 132)"
        ),
        # Exclusiones de productos/SKUs de conversión (no fabricados) solicitados por el usuario
        Exclusion(
            exclusion_type=ExclusionType.ITEM_CODE,
            value="2112035",
            description="Exclusión SKU (Conversión): QUESO GOUDA EN BARRA N 2.5KG PV"
        ),
        Exclusion(
            exclusion_type=ExclusionType.ITEM_CODE,
            value="2112104",
            description="Exclusión SKU (Conversión): QUESO MANCHEGO EN BARRA 1 / 400 GR CALII"
        ),
        Exclusion(
            exclusion_type=ExclusionType.ITEM_CODE,
            value="2112105",
            description="Exclusión SKU (Conversión): QUESO CHIHUAHUA EN BARRA 1 / 400 GR CALII"
        ),
        Exclusion(
            exclusion_type=ExclusionType.ITEM_CODE,
            value="2113029",
            description="Exclusión SKU (Conversión): QUESO CHIHUAHUA N RALLADO 2 KG"
        ),
        Exclusion(
            exclusion_type=ExclusionType.ITEM_CODE,
            value="2113032",
            description="Exclusión SKU (Conversión): QUESO ASADERO RALLADO N 2 KG"
        ),
        Exclusion(
            exclusion_type=ExclusionType.ITEM_CODE,
            value="2113058",
            description="Exclusión SKU (Conversión): QUESO MOZZARELLA RALLADO 1 / 300 GR CALII"
        ),
        Exclusion(
            exclusion_type=ExclusionType.ITEM_CODE,
            value="2113059",
            description="Exclusión SKU (Conversión): QUESO MONTEREY JACK RALLADO 1 / 300 GR CALII"
        ),
        Exclusion(
            exclusion_type=ExclusionType.ITEM_CODE,
            value="2113060",
            description="Exclusión SKU (Conversión): QUESO CHIHUAHUA RALLADO 1 / 300 GR CALII"
        ),
        Exclusion(
            exclusion_type=ExclusionType.ITEM_CODE,
            value="2113064",
            description="Exclusión SKU (Conversión): HEB CHAROLA REDONDA JAMON SERRANO 1 / .150 KG"
        ),
        Exclusion(
            exclusion_type=ExclusionType.ITEM_CODE,
            value="2114048",
            description="Exclusión SKU (Conversión): QUESO MANCHEGO REBANADO 1 / 400 GR CALII"
        ),
        Exclusion(
            exclusion_type=ExclusionType.ITEM_CODE,
            value="2114049",
            description="Exclusión SKU (Conversión): QUESO MONTEREY JACK REBANADO 1 / 200 GR CALII"
        ),
        Exclusion(
            exclusion_type=ExclusionType.ITEM_CODE,
            value="2114050",
            description="Exclusión SKU (Conversión): QUESO MUENSTER REBANADO 1 / 200 GR CALII"
        ),
        Exclusion(
            exclusion_type=ExclusionType.ITEM_CODE,
            value="2132004",
            description="Exclusión SKU (Conversión): QUESO PARMESANO REGGIANITO RUEDA 5 KG PV - CMT"
        ),
        Exclusion(
            exclusion_type=ExclusionType.ITEM_CODE,
            value="2132014",
            description="Exclusión SKU (Conversión): QUESO PARMESANO GRANA PADANO DOP 1/2 FORMA 1 / 20 KG PV"
        ),
        Exclusion(
            exclusion_type=ExclusionType.ITEM_CODE,
            value="2134003",
            description="Exclusión SKU (Conversión): QUESO PARMESANO RASURADO 1 / 454 GR - DON FOODS"
        ),
    ]


    added_count = 0
    for exc in defaults:
        query = db.query(Exclusion).filter(
            Exclusion.exclusion_type == exc.exclusion_type,
            Exclusion.value == exc.value
        )
        if exc.secondary_value is not None:
            query = query.filter(Exclusion.secondary_value == exc.secondary_value)
        
        exists = query.first()
        if not exists:
            db.add(exc)
            added_count += 1
            
    if added_count > 0:
        db.commit()
        print(f"✅ {added_count} nuevas exclusiones por defecto cargadas en la base de datos")
    else:
        print("ℹ️  Todas las exclusiones por defecto ya existen en la base de datos")
