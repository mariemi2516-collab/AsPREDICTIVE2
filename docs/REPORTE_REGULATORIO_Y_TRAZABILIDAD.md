# Reporte regulatorio y trazabilidad

## Proposito

AsPREDICTIVE genera evidencia operativa y analitica para apoyar actividades de gestion de seguridad operacional, supervision y trazabilidad institucional.

## Endpoint principal

- `GET /reports/executive?periodo_dias=90`
- `GET /model/traceability`

## Contenido del reporte

- fecha y hora de generacion
- periodo analizado
- organismo de referencia
- marco regulatorio de uso
- estado del modelo predictivo
- resumen operacional del periodo
- trazabilidad de carga, auditoria y calidad del dato
- top de aeropuertos
- top de tipos de incidente
- distribucion de riesgo
- recomendaciones operativas

## Trazabilidad explicita incluida

- incidentes con clima estructurado
- incidentes con geolocalizacion
- incidentes con evidencia de auditoria
- acciones auditadas dentro del periodo
- alertas pendientes y resueltas
- version y volumen de entrenamiento del modelo
- hashes y metadatos de archivos fuente usados en entrenamiento
- cobertura del mapping JST y codigos de evento no catalogados
- manifiesto exportable en `backend/models/traces/latest_training_trace.json`

## Uso sugerido frente a ANAC

- tablero de apoyo a supervision y vigilancia
- priorizacion de focos operacionales
- evidencia de carga y seguimiento de incidentes
- soporte para cultura SMS / SSP / PNSO
- respaldo documental para reuniones tecnicas y piloto regulatorio

## Alcance actual

El sistema no reemplaza la investigacion oficial ni la potestad regulatoria.
Opera como plataforma de apoyo para:

- captura y normalizacion de incidentes
- analitica de riesgo
- alertas tempranas
- trazabilidad de acciones
- evidencia ejecutiva y operativa
