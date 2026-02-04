@echo off
setlocal
title Lanzador STRIKELOG Pro
cd /d "%~dp0"

echo ========================================================
echo    INICIANDO STRIKELOG PRO
echo ========================================================
echo.

:: 1. Verificacion de Python
python --version >nul 2>&1
if %errorlevel% neq 0 goto :NO_PYTHON

:: 2. Instalar/Configurar Entorno Virtual (Automatico)
if not exist "env_strikelog" goto :SETUP_ENV

:START_APP
echo [INFO] Entorno detectado. Iniciando...
call env_strikelog\Scripts\activate
echo [INFO] Abriendo STRIKELOG Pro...
echo (Puedes minimizar esta ventana negra, pero NO la cierres)
echo.
streamlit run STRIKELOG.py --browser.gatherUsageStats false
if %errorlevel% neq 0 goto :APP_ERROR
goto :END

:SETUP_ENV
echo [INFO] Detectada primera ejecucion. Configurando entorno...
echo [1/3] Creando carpeta de sistema env_strikelog...
python -m venv env_strikelog
if %errorlevel% neq 0 goto :VENV_ERROR

echo [2/3] Activando entorno...
call env_strikelog\Scripts\activate

echo [3/3] Instalando librerias necesarias...
python -m pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 goto :PIP_ERROR

echo.
echo [EXITO] Instalacion completada correctamente.
echo.
goto :START_APP

:NO_PYTHON
echo [ERROR] No se detecto Python instalado.
echo.
echo Para que la aplicacion funcione en el ordenador de tu amigo,
echo es necesario que tenga Python instalado.
echo.
echo Descarga: https://www.python.org/downloads/
echo IMPORTANTE: Al instalar, marcar la casilla "Add Python to PATH".
echo.
pause
exit /b

:VENV_ERROR
echo [ERROR] No se pudo crear el entorno virtual.
pause
exit /b

:PIP_ERROR
echo.
echo [ERROR] Hubo un problema instalando las librerias.
echo Verifica tu conexion a internet.
pause
exit /b

:APP_ERROR
echo.
echo [ALERTA] La aplicacion se cerro o hubo un error.
pause
goto :END

:END
pause
