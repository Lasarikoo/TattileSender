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

## Selección de certificado y endpoint

- **Certificado WS-Security**: se firma siempre con el certificado asociado al
  municipio de la cámara (`municipality.certificate`). Del certificado se usan
  las rutas `client_cert_path`/`path` y `key_path` generadas a partir del `.pfx`
  almacenado en base de datos.
- **Endpoint efectivo**: el sender resuelve primero `camera.endpoint`; si no
  existe usa el endpoint del municipio. Si tampoco está configurado, utiliza el
  endpoint global `settings.MOSSOS_ENDPOINT_URL`. Si ninguno está disponible el
  mensaje se marca como `DEAD` sin intentar el envío.

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

## WS-Security

- Las peticiones SOAP al servicio MATR-WS se firman con X.509 utilizando el
  certificado del municipio obtenido desde la cámara.
- El cliente Zeep usa la clase `SignOnlySignature`, que hereda de
  `BinarySignature`, para firmar la petición. Esta variante mantiene la firma
  X.509 pero desactiva la verificación de la respuesta porque Mossos no envía
  cabecera `wsse:Security` en el reply.
- Código abreviado:

  ```python
  from zeep.wsse.signature import BinarySignature

  class SignOnlySignature(BinarySignature):
      def verify(self, envelope):
          return envelope
  ```

- El servicio se crea con el binding `{http://dgp.gencat.cat/matricules}MatriculesSoap11`
  apuntando al endpoint resuelto, y los logs muestran el endpoint usado al
  habilitar la firma.

## Política de reintentos y borrado

- Los reintentos dependen del endpoint (`retry_max`, `retry_backoff_ms`) o de los
  valores por defecto definidos en configuración.
- Los mensajes cuya lectura no tenga imágenes válidas (`has_image_ocr/ctx` falso,
  rutas nulas o ficheros inexistentes) se marcan inmediatamente como `DEAD` con
  errores `NO_IMAGE_AVAILABLE` o `NO_IMAGE_FILE` y **no** se reintentan.
- Tras un `codiRetorn` satisfactorio (`1`/`OK`/`0000`) se eliminan las imágenes
  en disco y los registros `alpr_readings` y `messages_queue` asociados.
- En errores permanentes (estado `DEAD`) los datos permanecen para análisis.
