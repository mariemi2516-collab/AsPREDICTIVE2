# PWA y modo offline

## Alcance implementado

- frontend instalable como PWA con `manifest.webmanifest`
- `service worker` para shell de aplicacion
- banner de estado de conectividad
- cola local persistente en `localStorage`
- sincronizacion automatica al recuperar conexion
- sincronizacion manual desde interfaz

## Operaciones que hoy pueden encolarse offline

- crear incidente
- actualizar incidente
- resolver alerta
- crear inspeccion
- eliminar inspeccion
- eliminar inspecciones de prueba
- crear accion correctiva
- actualizar estado de accion correctiva
- marcar una notificacion como leida
- marcar todas las notificaciones como leidas

## Regla actual de conflictos

- primera version: se reenvian las operaciones en el orden en que fueron capturadas
- si una operacion falla en sincronizacion, se mueve a una bandeja local de conflictos
- el usuario puede reintentar o descartar manualmente cada conflicto
- el criterio actual es operativo y simple: la ultima operacion aceptada por backend prevalece

## Limitaciones actuales

- no hay todavia resolucion visual avanzada de conflictos
- no hay soporte offline completo para capacitaciones encadenadas
- no hay almacenamiento cifrado local
- no hay background sync del navegador con reintento inteligente por lotes
- no hay merge semantico por campo ni conciliacion automatica por version

## Siguiente evolucion recomendada

- IndexedDB para cola mas robusta
- background sync cuando el navegador lo soporte
- versionado por registro para detectar conflicto real
- pantalla de conciliacion manual
- empaquetado movil o contenedor nativo
