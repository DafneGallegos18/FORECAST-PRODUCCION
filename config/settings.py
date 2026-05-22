"""
Configuración centralizada del proyecto.
Utiliza pydantic-settings para cargar variables de entorno de forma tipada.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class SAPSettings(BaseSettings):
    """Conexión a SAP B1 via ODBC."""
    dsn: str = "SAPB1"
    db_server: str = ""
    db_name: str = ""
    db_user: str = ""
    db_password: str = ""
    use_dsn: bool = True

    model_config = {"env_prefix": "SAP_"}


class SMTPSettings(BaseSettings):
    """Configuración de correo electrónico."""
    host: str = ""
    port: int = 587
    user: str = ""
    password: str = ""
    from_name: str = "Forecast de Producción"
    from_email: str = ""

    model_config = {"env_prefix": "SMTP_"}


class ForecastSettings(BaseSettings):
    """Parámetros del motor de pronóstico."""
    lookback_days: int = 28
    target_stock_days: int = 15
    schedule_day: str = "wednesday"

    model_config = {"env_prefix": "FORECAST_"}


class AppSettings(BaseSettings):
    """Configuración general de la aplicación."""
    port: int = 8000
    env: str = "development"
    secret_key: str = "change-me-in-production"

    model_config = {"env_prefix": "APP_"}


# --- Instancias Singleton ---
sap_settings = SAPSettings()
smtp_settings = SMTPSettings()
forecast_settings = ForecastSettings()
app_settings = AppSettings()
