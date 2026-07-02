@echo off
title Production Forecast - Iniciar Servidor
color 0E
echo ============================================================
echo      INICIANDO PRODUCTION FORECAST (LABEN)
echo ============================================================
echo.

:: Cambiar al directorio del script
cd /d "%~dp0"

:: Lanzar el navegador para abrir el forecast de producción
echo 1. Abriendo el navegador en http://localhost:8000...
start http://localhost:8000

echo 2. Iniciando servidor Python (FastAPI)...
echo.
if exist venv\Scripts\python.exe (
    venv\Scripts\python.exe app/main.py
) else (
    echo [!] Advertencia: No se encontro el entorno virtual en 'venv\Scripts\python.exe'.
    echo Intentando con el python global del sistema...
    python app/main.py
)

if %errorlevel% neq 0 (
    echo.
    echo ------------------------------------------------------------
    echo ERROR: No se pudo iniciar el servidor.
    echo Asegurate de tener Python instalado y las dependencias de 
    echo requirements.txt instaladas en tu entorno virtual.
    echo ------------------------------------------------------------
    pause
)
