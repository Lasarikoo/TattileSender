# Integración SOAP (Lectio / MATR-WS)

TattileSender envía lecturas al servicio SOAP de Mossos mediante Zeep con firma WS-Security y timestamp.

## Operación usada
- **Operación:** `matricula`
- **Binding:** `MatriculesSoap11`
- **WSDL:** configurable por `MOSSOS_WSDL_URL` (se recomienda usar el WSDL oficial proporcionado por Mossos).
- **Endpoint efectivo:**
  1) `endpoint.url` de la cámara/municipio en BD, o
  2) `MOSSOS_ENDPOINT_URL` como fallback.

## Seguridad WS-Security
- Se firma el Body y un `Timestamp` (`wsu:Timestamp`) dentro de `wsse:Security`.
- Se usa un certificado cliente (`client.pem`) y su clave privada (`key.pem`).
- La respuesta SOAP no se verifica con WS-Security (no viene firmada).

## Payload SOAP (campos)
El cuerpo SOAP envía la información como parámetros de `matricula`:

| Campo SOAP | Origen | Notas |
| --- | --- | --- |
| `codiLector` | `Camera.codigo_lector` | Obligatorio para identificar cámara. |
| `matricula` | `AlprReading.plate` | Se normaliza a mayúsculas y se recorta a 10 caracteres. |
| `dataLectura` | `AlprReading.timestamp_utc` | Formato `YYYY-MM-DD`. |
| `horaLectura` | `AlprReading.timestamp_utc` | Formato `HH:MM:SS`. |
| `imgMatricula` | Imagen OCR en Base64 | Requerida. |
| `imgContext` | Imagen contexto en Base64 | Opcional si existe. |
| `coordenadaX` / `coordenadaY` | `Camera.coord_x`/`coord_y` o `utm_x`/`utm_y` | Se envían si están disponibles. |
| `marca` / `model` / `color` / `tipusVehicle` / `pais` | Campos de `AlprReading` | *No se rellenan actualmente en la ingesta; quedan reservados.* |

## Ejemplo SOAP (placeholders)
```xml
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:mat="http://dgp.gencat.cat/matricules">
  <soapenv:Header>
    <wsse:Security>...</wsse:Security>
  </soapenv:Header>
  <soapenv:Body>
    <mat:matricula>
      <codiLector>LEC-0001</codiLector>
      <matricula>1234ABC</matricula>
      <dataLectura>2026-01-23</dataLectura>
      <horaLectura>09:25:57</horaLectura>
      <imgMatricula>BASE64_OCR...</imgMatricula>
      <imgContext>BASE64_CTX...</imgContext>
      <coordenadaX>430123.45</coordenadaX>
      <coordenadaY>4578123.45</coordenadaY>
    </mat:matricula>
  </soapenv:Body>
</soapenv:Envelope>
```

## Gestión de errores y reintentos
- **Códigos de éxito:** `1`, `0000`, `OK`, `1.0`.
- **Errores de datos / respuesta:** si `codiRetorn` es distinto de los códigos OK, el mensaje pasa a `DEAD`.
- **Errores de transporte o SOAP Fault:** se marca como `FAILED` y se reintenta según `retry_max` / `retry_backoff_ms`.
- **Sin imagen OCR:** la lectura se descarta (`DEAD`).

## Depuración
- Establece `SOAP_DEBUG=1` para imprimir el envelope SOAP en logs (útil en QA).
