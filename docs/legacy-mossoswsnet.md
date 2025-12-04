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
