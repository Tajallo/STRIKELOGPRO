@echo off
setlocal
title Lanzador STRIKELOG Pro

:: Ir al directorio donde esta el script
cd /d "%~dp0"

echo ==========================================
echo    INICIANDO STRIKELOG PRO
echo ==========================================
echo.

:: 1. Verificar si Python esta instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no esta instalado en este sistema.
    echo Por favor, instala Python desde python.org y marca la casilla "Add Python to PATH".
    pause
    exit /b
)

:: 2. Crear entorno virtual si no existe
if not exist "env_strikelog" (
    echo [INFO] Creando entorno virtual para la primera ejecucion...
    python -m venv env_strikelog
    if %errorlevel% neq 0 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b
    )
    
    echo [INFO] Instalando librerias necesarias (esto solo pasara una vez)...
    call env_strikelog\Scripts\activate
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Hubo un fallo instalando las librerias.
        pause
        exit /b
    )
) else (
    call env_strikelog\Scripts\activate
)

:: 3. Lanzar la app
echo [INFO] Iniciando la aplicacion...
streamlit run STRIKELOG.py --browser.gatherUsageStats false

:: Si la app se cierra por algun motivo
echo.
echo La aplicacion se ha cerrado.
pause
