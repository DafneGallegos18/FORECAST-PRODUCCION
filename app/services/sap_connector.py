"""
Conector a SAP Business One v9.3 via ODBC (solo lectura).
Maneja la conexión, ejecución de queries y cierre limpio.
"""

import pyodbc
import pandas as pd
import threading
from typing import Optional
from config.settings import sap_settings


class SAPConnector:
    """
    Gestiona la conexión de solo lectura a la base SQL Server de SAP B1.
    Soporta conexión por DSN preconfigurado o por conexión directa.
    """

    def __init__(self):
        self._connection: Optional[pyodbc.Connection] = None
        self._lock = threading.Lock()

    def _build_connection_string(self) -> str:
        """Construye el string de conexión según la configuración."""
        if sap_settings.use_dsn:
            return f"DSN={sap_settings.dsn}"
        else:
            return (
                f"DRIVER={{ODBC Driver 18 for SQL Server}};"
                f"SERVER={sap_settings.db_server};"
                f"DATABASE={sap_settings.db_name};"
                f"UID={sap_settings.db_user};"
                f"PWD={sap_settings.db_password};"
                f"TrustServerCertificate=yes;"
                f"MARS_Connection=yes;"
            )

    def connect(self, force_new: bool = False) -> pyodbc.Connection:
        """Establece o reutiliza la conexión a SAP."""
        if force_new or self._connection is None:
            self.close()
            conn_str = self._build_connection_string()
            self._connection = pyodbc.connect(conn_str, readonly=True, autocommit=True)
            print("✅ Conectado a SAP B1 (solo lectura)")
        return self._connection

    def query(self, sql: str, params: Optional[tuple] = None) -> pd.DataFrame:
        """
        Ejecuta un query SQL y retorna los resultados como DataFrame de Pandas.
        Reintenta automáticamente reconectando si la conexión se perdió.
        Utiliza un lock de hilo para prevenir colisiones concurrentes (Connection is busy).
        """
        with self._lock:
            for attempt in range(2):
                try:
                    conn = self.connect(force_new=(attempt > 0))
                    cursor = conn.cursor()
                    try:
                        if params:
                            cursor.execute(sql, params)
                        else:
                            cursor.execute(sql)
                        
                        columns = [col[0] for col in cursor.description]
                        rows = [list(row) for row in cursor.fetchall()]
                        
                        return pd.DataFrame(rows, columns=columns)
                    finally:
                        try:
                            cursor.close()
                        except Exception:
                            pass
                except (pyodbc.Error, Exception) as e:
                    print(f"⚠️ Intentando reconectar a SAP (intento {attempt + 1}) por error: {e}")
                    self.close()
                    if attempt == 1:
                        print(f"❌ Error fatal al ejecutar query SAP: {e}")
                        raise

    def test_connection(self) -> bool:
        """Prueba rápida de conectividad."""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 AS test")
            result = cursor.fetchone()
            cursor.close()
            return result[0] == 1
        except Exception as e:
            print(f"❌ Prueba de conexión fallida: {e}")
            return False

    def close(self):
        """Cierra la conexión a SAP de forma limpia."""
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
            self._connection = None
            print("🔌 Conexión a SAP cerrada")


# Instancia singleton
sap_connector = SAPConnector()
