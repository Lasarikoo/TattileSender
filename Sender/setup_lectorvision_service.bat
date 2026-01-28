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

REM Packages needed by the script
set "REQ_PKGS=fastapi uvicorn watchdog pywin32"

REM Exit code tracking
set "EXIT_CODE=0"
set "DID_PUSHD=0"

REM ============================================================
REM Admin check
REM ============================================================
net session >nul 2>&1
if %errorlevel% neq 0 (
  call :fail "Este .bat requiere privilegios de Administrador. Click derecho ^> \"Ejecutar como administrador\"." 1
)

REM ============================================================
REM Validate python
REM ============================================================
where %PY% >nul 2>&1
if %errorlevel% neq 0 (
  call :fail "No se encontro \"python\" en el PATH. Instala Python y verifica el PATH (o ajusta la variable PY)." 1
)

REM ============================================================
REM Validate script exists
REM ============================================================
if not exist "%SCRIPT_PATH%" (
  call :fail "No existe el script: \"%SCRIPT_PATH%\". Verifica la ruta en SCRIPT_PATH." 1
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
REM 1) Install deps using system Python (no venv)
REM ============================================================
pushd "%SCRIPT_DIR%"
set "DID_PUSHD=1"

echo [STEP] Validando pip en el Python del sistema...
"%PY%" -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
  call :fail "Pip no esta disponible en el Python del sistema. Ejecuta \"python -m ensurepip --upgrade\" o reinstala Python con pip habilitado." 1
)

echo [STEP] Actualizando pip/setuptools/wheel en el sistema...
"%PY%" -m pip install --upgrade pip setuptools wheel
if %errorlevel% neq 0 (
  call :fail "No se pudo actualizar pip/setuptools/wheel. Revisa permisos, proxy o conectividad a Internet." 1
)

echo [STEP] Instalando dependencias en el sistema: %REQ_PKGS%
"%PY%" -m pip install --upgrade %REQ_PKGS%
if %errorlevel% neq 0 (
  call :fail "Fallo instalando dependencias (%REQ_PKGS%). Verifica conectividad, permisos o version de Python." 1
)

REM ============================================================
REM 2) Install service using system python
REM ============================================================
echo [STEP] Instalando servicio (pywin32)...
"%PY%" "%SCRIPT_PATH%" install >nul 2>&1
if %errorlevel% neq 0 (
  echo [WARN] La instalacion devolvio error. Puede ser que ya este instalado. Continuo...
) else (
  echo [OK] Servicio instalado.
)

REM ============================================================
REM 3) Start mode
REM ============================================================
echo [STEP] Configurando inicio: %START_MODE%
sc.exe config "%SVC_NAME%" start= %START_MODE% >nul
if %errorlevel% neq 0 (
  call :fail "No se pudo configurar start=%START_MODE% para %SVC_NAME%. Verifica el nombre del servicio y permisos." 1
)
echo [OK] Start mode aplicado.

REM ============================================================
REM 4) Recovery config (restart on failure)
REM ============================================================
echo [STEP] Configurando Recovery (auto-restart tras fallos)...
sc.exe failure "%SVC_NAME%" reset= 0 actions= restart/%RESTART_DELAY_MS%/restart/%RESTART_DELAY_MS%/restart/%RESTART_DELAY_MS% >nul
if %errorlevel% neq 0 (
  call :fail "No se pudo configurar \"failure actions\" para %SVC_NAME%. Verifica que el servicio exista." 1
)

sc.exe failureflag "%SVC_NAME%" 1 >nul
if %errorlevel% neq 0 (
  call :fail "No se pudo configurar \"failureflag\" para %SVC_NAME%. Verifica permisos." 1
)
echo [OK] Recovery aplicado.

REM ============================================================
REM 5) Start service (use system python)
REM ============================================================
echo [STEP] Arrancando servicio...
sc.exe query "%SVC_NAME%" | find /I "RUNNING" >nul
if %errorlevel% equ 0 (
  echo [INFO] Ya estaba RUNNING. Reiniciando para asegurar dependencias/config...
  "%PY%" "%SCRIPT_PATH%" stop >nul 2>&1
  timeout /t 2 /nobreak >nul
)

"%PY%" "%SCRIPT_PATH%" start
if %errorlevel% neq 0 (
  echo [WARN] Start via pywin devolvio error. Intento con sc.exe start...
  sc.exe start "%SVC_NAME%" >nul 2>&1
)

timeout /t 2 /nobreak >nul

REM ============================================================
REM 6) Verification
REM ============================================================
echo.
echo [INFO] Estado del servicio:
sc.exe query "%SVC_NAME%"
echo.
echo [INFO] Configuracion de acciones ante fallos (no indica error actual):
sc.exe qfailure "%SVC_NAME%"
echo.
echo [INFO] QC config:
sc.exe qc "%SVC_NAME%"
echo.
echo [DONE] Listo.

goto :end

:fail
echo [ERROR] %~1
set "EXIT_CODE=%~2"
goto :end

:end
if "%DID_PUSHD%"=="1" popd
if %EXIT_CODE% neq 0 (
  echo.
  echo [FAILED] El proceso termino con errores. Revisa los mensajes anteriores.
) else (
  echo.
  echo [OK] El proceso finalizo correctamente.
)
echo.
echo Presiona cualquier tecla para cerrar esta ventana.
pause >nul
endlocal
exit /b %EXIT_CODE%
