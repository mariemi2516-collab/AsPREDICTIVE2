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
- `GET /institutional/notifications`
- `GET /institutional/exports/regulatory`
- `GET /institutional/exports/regulatory/pdf`
- verificacion de backlog de alertas pendientes
- verificacion de auditoria y acciones correctivas abiertas
- verificacion de inspecciones pendientes con criticidad alta o critica
- verificacion de capacitaciones vencidas
- chequeo de jobs de backup

## Soporte operativo sugerido

- ventana de soporte de lunes a viernes en horario operativo
- guardia pasiva para incidentes criticos de disponibilidad
- registro de ticket, severidad, responsable y fecha de resolucion
- runbook para login, API, base de datos, modelo y despliegue
- revision semanal de alertas predictivas, auditorias y acciones vencidas

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

- recordatorios por inspecciones pendientes de alta criticidad
- alertas por vencimiento de acciones correctivas
- notificaciones de cursos vencidos
- marcado masivo de lectura
- evolucion posterior a correo transaccional y resumen operativo diario

### Exportes regulatorios formales en PDF

- reporte regulatorio descargable en texto y PDF
- estado del modelo
- auditorias e inspecciones
- acciones correctivas
- base para version con membrete institucional y firma

### Hardening adicional

- monitoreo externo
- rotacion de secretos
- backups versionados
- bitacora de disponibilidad
- registro de cambios de modelo
