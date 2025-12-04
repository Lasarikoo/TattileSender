# Ejemplos de payload Tattile

## Ejemplo de lectura ALPR en XML
```xml
<Msg>
  <PLATE_STRING>7459MTL</PLATE_STRING>
  <DATE>2024-03-21</DATE>
  <TIME>15:42:10</TIME>
  <DEVICE_SN>TAT1234567</DEVICE_SN>
  <DEVICE_NAME>Camara Puente Norte</DEVICE_NAME>
  <OCRSCORE>92.5</OCRSCORE>
  <DIRECTION>GOAWAY</DIRECTION>
  <LANE_ID>1</LANE_ID>
  <LANE_DESCR>Carril derecho</LANE_DESCR>
  <ORIG_PLATE_MIN_X>120</ORIG_PLATE_MIN_X>
  <ORIG_PLATE_MIN_Y>360</ORIG_PLATE_MIN_Y>
  <ORIG_PLATE_MAX_X>320</ORIG_PLATE_MAX_X>
  <ORIG_PLATE_MAX_Y>420</ORIG_PLATE_MAX_Y>
  <PLATE_CHAR_HEIGHT>52</PLATE_CHAR_HEIGHT>
  <PLATE_COUNTRY_CODE>ESP</PLATE_COUNTRY_CODE>
  <PLATE_COUNTRY>España</PLATE_COUNTRY>
  <IMAGE_OCR>BASE64_JPG_OCR</IMAGE_OCR>
  <IMAGE_CTX>BASE64_JPG_CTX</IMAGE_CTX>
</Msg>
```

Campos mapeados al modelo interno `ALPRReading`:
- `PLATE_STRING` → `plate`
- `DATE` + `TIME` → `timestamp_utc` (convertido a UTC)
- `DEVICE_SN` → `device_sn`
- `DEVICE_NAME` → `device_name`
- `OCRSCORE` → `ocr_score`
- `DIRECTION` → `direction`
- `LANE_ID` y `LANE_DESCR` → `lane_id`, `lane_descr`
- `ORIG_PLATE_MIN_X`...`PLATE_CHAR_HEIGHT` → `bbox`
- `PLATE_COUNTRY_CODE`, `PLATE_COUNTRY` → `country_code`, `country`
- `IMAGE_OCR`, `IMAGE_CTX` → indicadores `has_image_ocr`, `has_image_ctx` y
  almacenamiento opcional de binarios.
