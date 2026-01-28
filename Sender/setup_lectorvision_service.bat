@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================
REM CONFIG
REM ============================================================
set "PY=python"
set "SCRIPT_PATH=C:\Users\lectorvision\Documents\Sender\lectorvision_service.py"
set "SVC_NAME=LectorVisionIngest"

REM auto o delayed-auto (recomendado si al arrancar Windows aún no están listas rutas/red)
set "START_MODE=auto"
REM set "START_MODE=delayed-auto"

REM Recovery delays (ms)
set "RESTART_DELAY_MS=5000"

REM VENV name inside script folder
set "VENV_DIR=.venv"

REM Packages needed by the script
set "REQ_PKGS=fastapi uvicorn watchdog pywin32"

REM ============================================================
REM Admin check
REM ============================================================
net session >nul 2>&1
if %errorlevel% neq 0 (
  echo [ERROR] Ejecuta este .bat como Administrador.
  echo         Click derecho ^> "Ejecutar como administrador"
  exit /b 1
)

REM ============================================================
REM Validate python
REM ============================================================
where %PY% >nul 2>&1
if %errorlevel% neq 0 (
  echo [ERROR] No se encontro "python" en el PATH.
  echo         Instala Python o anadelo al PATH y vuelve a ejecutar.
  exit /b 1
)

REM ============================================================
REM Validate script exists
REM ============================================================
if not exist "%SCRIPT_PATH%" (
  echo [ERROR] No existe el script: "%SCRIPT_PATH%"
  exit /b 1
)

REM Resolve script dir
for %%I in ("%SCRIPT_PATH%") do (
  set "SCRIPT_DIR=%%~dpI"
  set "SCRIPT_FILE=%%~nxI"
)

echo [OK] Admin detectado.
echo [INFO] Python: %PY%
echo [INFO] Script: "%SCRIPT_PATH%"
echo [INFO] Script dir: "%SCRIPT_DIR%"
echo [INFO] Service: %SVC_NAME%
echo.

REM ============================================================
REM 1) Create / use venv (recommended)
REM ============================================================
pushd "%SCRIPT_DIR%"

if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo [STEP] Creando venv en "%SCRIPT_DIR%%VENV_DIR%" ...
  %PY% -m venv "%VENV_DIR%"
  if %errorlevel% neq 0 (
    echo [ERROR] No se pudo crear el venv. Abortando.
    popd
    exit /b 1
  )
) else (
  echo [INFO] Venv ya existe: "%SCRIPT_DIR%%VENV_DIR%"
)

set "VENV_PY=%SCRIPT_DIR%%VENV_DIR%\Scripts\python.exe"
set "VENV_PIP=%SCRIPT_DIR%%VENV_DIR%\Scripts\pip.exe"

REM ============================================================
REM 2) Upgrade pip + install deps
REM ============================================================
echo [STEP] Actualizando pip/setuptools/wheel...
"%VENV_PY%" -m pip install --upgrade pip setuptools wheel
if %errorlevel% neq 0 (
  echo [ERROR] No se pudo actualizar pip. Abortando.
  popd
  exit /b 1
)

echo [STEP] Instalando dependencias: %REQ_PKGS%
"%VENV_PY%" -m pip install --upgrade %REQ_PKGS%
if %errorlevel% neq 0 (
  echo [ERROR] Fallo instalando dependencias. Abortando.
  popd
  exit /b 1
)

REM ============================================================
REM 3) Install service using venv python (important)
REM ============================================================
echo [STEP] Instalando servicio (pywin32)...
"%VENV_PY%" "%SCRIPT_PATH%" install >nul 2>&1
if %errorlevel% neq 0 (
  echo [WARN] La instalacion devolvio error. Puede ser que ya este instalado. Continuo...
) else (
  echo [OK] Servicio instalado.
)

REM ============================================================
REM 4) Start mode
REM ============================================================
echo [STEP] Configurando inicio: %START_MODE%
sc.exe config "%SVC_NAME%" start= %START_MODE% >nul
if %errorlevel% neq 0 (
  echo [ERROR] No se pudo configurar start=%START_MODE% para %SVC_NAME%
  popd
  exit /b 1
)
echo [OK] Start mode aplicado.

REM ============================================================
REM 5) Recovery config (restart on failure)
REM ============================================================
echo [STEP] Configurando Recovery (auto-restart tras fallos)...
sc.exe failure "%SVC_NAME%" reset= 0 actions= restart/%RESTART_DELAY_MS%/restart/%RESTART_DELAY_MS%/restart/%RESTART_DELAY_MS% >nul
if %errorlevel% neq 0 (
  echo [ERROR] No se pudo configurar "failure actions" para %SVC_NAME%
  popd
  exit /b 1
)

sc.exe failureflag "%SVC_NAME%" 1 >nul
if %errorlevel% neq 0 (
  echo [ERROR] No se pudo configurar "failureflag" para %SVC_NAME%
  popd
  exit /b 1
)
echo [OK] Recovery aplicado.

REM ============================================================
REM 6) Start service (use venv python to avoid missing modules)
REM ============================================================
echo [STEP] Arrancando servicio...
sc.exe query "%SVC_NAME%" | find /I "RUNNING" >nul
if %errorlevel% equ 0 (
  echo [INFO] Ya estaba RUNNING. Reiniciando para asegurar dependencias/config...
  "%VENV_PY%" "%SCRIPT_PATH%" stop >nul 2>&1
  timeout /t 2 /nobreak >nul
)

"%VENV_PY%" "%SCRIPT_PATH%" start
if %errorlevel% neq 0 (
  echo [WARN] Start via pywin devolvio error. Intento con sc.exe start...
  sc.exe start "%SVC_NAME%" >nul 2>&1
)

timeout /t 2 /nobreak >nul

REM ============================================================
REM 7) Verification
REM ============================================================
echo.
echo [INFO] Estado del servicio:
sc.exe query "%SVC_NAME%"
echo.
echo [INFO] Failure config:
sc.exe qfailure "%SVC_NAME%"
echo.
echo [INFO] QC config:
sc.exe qc "%SVC_NAME%"
echo.
echo [DONE] Listo.

popd
endlocal
exit /b 0
