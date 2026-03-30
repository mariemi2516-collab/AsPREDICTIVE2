# Seguridad comercial y gobierno del sistema

## Roles

- `administrador`: alta de usuarios de su organizacion, entrenamiento, auditoria, gestion integral
- `supervisor`: lectura integral, resolucion de alertas, auditoria y alta controlada de usuarios de su organizacion
- `inspector`: gestion de incidentes y resolucion de alertas
- `analista`: analisis, entrenamiento del modelo, lectura operativa

## Controles implementados

- JWT para sesion
- verificacion de roles en endpoints sensibles
- aislamiento por `organization_key` derivado del usuario autenticado
- registro publico deshabilitado por defecto
- auditoria de:
  - registro de usuario
  - inicio de sesion
  - creacion y actualizacion de incidentes
  - creacion y resolucion de alertas
  - recuperacion de acceso

## Altas de usuario

- El alta inicial requiere aprovisionar `INITIAL_ADMIN_EMAIL` y `INITIAL_ADMIN_PASSWORD`.
- El registro publico queda deshabilitado por defecto.
- La creacion posterior de usuarios debe realizarla un `administrador` o `supervisor` autenticado dentro de su propia organizacion.

## Recuperacion de acceso

Endpoints:

- `POST /auth/password-reset/request`
- `POST /auth/password-reset/confirm`

En configuracion segura el token no se devuelve al cliente.
Solo puede exponerse si `EXPOSE_PASSWORD_RESET_TOKEN=true` en un entorno controlado.
Para produccion comercial se recomienda integrarlo con correo corporativo o mesa de ayuda interna.
