LECTORVISION SERVICE (Windows 10) - Requisitos e instrucciones
=============================================================

Este paquete configura un servicio de Windows (pywin32) que:
- Levanta un endpoint local (FastAPI/Uvicorn) para recibir JSON por HTTP
- Guarda los JSON en disco
- Clona imágenes desde una carpeta temporal a una carpeta permanente
- Procesa JSON para convertir imágenes a Base64 (si aplica)
- Envía JSON procesados a un endpoint remoto (si está habilitado)
- Limpia imágenes antiguas y rota logs

-------------------------------------------------------------
1) Requisitos previos (ANTES de ejecutar el BAT)
-------------------------------------------------------------

A) Python instalado y accesible desde consola
- Debe existir el comando: python
- Comprueba con:
  - Abrir PowerShell o CMD
  - Ejecutar: python --version

Si no funciona:
- Instala Python para Windows y marca "Add Python to PATH" durante la instalación.
- Cierra y vuelve a abrir la consola tras instalar.

IMPORTANTE:
- Este instalador NO fija una versión concreta de Python. Usará "python" del PATH.

B) Permisos de administrador
- Debes ejecutar el .bat con: Click derecho -> "Ejecutar como administrador"
- Motivo: instalar/gestionar servicios y escribir en rutas del sistema (ProgramData).

C) Acceso a Internet (o repositorio interno de pip)
- El BAT instala dependencias con pip. Necesita poder descargar paquetes.
- Si estás detrás de proxy corporativo, pip puede requerir configuración adicional.

D) Rutas usadas por el servicio (deben existir o poder crearse)
- Script:
  C:\Users\lectorvision\Documents\Sender\lectorvision_service.py

- Entrada de imágenes (origen):
  C:\Program Files (x86)\LectorVision\RedLight\PlateImageDir

- Carpeta de imágenes clonadas (destino):
  C:\Program Files (x86)\LectorVision\RedLight\Images

- JSON de entrada (ingest):
  C:\ProgramData\LectorVision\Ingest\json

- JSON procesados (sender):
  C:\ProgramData\LectorVision\Sender\json
  C:\ProgramData\LectorVision\Sender\pending
  C:\ProgramData\LectorVision\Sender\failed

- Logs:
  C:\ProgramData\LectorVision\logs

El BAT y el script crean carpetas si faltan, pero:
- Debes tener permisos de escritura en ProgramData.
- En Program Files (x86) la escritura suele requerir Admin.
  El servicio se instala para ejecutarse con permisos suficientes; si lo cambias, revisa permisos.

E) Puerto local (endpoint)
- Por defecto el servicio abre: 0.0.0.0:5055
- Si hay otro proceso usando el puerto, el servicio puede fallar.
- Para comprobar si el puerto está ocupado:
  - PowerShell: netstat -ano | findstr :5055
  - Si hay PID, puedes localizar el proceso y cerrarlo.

F) Firewall / Antivirus
- Si necesitas acceder desde otra máquina al endpoint:
  - Crea una regla de Firewall de entrada para el puerto 5055.
- Si todo es local (127.0.0.1), normalmente no hace falta abrir firewall.
- Algunos antivirus pueden bloquear watchdog/copias frecuentes: añade exclusión si fuese necesario.

-------------------------------------------------------------
2) Qué instala el BAT automáticamente
-------------------------------------------------------------

El BAT hace lo siguiente:
1) Crea un entorno virtual (venv) dentro de la carpeta del script:
   - C:\Users\lectorvision\Documents\Sender\.venv\

2) Actualiza pip/setuptools/wheel dentro del venv

3) Instala/actualiza dependencias requeridas en el venv:
   - fastapi
   - uvicorn
   - watchdog
   - pywin32

4) Instala el servicio de Windows usando el python del venv (pywin32)

5) Configura el servicio para:
   - Arrancar automáticamente en cada reinicio de Windows
   - Reiniciarse automáticamente si crashea (Recovery)

6) Arranca el servicio

-------------------------------------------------------------
3) Instrucciones de uso (paso a paso)
-------------------------------------------------------------

1) Abrir consola como Administrador
- Click en Inicio -> buscar "cmd" o "PowerShell"
- Click derecho -> "Ejecutar como administrador"

2) Ejecutar el BAT de instalación/configuración
- Ejemplo:
  - cd a la carpeta donde tengas el .bat
  - Ejecutar: setup_lectorvision_service.bat

3) Verificar que el servicio está en ejecución
- PowerShell:
  - sc.exe query LectorVisionIngest
  - sc.exe qfailure LectorVisionIngest

4) Probar el endpoint local (si el servicio está levantado)
- PowerShell:
  - Invoke-RestMethod http://127.0.0.1:5055/health

-------------------------------------------------------------
4) Operaciones comunes (start/stop/restart)
-------------------------------------------------------------

A) Con sc.exe:
- Parar:
  sc.exe stop LectorVisionIngest

- Arrancar:
  sc.exe start LectorVisionIngest

B) Con el script (IMPORTANTE: usando el Python del venv si quieres asegurar módulos)
- Ruta típica:
  C:\Users\lectorvision\Documents\Sender\.venv\Scripts\python.exe C:\Users\lectorvision\Documents\Sender\lectorvision_service.py stop
  C:\Users\lectorvision\Documents\Sender\.venv\Scripts\python.exe C:\Users\lectorvision\Documents\Sender\lectorvision_service.py start

-------------------------------------------------------------
5) Persistencia y auto-recuperación (lo que garantiza)
-------------------------------------------------------------

- Tras reinicio del ordenador:
  El servicio arranca solo (start=auto o delayed-auto, según configuración del BAT).

- Si el proceso del servicio se cae (crash):
  Windows lo reinicia automáticamente según la configuración de Recovery.

NOTA IMPORTANTE:
Si el proceso NO se cae, pero muere algún hilo interno (mirror/proc/send) y el proceso sigue vivo,
Windows no lo detecta como fallo.
En ese caso, la solución ideal es un "supervisor interno" en el script (watchdog de threads).
Si se necesita, se puede añadir.

-------------------------------------------------------------
6) Troubleshooting rápido
-------------------------------------------------------------

1) Error: "solo se permite un uso de cada dirección de socket" (WinError 10048)
- El puerto 5055 ya está en uso o hay un proceso colgado.
- Comprueba:
  netstat -ano | findstr :5055
- Para matar el PID (ejemplo):
  taskkill /PID <PID> /F

2) Error: ModuleNotFoundError (faltan módulos)
- Asegúrate de arrancar/instalar con el python del venv.
- Re-ejecuta el BAT.

3) El endpoint /health no responde
- Revisa el estado del servicio:
  sc.exe query LectorVisionIngest
- Revisa logs:
  C:\ProgramData\LectorVision\logs\

4) Problemas con escritura en Program Files (x86)
- Verifica permisos. Ejecuta instalación como Admin.
- Si cambiaste el usuario del servicio, vuelve a uno con permisos.

-------------------------------------------------------------
7) Archivos importantes
-------------------------------------------------------------

- Script:
  C:\Users\lectorvision\Documents\Sender\lectorvision_service.py

- Venv creado por el BAT:
  C:\Users\lectorvision\Documents\Sender\.venv\

- Logs:
  C:\ProgramData\LectorVision\logs\

- JSON ingest:
  C:\ProgramData\LectorVision\Ingest\json

- JSON sender:
  C:\ProgramData\LectorVision\Sender\json
  C:\ProgramData\LectorVision\Sender\pending
  C:\ProgramData\LectorVision\Sender\failed
