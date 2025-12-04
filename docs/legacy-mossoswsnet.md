# Sistema legacy: MossosWSNet.exe

## Configuración
El ejecutable Windows actual utiliza un archivo `Configuration.json` con claves
como:
- `LogLevel`: nivel de logs del exe.
- `PortReceiveTransit`: puerto TCP de recepción de lecturas (ej. 33334).
- `CertPath`: ruta al certificado `.pfx` usado para firmar.
- `Password`: contraseña del PFX (**no incluir valor real; usar `[REDACTED]`).
- `Endpoint`: URL del servicio SOAP de Mossos.
- `Camaras`: lista de mapeos `SerialNumber` → `CodigoLector`.

## Comportamiento
- Recibe lecturas Tattile en XML, construye una petición SOAP y la envía al
  endpoint configurado.
- Firma la petición con el certificado PFX indicado en `CertPath`.
- Puede registrar errores tipo `WSE511` cuando el certificado es inválido o está
  caducado.

## Limitaciones observadas
- Dependencia de Windows para la ejecución.
- Gestión limitada de múltiples certificados según cámara o municipio.
- Escasa trazabilidad y herramientas de observabilidad.
- Manejo de errores y reintentos poco configurable.

## Evolución en TattileSender
- El exe legacy mapea `SerialNumber` → `CodigoLector` mediante un único
  `Configuration.json`, con el certificado acoplado al binario y sin un modelo
  de municipios con múltiples certificados almacenado en base de datos.
- TattileSender introduce tablas `municipalities`, `certificates` y `cameras`
  para soportar de forma explícita la relación cámara → municipio → certificado
  (y endpoint), permitiendo gestionar varios municipios y certificados de forma
  escalable y mantenible.
