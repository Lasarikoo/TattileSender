# Envío a Mossos (Fase 2)

Este documento resume cómo preparar certificados y cómo funciona el cliente SOAP
`matricula` incluido en TattileSender.

## Flujo de datos

1. La cámara envía la lectura (XML Tattile) al servicio de ingesta.
2. El ingest parsea y guarda la lectura en `alpr_readings` y crea una entrada en
   `messages_queue` con estado `PENDING`.
3. El sender procesa los mensajes pendientes, construye la petición SOAP
   `matricula` y la envía a Mossos.
4. Tras un `codiRetorn` satisfactorio se eliminan imágenes y registros; en caso
   de fallo se aplican reintentos o se marca como `DEAD` según la causa.

## Selección de endpoint y certificado

- **Endpoint efectivo**: el sender usa primero el endpoint de la cámara
  (`camera.endpoint`). Si no existe, usa el endpoint del municipio. Si tampoco
  está configurado, utiliza el endpoint global indicado en
  `settings.MOSSOS_ENDPOINT_URL`. Si ninguno está disponible el mensaje se marca
  como `DEAD`.
- **Certificado WS-Security**: se usa el certificado asociado al municipio
  (`municipality.certificate`). El cliente toma las rutas `client_cert_path`/`path`
  y `key_path` almacenadas en la base de datos (cargadas a partir del `.pfx` del
  municipio) para firmar la petición.

## Construcción de la petición `matricula`

- Se construye un diccionario de Python y se pasa a Zeep como argumentos con
  `self.service.matricula(**payload)`.
- Campos principales:
  - `codiLector`: `camera.codigo_lector` (máx. 16 caracteres).
  - `matricula`: matrícula en mayúsculas, recortada a 10 caracteres.
  - `dataLectura`: fecha UTC de la lectura en formato `YYYY-MM-DD`.
  - `horaLectura`: hora UTC en formato `HH:MM:SS`.
  - `imgMatricula` e `imgContext`: binarios de las imágenes leídas en disco y
    codificados en Base64.
- Campos opcionales si existen datos en la lectura o cámara: `coordenadaX`,
  `coordenadaY`, `marca`, `model`, `color`, `tipusVehicle`, `pais`.

## WS-Security con Zeep

- El cliente SOAP (`app/sender/mossos_client.py`) usa `zeep.wsse.signature.Signature`
  para firmar el cuerpo del mensaje con el certificado del municipio y añadir
  `Timestamp` y `BinarySecurityToken`.
- Se crea el servicio con el binding `{http://dgp.gencat.cat/matricules}MatriculesSoap11`
  apuntando al endpoint resuelto. Los logs muestran explícitamente el endpoint
  usado al habilitar la firma.

## Política de reintentos y borrado

- Los reintentos dependen del endpoint (`retry_max`, `retry_backoff_ms`) o de los
  valores por defecto definidos en configuración.
- Los mensajes cuya lectura no tenga imágenes válidas (`has_image_ocr/ctx` falso,
  rutas nulas o ficheros inexistentes) se marcan inmediatamente como `DEAD` con
  errores `NO_IMAGE_AVAILABLE` o `NO_IMAGE_FILE` y **no** se reintentan.
- Tras un `codiRetorn` satisfactorio (`1`/`OK`/`0000`) se eliminan las imágenes
  en disco y los registros `alpr_readings` y `messages_queue` asociados.
- En errores permanentes (estado `DEAD`) los datos permanecen para análisis.
