# Esquema de base de datos conceptual

## Tabla `certificates`
- `id` (uuid): identificador único.
- `name` (texto): nombre descriptivo del certificado.
- `pfx_path` (texto): ruta al archivo .pfx en el servidor (fuera del repo).
- `password_hint` (texto, opcional): pista de contraseña sin exponer el valor.
- `expires_at` (timestamp, opcional): fecha de caducidad conocida.

## Tabla `endpoints`
- `id` (uuid): identificador único.
- `name` (texto): nombre descriptivo (ej. "Mossos Producción").
- `url` (texto): endpoint SOAP.
- `soap_action` (texto, opcional): acción SOAP si aplica.

## Tabla `cameras`
- `id` (uuid): identificador único.
- `serial_number` (texto): `DEVICE_SN` de la cámara Tattile.
- `code` (texto): código interno (ej. `CodigoLector` en legacy).
- `description` (texto, opcional): detalle de ubicación.
- `certificate_id` (uuid, fk): referencia a `certificates`.
- `endpoint_id` (uuid, fk): referencia a `endpoints`.

## Tabla `alpr_readings`
- `id` (uuid): identificador único.
- `plate` (texto).
- `timestamp_utc` (timestamp).
- `device_sn` (texto) y `device_name` (texto opcional).
- `direction` (texto), `lane_id` (texto), `lane_descr` (texto opcional).
- `ocr_score` (numérico), `country_code` (texto), `country` (texto).
- `bbox_min_x`, `bbox_min_y`, `bbox_max_x`, `bbox_max_y`, `char_height` (numéricos).
- `has_image_ocr` (booleano), `has_image_ctx` (booleano).
- `raw_xml` (texto largo o XML).
- Índices sugeridos: por `plate`, por `timestamp_utc`, por `device_sn`.

## Tabla `messages_queue`
- `id` (uuid): identificador único.
- `reading_id` (uuid, fk): referencia a `alpr_readings`.
- `status` (texto controlado): `PENDING`, `SENT`, `FAILED`, `RETRYING`.
- `attempts` (entero): número de intentos de envío.
- `last_error` (texto opcional): mensaje de error del último intento.
- `sent_at` (timestamp opcional): última fecha de envío exitoso.
- `created_at` (timestamp): fecha de encolado.

## Relaciones y notas
- `cameras.certificate_id` → `certificates.id` (una cámara usa un certificado).
- `cameras.endpoint_id` → `endpoints.id` (una cámara apunta a un endpoint).
- `messages_queue.reading_id` → `alpr_readings.id`.
- Se pueden añadir índices compuestos (`plate`, `timestamp_utc`) para acelerar
  búsquedas por matrícula y rango temporal.
