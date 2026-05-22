"""
Production Forecast — Punto de entrada principal.
Aplicación FastAPI que orquesta el pronóstico automatizado de producción.
"""

import os
import sys
import io

# Forzar UTF-8 en stdout/stderr para evitar errores con emojis en Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Asegurar que el directorio raíz del proyecto esté en el path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()  # Cargar variables de entorno antes de importar settings

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database import init_db, SessionLocal
from app.routes import forecast, exclusions, alerts
from app.services.exclusion_service import seed_default_exclusions
from config.settings import app_settings


# ── Lifespan (startup / shutdown) ─────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Maneja el ciclo de vida de la aplicación."""
    # --- Startup ---
    print("\n[*] Production Forecast iniciando...")
    init_db()

    # Cargar exclusiones del Excel original si es la primera vez
    db = SessionLocal()
    try:
        seed_default_exclusions(db)
    finally:
        db.close()

    print(f"    Servidor: http://localhost:{app_settings.port}")
    print(f"    Docs API: http://localhost:{app_settings.port}/docs")
    print(f"    Entorno:  {app_settings.env}\n")

    yield

    # --- Shutdown ---
    from app.services.sap_connector import sap_connector
    sap_connector.close()
    print("\n[*] Production Forecast detenido")


# ── Crear aplicación FastAPI ───────────────────────────────────────

app = FastAPI(
    title="Production Forecast",
    description="Sistema automatizado de pronostico de produccion",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — permitir acceso desde cualquier origen (para desarrollo local)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Registrar rutas API ───────────────────────────────────────────

app.include_router(forecast.router)
app.include_router(exclusions.router)
app.include_router(alerts.router)


# ── Health Check ──────────────────────────────────────────────────

@app.get("/api/health")
def health_check():
    """Endpoint de verificacion de salud del servidor."""
    return {"status": "ok", "service": "production-forecast"}


# ── Servir Frontend Estático (futuro) ─────────────────────────────

frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.isdir(frontend_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dir, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """SPA fallback: sirve index.html para rutas no-API."""
        index = os.path.join(frontend_dir, "index.html")
        if os.path.exists(index):
            return FileResponse(index)
        return {"detail": "Frontend no encontrado"}


# ── Ejecucion directa ────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=app_settings.port,
        reload=app_settings.env == "development",
    )
