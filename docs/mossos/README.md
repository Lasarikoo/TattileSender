# Envío a Mossos (Fase 2)

Este documento resume cómo preparar certificados y cómo funciona el cliente SOAP
`matricula` incluido en TattileSender.

## Certificados

- Mossos entrega los certificados en formato `.pfx`. Es necesario convertirlos a
  PEM (certificado + clave privada) **fuera** de la aplicación.
- Ejemplo de conversión en un host seguro:
  ```bash
  openssl pkcs12 -in origen.pfx -out cert.pem -clcerts -nokeys
  openssl pkcs12 -in origen.pfx -out key.pem -nocerts -nodes
  cat cert.pem key.pem > mossos-combinado.pem
  ```
- Copia el fichero PEM resultante al directorio definido en `CERTS_DIR`.
- Registra el certificado con `./ajustes.sh` (opción Certificados) indicando el
  `path` relativo dentro de `CERTS_DIR`.
- Asigna el certificado al municipio o a la cámara con los scripts de
  asignación (`assign_municipality_certificate`, `assign_camera_certificate`).

## SOAP `matricula`

- Espacios de nombres: `soapenv` = `http://schemas.xmlsoap.org/soap/envelope/`
  y `mat` = `http://dgp.gencat.cat/matricules`.
- Campos obligatorios:
  - `codiLector`: viene de `camera.codigo_lector`.
  - `matricula`: matrícula leída.
  - `dataLectura` y `horaLectura`: fecha/hora UTC de la lectura.
  - `imgMatricula` e `imgContext`: binarios en Base64.
- La petición viaja por HTTPS usando el certificado cliente configurado. La
  capa WS-Security no se implementa por ahora; el código deja puntos de
  extensión (ver `app/sender/mossos_client.py`) para añadir firma XML si fuera
  necesario.

## Política de reintentos y borrado

- Los reintentos dependen del endpoint (`retry_max`, `retry_backoff_ms`) o de
  los valores por defecto definidos en configuración.
- Los mensajes cuya lectura no tenga imágenes válidas (`has_image_ocr/ctx` falso,
  rutas nulas o ficheros inexistentes) se marcan inmediatamente como `DEAD`
  con errores `NO_IMAGE_AVAILABLE` o `NO_IMAGE_FILE` y **no** se reintentan.
- Tras un `codiRetorn=1`:
  - Se eliminan las imágenes en disco (si existen rutas registradas).
  - Se borran los registros `alpr_readings` y `messages_queue` asociados.
- En errores permanentes (estado `DEAD`) los datos permanecen para análisis.
