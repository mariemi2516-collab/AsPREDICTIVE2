from __future__ import annotations

from datetime import datetime, timedelta
from threading import Lock
from typing import Any
import secrets

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from .api_schemas import (
    AlertaCreate,
    AlertaOut,
    ExecutiveReportResponse,
    AuthResponse,
    CatalogAeronaveOut,
    CatalogAeropuertoOut,
    CatalogTipoIncidenteOut,
    DashboardStats,
    DashboardSummaryResponse,
    FormCatalogsResponse,
    IncidenteOut,
    IncidentePayload,
    LoginRequest,
    ModelMetricsOut,
    ModelTraceabilityOut,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    UsuarioOut,
    AuditLogOut,
)
from .config import settings
from .db import Base, engine, ensure_runtime_columns, get_db
from . import institutional_models  # noqa: F401
from .institutional_router import router as institutional_router
from .model_service import RiskPredictor, bootstrap_bundle, build_training_trace, combine_training_rows, load_jst_training_rows, load_ntsb_training_rows, save_bundle, train_bundle
from .models import Aeronave, Aeropuerto, Alerta, AuditLog, Incidente, PasswordResetToken, TipoIncidente, Usuario
from .observability import cleanup_expired_password_resets, log_request_event, logger, write_audit_log
from .schemas import HealthResponse, IncidentePayload as PredictPayload, PredictionResponse
from .seed import seed_initial_data
from .security import create_access_token, decode_access_token, get_password_hash, verify_password


app = FastAPI(title="AsPREDICTIVE API", version="2.0.0")
predictor = RiskPredictor()
training_state: dict[str, Any] = {
    "status": "idle",
    "started_at": None,
    "finished_at": None,
    "last_result": None,
    "last_error": None,
}
training_lock = Lock()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(institutional_router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = datetime.utcnow()
    try:
        response = await call_next(request)
        duration_ms = (datetime.utcnow() - started).total_seconds() * 1000
        log_request_event(request, response.status_code, duration_ms)
        return response
    except Exception as error:
        duration_ms = (datetime.utcnow() - started).total_seconds() * 1000
        logger.exception("unhandled_error path=%s duration_ms=%.2f", request.url.path, duration_ms)
        return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_runtime_columns()
    with Session(bind=engine) as db:
        seed_initial_data(db)
        cleanup_expired_password_resets(db, PasswordResetToken)
        db.commit()


def to_user_out(user: Usuario) -> UsuarioOut:
    return UsuarioOut(
        id=user.id,
        nombre=user.nombre,
        email=user.email,
        rol=user.rol,
        organization_key=user.organization_key,
        estado=user.estado,
        ultimo_login=user.ultimo_login,
        created_at=user.created_at,
    )


def to_incidente_out(incidente: Incidente) -> IncidenteOut:
    return IncidenteOut(
        id=incidente.id,
        organization_key=incidente.organization_key,
        aeropuerto_id=incidente.aeropuerto_id,
        pista_id=incidente.pista_id,
        aeronave_id=incidente.aeronave_id,
        tipo_incidente_id=incidente.tipo_incidente_id,
        fecha_hora=incidente.fecha_hora,
        descripcion=incidente.descripcion,
        nivel_riesgo=incidente.nivel_riesgo,
        fase_vuelo=incidente.fase_vuelo,
        condicion_meteorologica=incidente.condicion_meteorologica,
        condicion_luz=incidente.condicion_luz,
        visibilidad_millas=incidente.visibilidad_millas,
        viento_kt=incidente.viento_kt,
        latitud=incidente.latitud,
        longitud=incidente.longitud,
        reportado_por=incidente.reportado_por,
        created_at=incidente.created_at,
        aeropuertos={
            "nombre": incidente.aeropuerto.nombre,
            "codigo_icao": incidente.aeropuerto.codigo_icao,
        }
        if incidente.aeropuerto
        else None,
        tipos_incidente={"nombre": incidente.tipo_incidente.nombre} if incidente.tipo_incidente else None,
        aeronaves={"matricula": incidente.aeronave.matricula} if incidente.aeronave else None,
    )


def to_alerta_out(alerta: Alerta) -> AlertaOut:
    return AlertaOut(
        id=alerta.id,
        organization_key=alerta.organization_key,
        aeropuerto_id=alerta.aeropuerto_id,
        fecha_generacion=alerta.fecha_generacion,
        tipo_alerta=alerta.tipo_alerta,
        nivel_criticidad=alerta.nivel_criticidad,
        mensaje=alerta.mensaje,
        score_predictivo=float(alerta.score_predictivo) if alerta.score_predictivo is not None else None,
        ejecucion_agente_id=alerta.ejecucion_agente_id,
        estado=alerta.estado,
        atendido_por=alerta.atendido_por,
        fecha_resolucion=alerta.fecha_resolucion,
        aeropuertos={"nombre": alerta.aeropuerto.nombre} if alerta.aeropuerto else None,
    )


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Usuario:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token requerido")

    token = authorization.split(" ", 1)[1]
    try:
        user_id = decode_access_token(token)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error

    user = db.get(Usuario, user_id)
    if not user or not user.estado:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario invÃ¡lido")

    return user


def require_roles(*allowed_roles: str):
    def dependency(current_user: Usuario = Depends(get_current_user)) -> Usuario:
        if current_user.rol not in allowed_roles:
            raise HTTPException(status_code=403, detail="No tienes permisos suficientes")
        return current_user

    return dependency


def get_user_organization_key(current_user: Usuario) -> str:
    return (current_user.organization_key or "default").strip() or "default"


def enforce_same_organization(current_user: Usuario, organization_key: str) -> None:
    if organization_key != get_user_organization_key(current_user):
        raise HTTPException(status_code=403, detail="No tienes permisos para operar sobre otra organizacion")


def fetch_incidentes_with_relations(db: Session, limit: int, organization_key: str = "default") -> list[Incidente]:
    statement = (
        select(Incidente)
        .options(joinedload(Incidente.aeropuerto), joinedload(Incidente.tipo_incidente), joinedload(Incidente.aeronave))
        .where(Incidente.organization_key == organization_key)
        .order_by(Incidente.fecha_hora.desc())
        .limit(limit)
    )
    return list(db.scalars(statement))


def fetch_alertas_with_relations(db: Session, estado: str | None, limit: int, organization_key: str = "default") -> list[Alerta]:
    statement = (
        select(Alerta)
        .options(joinedload(Alerta.aeropuerto))
        .where(Alerta.organization_key == organization_key)
        .order_by(Alerta.fecha_generacion.desc())
        .limit(limit)
    )
    if estado:
        statement = statement.where(Alerta.estado == estado)
    return list(db.scalars(statement))


def calculate_riesgo_promedio(incidentes: list[Incidente]) -> int:
    if not incidentes:
        return 0
    risk_map = {"Bajo": 1, "Medio": 2, "Alto": 3, "Crítico": 4}
    promedio = sum(risk_map.get(incidente.nivel_riesgo or "", 0) for incidente in incidentes) / len(incidentes)
    return round((promedio / 4) * 100)


def calculate_riesgo_futuro(incidentes: list[Incidente]) -> int:
    if not incidentes:
        return 0
    predicciones = [
        predictor.predict(
            PredictPayload(
                aeropuerto_id=incidente.aeropuerto_id,
                tipo_incidente_id=incidente.tipo_incidente_id,
                aeronave_id=incidente.aeronave_id,
                fase_vuelo=incidente.fase_vuelo,
                condicion_meteorologica=incidente.condicion_meteorologica,
                condicion_luz=incidente.condicion_luz,
                visibilidad_millas=incidente.visibilidad_millas,
                viento_kt=incidente.viento_kt,
                descripcion=incidente.descripcion,
                latitud=incidente.latitud,
                longitud=incidente.longitud,
                fecha_hora=incidente.fecha_hora.isoformat(),
            )
        )
        for incidente in incidentes
    ]
    return round(sum(pred.score for pred in predicciones) / len(predicciones))


def build_top_items(items: list[tuple[str, int]]) -> list[dict[str, int | str]]:
    return [{"clave": key, "total": int(total)} for key, total in items if key]


def build_executive_report(db: Session, periodo_dias: int, organization_key: str = "default") -> ExecutiveReportResponse:
    cutoff = datetime.utcnow() - timedelta(days=periodo_dias)
    incidentes_periodo = list(
        db.scalars(
            select(Incidente)
            .options(joinedload(Incidente.aeropuerto), joinedload(Incidente.tipo_incidente), joinedload(Incidente.aeronave))
            .where(Incidente.fecha_hora >= cutoff, Incidente.organization_key == organization_key)
            .order_by(Incidente.fecha_hora.desc())
        )
    )
    alertas_pendientes = db.scalar(
        select(func.count()).select_from(Alerta).where(Alerta.estado == "Pendiente", Alerta.organization_key == organization_key)
    ) or 0
    alertas_resueltas_periodo = (
        db.scalar(
            select(func.count()).select_from(Alerta).where(
                Alerta.fecha_resolucion.is_not(None),
                Alerta.fecha_resolucion >= cutoff,
                Alerta.organization_key == organization_key,
            )
        )
        or 0
    )
    usuarios_activos = (
        db.scalar(select(func.count()).select_from(Usuario).where(Usuario.estado.is_(True), Usuario.organization_key == organization_key))
        or 0
    )
    aeropuertos_monitoreados = db.scalar(select(func.count()).select_from(Aeropuerto)) or 0
    acciones_auditadas_periodo = db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.created_at >= cutoff)) or 0
    incidentes_auditados = (
        db.scalar(select(func.count(func.distinct(AuditLog.resource_id))).where(AuditLog.resource_type == "incidente", AuditLog.created_at >= cutoff))
        or 0
    )

    top_aeropuertos_raw = db.execute(
        select(Aeropuerto.nombre, func.count(Incidente.id))
        .join(Incidente, Incidente.aeropuerto_id == Aeropuerto.id)
        .where(Incidente.fecha_hora >= cutoff, Incidente.organization_key == organization_key)
        .group_by(Aeropuerto.nombre)
        .order_by(func.count(Incidente.id).desc(), Aeropuerto.nombre.asc())
        .limit(5)
    ).all()
    top_tipos_raw = db.execute(
        select(TipoIncidente.nombre, func.count(Incidente.id))
        .join(Incidente, Incidente.tipo_incidente_id == TipoIncidente.id)
        .where(Incidente.fecha_hora >= cutoff, Incidente.organization_key == organization_key)
        .group_by(TipoIncidente.nombre)
        .order_by(func.count(Incidente.id).desc(), TipoIncidente.nombre.asc())
        .limit(5)
    ).all()
    distribucion_riesgo_raw = db.execute(
        select(Incidente.nivel_riesgo, func.count(Incidente.id))
        .where(Incidente.fecha_hora >= cutoff, Incidente.nivel_riesgo.is_not(None), Incidente.organization_key == organization_key)
        .group_by(Incidente.nivel_riesgo)
        .order_by(func.count(Incidente.id).desc())
    ).all()

    incidentes_con_clima = sum(
        1
        for incidente in incidentes_periodo
        if incidente.condicion_meteorologica or incidente.condicion_luz or incidente.visibilidad_millas is not None or incidente.viento_kt is not None
    )
    incidentes_con_geolocalizacion = sum(
        1 for incidente in incidentes_periodo if incidente.latitud is not None and incidente.longitud is not None
    )

    metricas_modelo = predictor.bundle.get("metrics", {})
    recomendaciones = [
        "Incrementar la carga de incidentes argentinos con clima estructurado para fortalecer el ajuste local del modelo.",
        "Priorizar seguimiento sobre aeropuertos y tipos de incidente con mayor recurrencia en el periodo analizado.",
        "Mantener trazabilidad de acciones correctivas y cierre de alertas para evidencia regulatoria ante auditorias.",
    ]

    return ExecutiveReportResponse(
        generado_en=datetime.utcnow(),
        periodo_dias=periodo_dias,
        organismo_referencia="ANAC / SSP / PNSO",
        marco_regulatorio=[
            "Sistema de Gestion de Seguridad Operacional (SMS)",
            "Programa Estatal de Seguridad Operacional (SSP)",
            "Programa Nacional de Seguridad Operacional (PNSO)",
            "Trazabilidad de incidentes, alertas y acciones auditables",
        ],
        estado_modelo={
            "version": predictor.model_version,
            "registros_entrenamiento": int(predictor.bundle.get("training_rows", 0)),
            "accuracy": metricas_modelo.get("accuracy"),
            "balanced_accuracy": metricas_modelo.get("balanced_accuracy"),
            "macro_f1": metricas_modelo.get("macro_f1"),
        },
        resumen_operacional={
            "incidentes_periodo": len(incidentes_periodo),
            "alertas_pendientes": int(alertas_pendientes),
            "alertas_resueltas_periodo": int(alertas_resueltas_periodo),
            "usuarios_activos": int(usuarios_activos),
            "aeropuertos_monitoreados": int(aeropuertos_monitoreados),
            "riesgo_promedio": calculate_riesgo_promedio(incidentes_periodo),
            "riesgo_futuro": calculate_riesgo_futuro(incidentes_periodo[:10]),
        },
        trazabilidad={
            "incidentes_con_clima": int(incidentes_con_clima),
            "incidentes_con_geolocalizacion": int(incidentes_con_geolocalizacion),
            "incidentes_auditados": int(incidentes_auditados),
            "acciones_auditadas_periodo": int(acciones_auditadas_periodo),
        },
        top_aeropuertos=build_top_items(top_aeropuertos_raw),
        top_tipos_incidente=build_top_items(top_tipos_raw),
        distribucion_riesgo=build_top_items(distribucion_riesgo_raw),
        recomendaciones=recomendaciones,
    )


def train_predictive_model_from_db(db: Session) -> dict[str, Any]:
    ntsb_rows = load_ntsb_training_rows()
    jst_rows = load_jst_training_rows()
    postgres_rows = [
        {
            "aeropuerto_id": incidente.aeropuerto_id,
            "tipo_incidente_id": incidente.tipo_incidente_id,
            "aeronave_id": incidente.aeronave_id,
            "fase_vuelo": incidente.fase_vuelo,
            "condicion_meteorologica": incidente.condicion_meteorologica,
            "condicion_luz": incidente.condicion_luz,
            "visibilidad_millas": incidente.visibilidad_millas,
            "viento_kt": incidente.viento_kt,
            "descripcion": incidente.descripcion,
            "latitud": incidente.latitud,
            "longitud": incidente.longitud,
            "fecha_hora": incidente.fecha_hora.isoformat(),
            "nivel_riesgo": incidente.nivel_riesgo,
        }
        for incidente in db.scalars(select(Incidente).where(Incidente.nivel_riesgo.is_not(None)))
    ]

    training_rows, source_name = combine_training_rows([*ntsb_rows, *jst_rows], postgres_rows)

    if len(training_rows) < 12:
        bundle = bootstrap_bundle()
    else:
        traceability = build_training_trace(training_rows, source_name=source_name, postgres_rows=postgres_rows)
        bundle = train_bundle(training_rows, source_name=source_name, traceability=traceability)

    save_bundle(bundle)
    predictor.reload()
    return bundle


def run_training_job() -> None:
    with training_lock:
        training_state["status"] = "running"
        training_state["started_at"] = datetime.utcnow().isoformat()
        training_state["finished_at"] = None
        training_state["last_error"] = None

    try:
        with Session(bind=engine) as db:
            bundle = train_predictive_model_from_db(db)
        with training_lock:
            training_state["status"] = "completed"
            training_state["finished_at"] = datetime.utcnow().isoformat()
            training_state["last_result"] = {
                "training_rows": int(bundle["training_rows"]),
                "model_version": predictor.model_version,
                "metrics": bundle.get("metrics", {}),
            }
    except Exception as error:
        with training_lock:
            training_state["status"] = "failed"
            training_state["finished_at"] = datetime.utcnow().isoformat()
            training_state["last_error"] = str(error)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", model_loaded=True, model_version=predictor.model_version)


@app.post("/auth/register", response_model=AuthResponse)
def register(
    payload: RegisterRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AuthResponse:
    requested_role = payload.rol
    existing_user = db.scalar(select(Usuario).where(Usuario.email == payload.email))
    if existing_user:
        raise HTTPException(status_code=400, detail="Ya existe un usuario con ese correo")

    first_user = db.scalar(select(Usuario.id).limit(1)) is None
    if first_user and not settings.allow_self_registration:
        raise HTTPException(status_code=403, detail="El alta inicial de usuarios requiere aprovisionamiento administrativo")

    actor_user: Usuario | None = None
    if not first_user:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=403, detail="El registro publico esta deshabilitado")
        token = authorization.split(" ", 1)[1]
        try:
            actor_user_id = decode_access_token(token)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error

        actor_user = db.get(Usuario, actor_user_id)
        if not actor_user or not actor_user.estado:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario invÃƒÂ¡lido")
        if actor_user.rol not in {"administrador", "supervisor"}:
            raise HTTPException(status_code=403, detail="No tienes permisos para crear usuarios")

    user = Usuario(
        nombre=payload.nombre,
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        rol="administrador" if first_user else requested_role,
        organization_key=settings.initial_admin_organization_key if first_user else get_user_organization_key(actor_user),
        estado=True,
    )
    db.add(user)
    write_audit_log(
        db,
        actor_user_id=actor_user.id if actor_user else user.id,
        organization_key=user.organization_key,
        action="usuario_registrado",
        resource_type="usuario",
        resource_id=user.id,
        details={"email": user.email, "rol": user.rol, "requested_role": requested_role},
    )
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return AuthResponse(access_token=token, user=to_user_out(user))


@app.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.scalar(select(Usuario).where(Usuario.email == payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales invÃ¡lidas")

    user.ultimo_login = datetime.utcnow()
    write_audit_log(
        db,
        actor_user_id=user.id,
        organization_key=user.organization_key,
        action="inicio_sesion",
        resource_type="usuario",
        resource_id=user.id,
        details={"email": user.email},
    )
    db.commit()

    token = create_access_token(user.id)
    return AuthResponse(access_token=token, user=to_user_out(user))


@app.get("/auth/me", response_model=UsuarioOut)
def me(current_user: Usuario = Depends(get_current_user)) -> UsuarioOut:
    return to_user_out(current_user)


@app.post("/auth/password-reset/request")
def request_password_reset(payload: PasswordResetRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    user = db.scalar(select(Usuario).where(Usuario.email == payload.email))
    if not user:
        return {"status": "ok", "message": "Si el correo existe, se genero una solicitud de recuperacion"}

    token = secrets.token_urlsafe(32)
    reset = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=datetime.utcnow() + timedelta(hours=2),
    )
    db.add(reset)
    write_audit_log(
        db,
        actor_user_id=user.id,
        organization_key=user.organization_key,
        action="solicitud_recuperacion_acceso",
        resource_type="password_reset",
        resource_id=user.id,
        details={"email": user.email},
    )
    db.commit()

    response = {
        "status": "ok",
        "message": "Solicitud generada. Si el usuario existe, el flujo de recuperacion quedo registrado para gestion segura.",
    }
    if settings.expose_password_reset_token:
        response["reset_token"] = token
    return response

@app.post("/auth/password-reset/confirm")
def confirm_password_reset(payload: PasswordResetConfirm, db: Session = Depends(get_db)) -> dict[str, str]:
    reset = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token == payload.token,
            PasswordResetToken.used_at.is_(None),
        )
    )
    if not reset or reset.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Token invÃ¡lido o expirado")

    user = db.get(Usuario, reset.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user.password_hash = get_password_hash(payload.new_password)
    reset.used_at = datetime.utcnow()
    write_audit_log(
        db,
        actor_user_id=user.id,
        organization_key=user.organization_key,
        action="recuperacion_acceso_confirmada",
        resource_type="usuario",
        resource_id=user.id,
        details={"email": user.email},
    )
    db.commit()
    return {"status": "ok", "message": "ContraseÃ±a actualizada correctamente"}


@app.get("/catalogs/aeropuertos", response_model=list[CatalogAeropuertoOut])
def list_aeropuertos(
    _: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CatalogAeropuertoOut]:
    aeropuertos = list(db.scalars(select(Aeropuerto).order_by(Aeropuerto.nombre.asc())))
    return [CatalogAeropuertoOut.model_validate(aeropuerto, from_attributes=True) for aeropuerto in aeropuertos]


@app.get("/catalogs/aeropuertos/count")
def count_aeropuertos(
    _: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    total = db.scalar(select(func.count()).select_from(Aeropuerto)) or 0
    return {"total": int(total)}


@app.get("/catalogs/tipos-incidente", response_model=list[CatalogTipoIncidenteOut])
def list_tipos_incidente(
    _: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CatalogTipoIncidenteOut]:
    tipos = list(db.scalars(select(TipoIncidente).order_by(TipoIncidente.nombre.asc())))
    return [CatalogTipoIncidenteOut.model_validate(tipo, from_attributes=True) for tipo in tipos]


@app.get("/catalogs/aeronaves", response_model=list[CatalogAeronaveOut])
def list_aeronaves(
    _: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CatalogAeronaveOut]:
    aeronaves = list(db.scalars(select(Aeronave).order_by(Aeronave.matricula.asc())))
    return [CatalogAeronaveOut.model_validate(aeronave, from_attributes=True) for aeronave in aeronaves]


@app.get("/catalogs/form-data", response_model=FormCatalogsResponse)
def form_data(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FormCatalogsResponse:
    return FormCatalogsResponse(
        aeropuertos=list_aeropuertos(current_user, db),
        tipos_incidente=list_tipos_incidente(current_user, db),
        aeronaves=list_aeronaves(current_user, db),
    )


@app.get("/incidentes", response_model=list[IncidenteOut])
def list_incidentes(
    limit: int = Query(default=50, ge=1, le=500),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[IncidenteOut]:
    incidentes = fetch_incidentes_with_relations(db, limit, organization_key=get_user_organization_key(current_user))
    return [to_incidente_out(incidente) for incidente in incidentes]


@app.post("/incidentes", response_model=IncidenteOut, status_code=201)
def create_incidente(
    payload: IncidentePayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IncidenteOut:
    incidente = Incidente(
        organization_key=get_user_organization_key(current_user),
        aeropuerto_id=payload.aeropuerto_id,
        tipo_incidente_id=payload.tipo_incidente_id,
        aeronave_id=payload.aeronave_id,
        fecha_hora=payload.fecha_hora,
        descripcion=payload.descripcion,
        nivel_riesgo=payload.nivel_riesgo,
        fase_vuelo=payload.fase_vuelo,
        condicion_meteorologica=payload.condicion_meteorologica,
        condicion_luz=payload.condicion_luz,
        visibilidad_millas=payload.visibilidad_millas,
        viento_kt=payload.viento_kt,
        latitud=payload.latitud,
        longitud=payload.longitud,
        reportado_por=current_user.id,
    )
    db.add(incidente)
    write_audit_log(
        db,
        actor_user_id=current_user.id,
        organization_key=incidente.organization_key,
        action="incidente_creado",
        resource_type="incidente",
        details={"aeropuerto_id": payload.aeropuerto_id, "nivel_riesgo": payload.nivel_riesgo, "organization_key": incidente.organization_key},
    )
    db.commit()
    db.refresh(incidente)
    incidente = db.scalar(
        select(Incidente)
        .options(joinedload(Incidente.aeropuerto), joinedload(Incidente.tipo_incidente), joinedload(Incidente.aeronave))
        .where(Incidente.id == incidente.id)
    )
    return to_incidente_out(incidente)


@app.put("/incidentes/{incidente_id}", response_model=IncidenteOut)
def update_incidente(
    incidente_id: int,
    payload: IncidentePayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IncidenteOut:
    incidente = db.get(Incidente, incidente_id)
    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
    enforce_same_organization(current_user, incidente.organization_key)

    incidente.aeropuerto_id = payload.aeropuerto_id
    incidente.tipo_incidente_id = payload.tipo_incidente_id
    incidente.aeronave_id = payload.aeronave_id
    incidente.fecha_hora = payload.fecha_hora
    incidente.descripcion = payload.descripcion
    incidente.nivel_riesgo = payload.nivel_riesgo
    incidente.fase_vuelo = payload.fase_vuelo
    incidente.condicion_meteorologica = payload.condicion_meteorologica
    incidente.condicion_luz = payload.condicion_luz
    incidente.visibilidad_millas = payload.visibilidad_millas
    incidente.viento_kt = payload.viento_kt
    incidente.latitud = payload.latitud
    incidente.longitud = payload.longitud
    write_audit_log(
        db,
        actor_user_id=current_user.id,
        organization_key=incidente.organization_key,
        action="incidente_actualizado",
        resource_type="incidente",
        resource_id=str(incidente_id),
        details={"nivel_riesgo": payload.nivel_riesgo, "organization_key": incidente.organization_key},
    )
    db.commit()

    incidente = db.scalar(
        select(Incidente)
        .options(joinedload(Incidente.aeropuerto), joinedload(Incidente.tipo_incidente), joinedload(Incidente.aeronave))
        .where(Incidente.id == incidente_id)
    )
    return to_incidente_out(incidente)


@app.get("/alertas", response_model=list[AlertaOut])
def list_alertas(
    estado: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=200),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AlertaOut]:
    alertas = fetch_alertas_with_relations(db, estado, limit, organization_key=get_user_organization_key(current_user))
    return [to_alerta_out(alerta) for alerta in alertas]


@app.post("/alertas", response_model=AlertaOut, status_code=201)
def create_alerta(
    payload: AlertaCreate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertaOut:
    alerta = Alerta(
        organization_key=get_user_organization_key(current_user),
        aeropuerto_id=payload.aeropuerto_id,
        tipo_alerta=payload.tipo_alerta,
        nivel_criticidad=payload.nivel_criticidad,
        mensaje=payload.mensaje,
        score_predictivo=payload.score_predictivo,
        estado=payload.estado,
    )
    db.add(alerta)
    write_audit_log(
        db,
        actor_user_id=current_user.id,
        organization_key=alerta.organization_key,
        action="alerta_creada",
        resource_type="alerta",
        details={"tipo_alerta": payload.tipo_alerta, "nivel_criticidad": payload.nivel_criticidad, "organization_key": alerta.organization_key},
    )
    db.commit()
    db.refresh(alerta)
    alerta = db.scalar(select(Alerta).options(joinedload(Alerta.aeropuerto)).where(Alerta.id == alerta.id))
    return to_alerta_out(alerta)


@app.post("/alertas/{alerta_id}/resolve", response_model=AlertaOut)
def resolve_alerta(
    alerta_id: int,
    current_user: Usuario = Depends(require_roles("administrador", "supervisor", "inspector")),
    db: Session = Depends(get_db),
) -> AlertaOut:
    alerta = db.get(Alerta, alerta_id)
    if not alerta:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    enforce_same_organization(current_user, alerta.organization_key)

    alerta.estado = "Resuelta"
    alerta.atendido_por = current_user.id
    alerta.fecha_resolucion = datetime.utcnow()
    write_audit_log(
        db,
        actor_user_id=current_user.id,
        organization_key=alerta.organization_key,
        action="alerta_resuelta",
        resource_type="alerta",
        resource_id=str(alerta_id),
        details={"estado": alerta.estado},
    )
    db.commit()

    alerta = db.scalar(select(Alerta).options(joinedload(Alerta.aeropuerto)).where(Alerta.id == alerta_id))
    return to_alerta_out(alerta)


@app.get("/dashboard/summary", response_model=DashboardSummaryResponse)
def dashboard_summary(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardSummaryResponse:
    organization_key = get_user_organization_key(current_user)
    recent_incidentes = fetch_incidentes_with_relations(db, 5, organization_key=organization_key)
    all_incidentes = fetch_incidentes_with_relations(db, 200, organization_key=organization_key)
    alertas = fetch_alertas_with_relations(db, "Pendiente", 10, organization_key=organization_key)

    total_incidentes = db.scalar(select(func.count()).select_from(Incidente).where(Incidente.organization_key == organization_key)) or 0
    total_aeropuertos = db.scalar(select(func.count()).select_from(Aeropuerto)) or 0

    stats = DashboardStats(
        totalIncidentes=int(total_incidentes),
        alertasActivas=len(alertas),
        aeropuertos=int(total_aeropuertos),
        riesgoPromedio=calculate_riesgo_promedio(all_incidentes),
        riesgoFuturo=calculate_riesgo_futuro(recent_incidentes),
    )

    return DashboardSummaryResponse(
        stats=stats,
        recentIncidentes=[to_incidente_out(incidente) for incidente in recent_incidentes],
        alertas=[to_alerta_out(alerta) for alerta in alertas],
    )


@app.post("/predict", response_model=PredictionResponse)
def predict(payload: PredictPayload) -> PredictionResponse:
    result = predictor.predict(payload)
    return PredictionResponse(score=result.score, nivel=result.nivel, factores=result.factores, modelo=result.modelo)


@app.get("/model/metrics", response_model=ModelMetricsOut)
def model_metrics(_: Usuario = Depends(get_current_user)) -> ModelMetricsOut:
    metrics = predictor.bundle.get("metrics", {})
    return ModelMetricsOut(
        model_version=predictor.model_version,
        training_rows=int(predictor.bundle.get("training_rows", 0)),
        accuracy=metrics.get("accuracy"),
        balanced_accuracy=metrics.get("balanced_accuracy"),
        macro_f1=metrics.get("macro_f1"),
        samples_train=metrics.get("samples_train"),
        samples_test=metrics.get("samples_test"),
    )


@app.get("/model/traceability", response_model=ModelTraceabilityOut)
def model_traceability(_: Usuario = Depends(require_roles("administrador", "supervisor", "analista"))) -> ModelTraceabilityOut:
    return ModelTraceabilityOut(
        model_version=predictor.model_version,
        training_rows=int(predictor.bundle.get("training_rows", 0)),
        traceability=predictor.bundle.get("traceability", {}),
    )


@app.get("/reports/executive", response_model=ExecutiveReportResponse)
def executive_report(
    periodo_dias: int = Query(default=90, ge=7, le=365),
    current_user: Usuario = Depends(require_roles("administrador", "supervisor", "analista")),
    db: Session = Depends(get_db),
) -> ExecutiveReportResponse:
    return build_executive_report(db, periodo_dias, organization_key=get_user_organization_key(current_user))


@app.get("/audit-logs", response_model=list[AuditLogOut])
def list_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    current_user: Usuario = Depends(require_roles("administrador", "supervisor")),
    db: Session = Depends(get_db),
) -> list[AuditLogOut]:
    logs = list(
        db.scalars(
            select(AuditLog)
            .where(AuditLog.organization_key == get_user_organization_key(current_user))
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
    )
    return [
        AuditLogOut(
            id=log.id,
            actor_user_id=log.actor_user_id,
            organization_key=log.organization_key,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            details_json=log.details_json,
            created_at=log.created_at,
        )
        for log in logs
    ]


@app.get("/train/status")
def train_status(_: Usuario = Depends(require_roles("administrador", "analista", "supervisor"))) -> dict[str, Any]:
    with training_lock:
        return dict(training_state)


@app.post("/train")
def train_model(
    background_tasks: BackgroundTasks,
    background: bool = Query(default=True),
    _: Usuario = Depends(require_roles("administrador", "analista")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if background:
        with training_lock:
            if training_state["status"] == "running":
                return {"status": "running", "detail": "Ya existe un entrenamiento en curso"}
            training_state["status"] = "queued"
            training_state["started_at"] = datetime.utcnow().isoformat()
            training_state["finished_at"] = None
            training_state["last_error"] = None
        background_tasks.add_task(run_training_job)
        return {"status": "queued", "detail": "Entrenamiento enviado a segundo plano"}

    bundle = train_predictive_model_from_db(db)
    with training_lock:
        training_state["status"] = "completed"
        training_state["started_at"] = datetime.utcnow().isoformat()
        training_state["finished_at"] = datetime.utcnow().isoformat()
        training_state["last_result"] = {
            "training_rows": int(bundle["training_rows"]),
            "model_version": predictor.model_version,
            "metrics": bundle.get("metrics", {}),
        }
        training_state["last_error"] = None
    return {
        "status": "ok",
        "training_rows": int(bundle["training_rows"]),
        "model_version": predictor.model_version,
        "metrics": bundle.get("metrics", {}),
    }

