# Formatos de datos

## 1) XML Tattile (ingesta TCP)
El servicio TCP recibe un XML con estas etiquetas principales. **Obligatorias**: `PLATE_STRING` y `DEVICE_SN`.

### Campos soportados
- `PLATE_STRING` (string, requerido)
- `DEVICE_SN` (string, requerido)
- `DATE` (YYYY-MM-DD)
- `TIME` (HH-MM-SS-mmm)
- `IMAGE_OCR` (Base64)
- `IMAGE_CTX` (Base64)
- `OCRSCORE` (int, 0-999)
- `DIRECTION` (string)
- `LANE_ID` (int)
- `LANE_DESCR` (string)
- `ORIG_PLATE_MIN_X`, `ORIG_PLATE_MIN_Y`, `ORIG_PLATE_MAX_X`, `ORIG_PLATE_MAX_Y` (int)
- `PLATE_COUNTRY_CODE` (string)
- `PLATE_COUNTRY` (string)
- `CHAR_HEIGHT` / `PLATE_CHAR_HEIGHT` (int)

### Ejemplo mínimo
```xml
<root>
  <PLATE_STRING>1234ABC</PLATE_STRING>
  <DEVICE_SN>CAM-001</DEVICE_SN>
  <DATE>2026-01-23</DATE>
  <TIME>09-25-57-000</TIME>
  <IMAGE_OCR>BASE64_OCR...</IMAGE_OCR>
</root>
```

## 2) JSON Lector Vision
El endpoint `POST /ingest/lectorvision` recibe JSON y lo convierte a XML Tattile. Campos obligatorios:
- `Plate`
- `TimeStamp` (formato `YYYY/MM/DD HH:MM:SS.mmm`)
- `SerialNumber` (o `IdDevice` como fallback)

### Campos soportados (mapa → XML Tattile)
- `Plate` → `PLATE_STRING` (obligatorio)
- `SerialNumber` / `IdDevice` → `DEVICE_SN` (obligatorio)
- `TimeStamp` → `DATE` + `TIME` (obligatorio)
- `ImageOcr` / `ImageOCR` / `ImageOcrBase64` / `ImageOCRBase64` / `ImageOcrB64` → `IMAGE_OCR`
- `ImageCtx` / `ImageCTX` / `ImageCtxBase64` / `ImageCTXBase64` / `ImageCtxB64` → `IMAGE_CTX`
- `Fiability` → `OCRSCORE`
- `Direction` → `DIRECTION`
- `LaneNumber` → `LANE_ID`
- `LaneName` → `LANE_DESCR`
- `PlateCoord` (array[4]) → `ORIG_PLATE_MIN_X`, `ORIG_PLATE_MIN_Y`, `ORIG_PLATE_MAX_X`, `ORIG_PLATE_MAX_Y`
- `Country` → `PLATE_COUNTRY_CODE` (+ `PLATE_COUNTRY` = `ES` si `Country == 724`)
- `CharHeight` / `PlateCharHeight` / `PlateCharheight` → `CHAR_HEIGHT`

### Ejemplo seguro
```json
{
  "Plate": "1234ABC",
  "TimeStamp": "2026/01/23 09:25:57.000",
  "SerialNumber": "LV-01",
  "Fiability": 87,
  "LaneNumber": 2,
  "LaneName": "Carril 2",
  "Direction": "IN",
  "PlateCoord": [10, 20, 110, 220],
  "Country": 724
}
```

## 3) Imágenes en disco
Las imágenes se guardan en el directorio configurado (`IMAGES_BASE_DIR`) con esta estructura:

```
<IMAGES_BASE_DIR>/<DEVICE_SN>/YYYY/MM/DD/<YYYYMMDDHHMMSS>_plate-<PLATE>_{ocr|ctx}.jpg
```

- En BD se almacena la **ruta relativa**.
- El sender resuelve rutas relativas contra `IMAGES_BASE_DIR` antes de enviar.
- Si falta la imagen OCR o el fichero no existe, el mensaje se marca `DEAD`.
