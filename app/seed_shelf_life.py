"""
Script de siembra e inicialización de la tabla product_shelf_life.
Pobla los días promedio de caducidad (vida útil) de los SKUs.
"""

import os
import sys

# Asegurar importación de app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import engine, Base, SessionLocal
from app.models.db_models import ProductShelfLife

SHELF_LIFE_DATA = [
    {"item_code": "2113053", "item_name": "QUESO MOZZARELLA RALLADO 1 / 2.3 KG HEB ALIMENTOS PREPARADOS", "shelf_life_days": 95},
    {"item_code": "2115012", "item_name": "QUESO MEZCLA DE LA CASA RALLADO MEAT AND EAT 1 / 2.3 KG - HEB", "shelf_life_days": 95},
    {"item_code": "2113075", "item_name": "QUESO MUENSTER RALLADO **TP** 1 / 2.3 KG", "shelf_life_days": 91},
    {"item_code": "2113079", "item_name": "QUESO MEZCLA MEXICANA RALLADO 1 / 2.3 KG", "shelf_life_days": 91},
    {"item_code": "2115008", "item_name": "QUESO MIX PARA PIZZA 1 / 2.3 KG", "shelf_life_days": 91},
    {"item_code": "2115004", "item_name": "QUESO PDP DON DOMENICO RALLADO 1 / 2.3 KG", "shelf_life_days": 87},
    {"item_code": "2113068", "item_name": "QUESO GOUDA HEB RALLADO 1 / 2.3 KG", "shelf_life_days": 85},
    {"item_code": "2113012", "item_name": "QUESO MONTEREY JACK RALLADO 1 / 2.3 KG", "shelf_life_days": 82},
    {"item_code": "2115010", "item_name": "QUESO PARA PIZZA 1 / 2.3KG - DON DOMENICO", "shelf_life_days": 80},
    {"item_code": "2116011", "item_name": "STRING CHEESE HEB 1 / .567 KG", "shelf_life_days": 78},
    {"item_code": "2113024", "item_name": "QUESO MANCHEGO RALLADO 1 / 2.3 KG", "shelf_life_days": 73},
    {"item_code": "2116010", "item_name": "STRING CHEESE HEB 1 / .454 KG", "shelf_life_days": 72},
    {"item_code": "2113006", "item_name": "QUESO CHEDDAR RALLADO 2.27 KG", "shelf_life_days": 70},
    {"item_code": "2134002", "item_name": "QUESO PARMESANO RASURADO 1/454 GR HEB", "shelf_life_days": 70},
    {"item_code": "2122079", "item_name": "QUESO EDAM CUÑA DON DOMINGO 1 KG PV", "shelf_life_days": 69},
    {"item_code": "2113010", "item_name": "QUESO MUENSTER RALLADO 1 / 2.3 KG", "shelf_life_days": 68},
    {"item_code": "2116009", "item_name": "STRING CHEESE HEB 1 / .277 KG", "shelf_life_days": 68},
    {"item_code": "2117016", "item_name": "QUESO CHEDDAR BOTANERO HEB 1 / 300 GR", "shelf_life_days": 68},
    {"item_code": "2134003", "item_name": "QUESO PARMESANO RASURADO 1 / 454 GR - DON FOODS", "shelf_life_days": 68},
    {"item_code": "2114038", "item_name": "QUESO CHEDDAR REBANADO 1 / 400 GR - DON FOODS", "shelf_life_days": 67},
    {"item_code": "2114039", "item_name": "QUESO MUENSTER REBANADO 1 / 400 GR - DON FOODS", "shelf_life_days": 67},
    {"item_code": "2114041", "item_name": "QUESOS REBANADOS PARA TAPAS 4 SABORES 1 / 400 KG (PARTY TRAY)", "shelf_life_days": 67},
    {"item_code": "2117018", "item_name": "QUESO ASADERO BOTANERO HEB 1 / 300 GR", "shelf_life_days": 67},
    {"item_code": "2117019", "item_name": "QUESO MONTEREY JACK BOTANERO HEB 1 / 300 GR", "shelf_life_days": 67},
    {"item_code": "2117020", "item_name": "QUESO CHEDDAR MADURADO BOTANERO HEB 1 / 300 GR", "shelf_life_days": 67},
    {"item_code": "2117024", "item_name": "QUESO MOZZARELLA CUBICADO BOTANERO 1 /.300 KG - HEB", "shelf_life_days": 67},
    {"item_code": "2134004", "item_name": "QUESO PARMESANO REGGIANITO RALLADO 1 / .300 KG - HCF", "shelf_life_days": 67},
    {"item_code": "2134005", "item_name": "PARMESANO REGGIANITO CUÑA H.C.F 1/300GR", "shelf_life_days": 67},
    {"item_code": "2113073", "item_name": "QUESO FIESTA BLEND RALLADO 1 / .454 KG - HEB", "shelf_life_days": 66},
    {"item_code": "2113078", "item_name": "QUESO MEZCLA MEXICANA RALLADO 1 / .300 KG - HCF HILL COUNTRY", "shelf_life_days": 66},
    {"item_code": "2113092", "item_name": "QUESO MUENSTER RALLADO 1 / .454 KG HEB", "shelf_life_days": 66},
    {"item_code": "2113093", "item_name": "QUESO MONTEREY JACK RALLADO REDUCIDO EN GRASA 1 /.250 KG DD", "shelf_life_days": 66},
    {"item_code": "2113096", "item_name": "QUESO MOZZARELLA RALLADO REDUCIDO EN GRASA 1 /.250 KG DD", "shelf_life_days": 66},
    {"item_code": "2117017", "item_name": "QUESO MUENSTER BOTANERO HEB 1 / 300 GR", "shelf_life_days": 66},
    {"item_code": "2414004", "item_name": "JAMON SERRANO REBANADO 1 / .300 KG", "shelf_life_days": 66},
    {"item_code": "2113094", "item_name": "QUESO CHEDDAR RALLADO REDUCIDO EN GRASA 1 /.250 KG DD", "shelf_life_days": 65},
    {"item_code": "2113062", "item_name": "QUESO MOZZARELLA TRADICIONAL ITALIAN PASTA FILATA RALLADO 1 / 227 GR HEB", "shelf_life_days": 59},
    {"item_code": "2113061", "item_name": "QUESO MOZZARELLA TRADICIONAL ITALIAN PASTA FILATA RALLADO 1 / 454 GR HEB", "shelf_life_days": 58},
    {"item_code": "2114059", "item_name": "QUESO MANCHEGO REBANADO MOLLETERO 1 / .250 KG DON DOMINGO", "shelf_life_days": 52},
    {"item_code": "2123009", "item_name": "QUESO BLUE CHEESE DESMIGADO POINT REYES 1 / .113 KG", "shelf_life_days": 52},
    {"item_code": "2113047", "item_name": "QUESO CHEDDAR MADURADO RALLADO 1 / 450 GR", "shelf_life_days": 50},
    {"item_code": "2114044", "item_name": "QUESO GOUDA REBANADO (1 CM) 1 / 2 KG", "shelf_life_days": 48},
    {"item_code": "2117015", "item_name": "QUESOS BOTANEROS 4 SABORES 1 / 400 GR - HEB", "shelf_life_days": 48},
    {"item_code": "2117025", "item_name": "QUESOS BOTANEROS 4 SABORES VERSION 2 1 / 400 GR - HEB", "shelf_life_days": 48},
    {"item_code": "2112104", "item_name": "QUESO MANCHEGO EN BARRA 1 / 400 GR CALI", "shelf_life_days": 47},
    {"item_code": "2114049", "item_name": "QUESO MONTEREY JACK REBANADO 1 / 200 GR CALII", "shelf_life_days": 47},
    {"item_code": "2114050", "item_name": "QUESO MUENSTER REBANADO 1 / 200 GR CALII", "shelf_life_days": 47},
    {"item_code": "2113058", "item_name": "QUESO MOZZARELLA RALLADO 1 /300 GR CALII", "shelf_life_days": 46},
    {"item_code": "2113059", "item_name": "QUESO MONTEREY JACK RALLADO 1 /300 GR CALII", "shelf_life_days": 46},
    {"item_code": "2113060", "item_name": "QUESO CHIHUAHUA RALLADO 1 /300 GR CALII", "shelf_life_days": 46},
    {"item_code": "2113064", "item_name": "HEB CHAROLA REDONDA JAMON SERRANO 1 / .150 KG", "shelf_life_days": 46},
    {"item_code": "2113071", "item_name": "QUESO MOZZARELLA RALLADO 1 / .300 KG - DON DOMINGO", "shelf_life_days": 46},
    {"item_code": "2113077", "item_name": "QUESO MEZCLA MEXICANA RALLADO 1 / .900 KG - HCF", "shelf_life_days": 46},
    {"item_code": "2114056", "item_name": "QUESO GOUDA REBANADO 20 GR 1 / 2 KG", "shelf_life_days": 46},
    {"item_code": "2130012", "item_name": "QUESO PARMESANO EN POLVO 1 / 2.3 KG", "shelf_life_days": 46},
    {"item_code": "2113072", "item_name": "QUESO MEZCLA MEXICANA RALLADO 1 / .900 KG - DON DOMINGO", "shelf_life_days": 45},
    {"item_code": "2114008", "item_name": "QUESO MONTEREY JACK REBANADO 2 KG", "shelf_life_days": 38},
    {"item_code": "2119003", "item_name": "QUESO CREMA PREPARADO CON ALCACHOFAS 1 /300 GR HEB", "shelf_life_days": 35},
    {"item_code": "2114003", "item_name": "QUESO CHEDDAR REBANADO 1/2 KG", "shelf_life_days": 31},
    {"item_code": "2114021", "item_name": "QUESO QUESADILLA 30 / 50 GR PV", "shelf_life_days": 31},
    {"item_code": "2133004", "item_name": "QUESO PARMESANO RALLADO 1 / 2.3 KG - LFS", "shelf_life_days": 31},
    {"item_code": "2114045", "item_name": "QUESO CHEDDAR REBANADO (REB 30 GRS) 1 / 2 KG", "shelf_life_days": 30},
    {"item_code": "2112015", "item_name": "QUESO MONTEREY JACK EN BARRA 2.3 KG PV", "shelf_life_days": 29},
    {"item_code": "2112016", "item_name": "QUESO PEPPER JACK - JALAPEÑO EN BARRA 2.3 KG PV", "shelf_life_days": 29},
    {"item_code": "2112088", "item_name": "QUESO CHEDDAR BLANCO BARRA 1 / 2.3 KG PV", "shelf_life_days": 29},
    {"item_code": "2112139", "item_name": "QUESO GOUDA EN BARRA JGF 1 / 2.4 KG PV", "shelf_life_days": 29},
    {"item_code": "2113005", "item_name": "QUESO MARBLED JACK (MIXTO) RALLADO 2.3 KG", "shelf_life_days": 29},
    {"item_code": "2113035", "item_name": "QUESO GOUDA RALLADO 1 / 2.3 KG", "shelf_life_days": 29},
    {"item_code": "2113038", "item_name": "QUESO SUIZO MAASDAM GRUYERE RALLADO 2.3 KG", "shelf_life_days": 29},
    {"item_code": "2114004", "item_name": "QUESO GOUDA REBANADO 1 / 2 KG", "shelf_life_days": 29},
    {"item_code": "2114006", "item_name": "QUESO MANCHEGO REBANADO 2 KG", "shelf_life_days": 29},
    {"item_code": "2114047", "item_name": "QUESO MUENSTER REBANADO (REB 30 GRS) 1 / 2 KG", "shelf_life_days": 29},
    {"item_code": "2112010", "item_name": "QUESO CHEDDAR EN BARRA 2.4 KG PV", "shelf_life_days": 28},
    {"item_code": "2112026", "item_name": "QUESO MUENSTER EN BARRA 2.3 KG PV", "shelf_life_days": 28},
    {"item_code": "2113076", "item_name": "QUESO CHEDDAR RALLADO **TP** 1 / 2.3 KG", "shelf_life_days": 28},
    {"item_code": "2114010", "item_name": "QUESO PEPPER JACK - JALAPEÑO REBANADO 2 KG", "shelf_life_days": 28},
    {"item_code": "2114011", "item_name": "QUESO PROVOLONE REBANADO 2 KG", "shelf_life_days": 28},
    {"item_code": "2114046", "item_name": "QUESO MONTEREY JACK REBANADO (REB 30 GRS) 1 / 2 KG", "shelf_life_days": 28},
]


def seed_shelf_life():
    """Crea la tabla product_shelf_life e inserta/actualiza los registros."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        count = 0
        for item in SHELF_LIFE_DATA:
            existing = db.query(ProductShelfLife).filter(ProductShelfLife.item_code == item["item_code"]).first()
            if existing:
                existing.item_name = item["item_name"]
                existing.shelf_life_days = float(item["shelf_life_days"])
            else:
                new_entry = ProductShelfLife(
                    item_code=item["item_code"],
                    item_name=item["item_name"],
                    shelf_life_days=float(item["shelf_life_days"]),
                )
                db.add(new_entry)
            count += 1
        db.commit()
        print(f"[OK] Se cargaron/actualizaron {count} registros de caducidad en product_shelf_life.")
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Error al sembrar product_shelf_life: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_shelf_life()
