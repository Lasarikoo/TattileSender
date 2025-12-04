# Guía de contribución

## Flujo de ramas
- `main`: estado listo para producción.
- `develop`: integración continua de cambios que luego se promueven a `main`.
- `feature/<nombre>`: ramas para nuevas funcionalidades o mejoras.

## Pasos básicos
1. Crear rama de trabajo: `git checkout -b feature/<nombre>` desde `develop`.
2. Realizar cambios con commits pequeños y mensajes claros.
3. Ejecutar pruebas y validaciones locales.
4. Crear Pull Request hacia `develop`, describiendo el alcance y pruebas
   ejecutadas.
5. Tras revisión y merge en `develop`, preparar un PR de release hacia `main`
   cuando corresponda desplegar.

## Buenas prácticas de commits
- Mensajes en imperativo y descriptivos (ej.: "Añadir endpoint de salud").
- Incluir referencias a issues o tareas cuando aplique.
- Evitar commits que mezclen cambios no relacionados.

## Código y estilo
- Mantener comentarios y documentación en español.
- Evitar introducir secretos o certificados en el repositorio.
- Seguir la estructura de carpetas establecida en la Fase 0 para mantener
  claridad y separación de responsabilidades.
