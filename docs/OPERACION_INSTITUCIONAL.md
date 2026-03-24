# Operacion institucional

## Alcance

Documento base para operacion controlada del sistema en un piloto institucional.

## Componentes

- Frontend Netlify
- Backend FastAPI en Render
- PostgreSQL en Neon
- Modelo predictivo con entrenamiento mixto NTSB + JST + operacion local

## Rutina diaria sugerida

1. Verificar `/health`
2. Verificar `/model/metrics`
3. Verificar `/reports/executive?periodo_dias=30`
4. Revisar alertas pendientes
5. Confirmar cargas nuevas del dia

## Rutina semanal sugerida

1. Ejecutar backup de base
2. Revisar auditoria
3. Importar incidentes argentinos nuevos si existen
4. Ejecutar reentrenamiento
5. Exportar reporte ejecutivo

## Control de cambios

- cambios de catalogos: mediante seed y versionado Git
- cambios de esquema: mediante SQL controlado
- cambios del modelo: mediante `train_model.py` o `POST /train`

## Evidencia operativa minima

- logs de salud de servicio
- auditoria de accesos y acciones
- version del modelo en uso
- volumen de entrenamiento
- reporte ejecutivo vigente

## Riesgos operativos a vigilar

- datos incompletos en incidentes
- baja cobertura de clima estructurado
- usuarios sin cierre de alertas
- falta de reentrenamiento periodico
- divergencia entre catalogos y operacion real
