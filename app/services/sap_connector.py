"""
Conector a SAP Business One v9.3 via ODBC (solo lectura).
Maneja la conexión, ejecución de queries y cierre limpio.
"""

import pyodbc
import pandas as pd
from typing import Optional
from config.settings import sap_settings


class SAPConnector:
    """
    Gestiona la conexión de solo lectura a la base SQL Server de SAP B1.
    Soporta conexión por DSN preconfigurado o por conexión directa.
    """

    def __init__(self):
        self._connection: Optional[pyodbc.Connection] = None

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
            )

    def connect(self) -> pyodbc.Connection:
        """Establece o reutiliza la conexión a SAP."""
        if self._connection is None:
            conn_str = self._build_connection_string()
            self._connection = pyodbc.connect(conn_str, readonly=True)
            print("✅ Conectado a SAP B1 (solo lectura)")
        return self._connection

    def query(self, sql: str, params: Optional[tuple] = None) -> pd.DataFrame:
        """
        Ejecuta un query SQL y retorna los resultados como DataFrame de Pandas.

        Args:
            sql: Query SQL de solo lectura.
            params: Parámetros opcionales para queries parametrizados.

        Returns:
            pd.DataFrame con los resultados.
        """
        conn = self.connect()
        try:
            if params:
                df = pd.read_sql_query(sql, conn, params=params)
            else:
                df = pd.read_sql_query(sql, conn)
            return df
        except pyodbc.Error as e:
            print(f"❌ Error al ejecutar query SAP: {e}")
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
            self._connection.close()
            self._connection = None
            print("🔌 Conexión a SAP cerrada")


# Instancia singleton
sap_connector = SAPConnector()
