# Modelo de datos lógico

## ALPRReading (JSON lógico)
```json
{
  "plate": "7459MTL",
  "timestamp_utc": "2024-03-21T15:42:10Z",
  "device_sn": "TAT1234567",
  "device_name": "Camara Puente Norte",
  "direction": "GOAWAY",
  "lane_id": "1",
  "lane_descr": "Carril derecho",
  "ocr_score": 92.5,
  "country_code": "ESP",
  "country": "España",
  "bbox": {
    "min_x": 120,
    "min_y": 360,
    "max_x": 320,
    "max_y": 420,
    "char_height": 52
  },
  "has_image_ocr": true,
  "has_image_ctx": true,
  "raw_xml": "<ALPR>...</ALPR>"
}
```

- `timestamp_utc` se construye combinando `DATE` y `TIME` del XML de Tattile,
  aplicando el huso horario configurado en el servidor y almacenándolo en UTC.
- `bbox` captura la caja de la matrícula usando los campos `ORIG_PLATE_MIN_X`,
  `ORIG_PLATE_MIN_Y`, `ORIG_PLATE_MAX_X`, `ORIG_PLATE_MAX_Y` y `PLATE_CHAR_HEIGHT`.
- `has_image_ocr` y `has_image_ctx` indican la presencia de `IMAGE_OCR` y
  `IMAGE_CTX` en base64; las imágenes podrán almacenarse o descartarse según la
  política definida.

## QueueMessage (estructura lógica)
```json
{
  "reading_id": "uuid",
  "status": "PENDING",
  "attempts": 0,
  "last_error": null,
  "sent_at": null,
  "created_at": "2024-03-21T15:42:11Z"
}
```

- `reading_id` referencia al `ALPRReading` persistido.
- `status` puede ser `PENDING`, `SENT`, `FAILED`, `RETRYING` u otros que se
  definan más adelante.
- `attempts` cuenta los intentos de envío al endpoint.
- `last_error` almacena el mensaje de error más reciente (texto controlado).
- `sent_at` se rellena cuando el envío se confirma como exitoso.
- `created_at` marca el momento de encolado.
