# Validacion funcional en produccion

## Objetivo

Validar de punta a punta que la plataforma opere correctamente en ambiente desplegado antes de una presentacion institucional.

## Precondiciones

- Frontend activo en Netlify
- Backend activo en Render
- PostgreSQL activo en Neon
- Migracion de clima ejecutada sobre `incidentes`
- Usuario con rol `administrador`

## Flujo minimo obligatorio

1. Abrir la aplicacion y validar acceso al login.
2. Ingresar con usuario administrador.
3. Confirmar carga del dashboard sin errores visibles.
4. Verificar `GET /health`.
5. Verificar `GET /model/metrics`.
6. Verificar `GET /reports/executive?periodo_dias=90`.
7. Crear un incidente con:
   - aeropuerto
   - tipo de incidente
   - aeronave
   - fase de vuelo
   - clima estructurado
8. Confirmar que el incidente aparece en tabla y dashboard.
9. Confirmar que la prediccion IA devuelve score, nivel y factores.
10. Verificar creacion de alerta predictiva si el riesgo supera el umbral.
11. Resolver una alerta con usuario habilitado.
12. Verificar que la accion quede reflejada en `GET /audit-logs`.
13. Ejecutar `POST /train`.
14. Confirmar que el modelo sigue disponible y que el reporte ejecutivo refleja datos actuales.

## Criterios de aceptacion

- No hay errores 500 durante el flujo
- Login, dashboard, incidentes y alertas funcionan
- El incidente guarda clima y geolocalizacion
- La accion queda auditada
- El modelo responde antes y despues del reentrenamiento
- El reporte ejecutivo muestra KPIs y trazabilidad

## Evidencia sugerida para ANAC

- Captura del dashboard
- Captura del incidente creado
- Captura del reporte ejecutivo
- Captura de auditoria
- Respuesta de `/model/metrics`
- Respuesta de `/reports/executive`
