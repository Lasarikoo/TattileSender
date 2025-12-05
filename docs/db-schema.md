# Esquema de base de datos conceptual

## Tabla `municipalities`
- `id` (uuid): identificador único.
- `name` (texto): nombre del municipio/ayuntamiento/instalación.
- `code` (texto, opcional): código de referencia externa.
- `certificate_id` (uuid, fk): referencia a `certificates` asociada al municipio.
- `endpoint_id` (uuid, fk opcional): destino preferente; si no está, se usa
  un endpoint por defecto.
- `active` (booleano): indica si el municipio está habilitado.
- Permite agrupar cámaras bajo un mismo certificado/endpoint sin duplicar
  configuración.

## Tabla `certificates`
- `id` (uuid): identificador único.
- `name` (texto): nombre descriptivo del certificado.
- `type` (enum): PFX/PEM u otro formato soportado.
- `path` (texto): ruta al archivo de certificado en el servidor (fuera del
  repositorio).
- `password_hint` (texto, opcional): pista de contraseña sin exponer el valor.
- `valid_from` / `valid_to` (timestamp, opcional): ventana de validez conocida.
- `active` (booleano): indica si se debe utilizar.
- Puede ser reutilizado por varios municipios y, por extensión, por las cámaras
  de dichos municipios.

## Tabla `endpoints`
- `id` (uuid): identificador único.
- `name` (texto): nombre descriptivo (ej. "Mossos Producción").
- `url` (texto): endpoint SOAP.
- `timeout_ms` (entero): timeout de petición en milisegundos.
- `retry_max` (entero): número máximo de reintentos.
- `retry_backoff_ms` (entero): backoff entre reintentos.
- `soap_action` (texto, opcional): acción SOAP si aplica.
- Normalmente apuntará a Mossos, pero el diseño permite otros destinos.

## Tabla `cameras`
- `id` (uuid): identificador único.
- `serial_number` (texto, único): `DEVICE_SN` de la cámara Tattile.
- `codigo_lector` (texto): código interno (ej. `CodigoLector` en legacy).
- `description` (texto, opcional): detalle de ubicación.
- `municipality_id` (uuid, fk): referencia a `municipalities` para resolver
  certificado y endpoint.
- `endpoint_id` (uuid, fk opcional): override de endpoint si la cámara tiene un
  destino distinto al de su municipio.
- `active` (booleano): indica si la cámara está habilitada.
- Hereda certificado/endpoint a través del municipio, permitiendo compartir
  configuración.

## Tabla `alpr_readings`
- `id` (uuid): identificador único.
- `plate` (texto).
- `timestamp_utc` (timestamp).
- `device_sn` (texto) y `device_name` (texto opcional).
- `direction` (texto), `lane_id` (texto), `lane_descr` (texto opcional).
- `ocr_score` (numérico), `country_code` (texto), `country` (texto).
- `bbox_min_x`, `bbox_min_y`, `bbox_max_x`, `bbox_max_y`, `char_height` (numéricos).
- `has_image_ocr` (booleano), `has_image_ctx` (booleano): indicadores de si la lectura llegó con imágenes válidas.
- `image_ocr_path` / `image_ctx_path` (texto, opcional): rutas relativas respecto a `IMAGES_BASE_DIR` donde se almacenaron las imágenes en disco.
- `raw_xml` (texto largo o XML).
- `camera_id` (uuid, fk): referencia a `cameras` para conocer municipio y
  certificados asociados.
- Índices sugeridos: por `plate`, por `timestamp_utc`, por `device_sn`.
- Tabla de trabajo temporal: almacena lecturas mientras estén pendientes de
  envío o en reintento. Tras envío exitoso se eliminan los registros y, si
  aplica, las imágenes asociadas en disco/almacenamiento externo.

## Tabla `messages_queue`
- `id` (uuid): identificador único.
- `reading_id` (uuid, fk): referencia a `alpr_readings`.
- `status` (texto controlado): `PENDING`, `SENDING`, `FAILED`, `DEAD`, `SUCCESS`.
- `attempts` (entero): número de intentos de envío.
- `last_error` (texto opcional): mensaje de error del último intento.
- `sent_at` (timestamp opcional): última fecha de envío exitoso.
- `created_at` (timestamp): fecha de encolado.
- Tabla de trabajo temporal: gestiona el estado de envío. Al confirmarse un
  envío correcto a Mossos se debe eliminar la fila correspondiente y la lectura
  asociada en `alpr_readings`, además de purgar imágenes vinculadas.
  Los mensajes cuya lectura no tenga imágenes válidas se marcan como `DEAD` sin
  reintentos. Errores típicos de imagen: `NO_IMAGE_AVAILABLE_OCR`,
  `NO_IMAGE_FILE_OCR:<ruta>`, `NO_IMAGE_FILE_CTX:<ruta>`, o
  `NO_IMAGE_FILE_RUNTIME:<detalle>`.

## Relaciones y notas
- `municipalities.certificate_id` → `certificates.id` (un municipio define el
  certificado compartido por sus cámaras).
- `municipalities.endpoint_id` → `endpoints.id` (destino por municipio; la
  cámara puede sobrescribirlo).
- `cameras.municipality_id` → `municipalities.id`.
- `cameras.endpoint_id` → `endpoints.id` (si necesita un destino específico).
- `messages_queue.reading_id` → `alpr_readings.id`.
- Se pueden añadir índices compuestos (`plate`, `timestamp_utc`) para acelerar
  búsquedas por matrícula y rango temporal.

## Posible extensión futura
- Tabla `delivery_log` (opcional): registro de auditoría sin matrícula ni
  imágenes, con campos como `camera_id`, `municipality_id`, `fecha_envio`,
  `resultado` y mensajes de error resumidos para trazabilidad sin datos
  personales.
