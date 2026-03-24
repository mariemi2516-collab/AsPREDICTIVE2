# SLA, monitoreo y roadmap

## Objetivo

Definir una base operativa madura para evolucionar AsPREDICTIVE hacia un entorno institucional.

## SLA inicial recomendado para piloto

- disponibilidad objetivo: 99,5%
- tiempo objetivo de respuesta API: menor a 2 segundos para operaciones de lectura
- tiempo objetivo de atencion de incidente tecnico critico: menor a 4 horas
- respaldo de base: diario
- reentrenamiento del modelo: semanal o ante lote relevante de incidentes nuevos

## Monitoreo minimo

- `GET /health`
- `GET /model/metrics`
- `GET /reports/executive`
- verificacion de backlog de alertas pendientes
- verificacion de auditoria y acciones correctivas abiertas
- chequeo de jobs de backup

## Soporte minimo sugerido

- canal tecnico para incidentes de operacion
- responsable funcional por organizacion
- responsable tecnico de plataforma
- bitacora de cambios y redeploys

## Roadmap siguiente

### Captura offline

- convertir frontend en PWA
- cola local de eventos
- sincronizacion diferida
- resolucion de conflictos

### Notificaciones automaticas robustas

- correo transaccional
- alertas por umbral y vencimiento
- notificaciones de cursos vencidos
- resumen operativo diario

### Exportes regulatorios formales en PDF

- reporte ejecutivo con membrete institucional
- estado del modelo
- top riesgos
- auditorias e inspecciones
- acciones correctivas

### Hardening adicional

- monitoreo externo
- rotacion de secretos
- backups versionados
- bitacora de disponibilidad
- registro de cambios de modelo
