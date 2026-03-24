from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from .api_schemas import (
    AlertaCreate,
    AlertaOut,
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
    RegisterRequest,
    UsuarioOut,
)
from .config import settings
from .db import Base, engine, get_db
from .model_service import RiskPredictor, bootstrap_bundle, save_bundle, train_bundle
from .models import Aeronave, Aeropuerto, Alerta, Incidente, TipoIncidente, Usuario
from .schemas import HealthResponse, IncidentePayload as PredictPayload, PredictionResponse
from .seed import seed_initial_data
from .security import create_access_token, decode_access_token, get_password_hash, verify_password


app = FastAPI(title="AsPREDICTIVE API", version="2.0.0")
predictor = RiskPredictor()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    with Session(bind=engine) as db:
        seed_initial_data(db)


def to_user_out(user: Usuario) -> UsuarioOut:
    return UsuarioOut(
        id=user.id,
        nombre=user.nombre,
        email=user.email,
        rol=user.rol,
        estado=user.estado,
        ultimo_login=user.ultimo_login,
        created_at=user.created_at,
    )


def to_incidente_out(incidente: Incidente) -> IncidenteOut:
    return IncidenteOut(
        id=incidente.id,
        aeropuerto_id=incidente.aeropuerto_id,
        pista_id=incidente.pista_id,
        aeronave_id=incidente.aeronave_id,
        tipo_incidente_id=incidente.tipo_incidente_id,
        fecha_hora=incidente.fecha_hora,
        descripcion=incidente.descripcion,
        nivel_riesgo=incidente.nivel_riesgo,
        fase_vuelo=incidente.fase_vuelo,
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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inválido")

    return user


def fetch_incidentes_with_relations(db: Session, limit: int) -> list[Incidente]:
    statement = (
        select(Incidente)
        .options(joinedload(Incidente.aeropuerto), joinedload(Incidente.tipo_incidente), joinedload(Incidente.aeronave))
        .order_by(Incidente.fecha_hora.desc())
        .limit(limit)
    )
    return list(db.scalars(statement))


def fetch_alertas_with_relations(db: Session, estado: str | None, limit: int) -> list[Alerta]:
    statement = select(Alerta).options(joinedload(Alerta.aeropuerto)).order_by(Alerta.fecha_generacion.desc()).limit(limit)
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
                descripcion=incidente.descripcion,
                latitud=incidente.latitud,
                longitud=incidente.longitud,
                fecha_hora=incidente.fecha_hora.isoformat(),
            )
        )
        for incidente in incidentes
    ]
    return round(sum(pred.score for pred in predicciones) / len(predicciones))


def train_predictive_model_from_db(db: Session) -> dict[str, Any]:
    rows = [
        {
            "aeropuerto_id": incidente.aeropuerto_id,
            "tipo_incidente_id": incidente.tipo_incidente_id,
            "aeronave_id": incidente.aeronave_id,
            "fase_vuelo": incidente.fase_vuelo,
            "descripcion": incidente.descripcion,
            "latitud": incidente.latitud,
            "longitud": incidente.longitud,
            "fecha_hora": incidente.fecha_hora.isoformat(),
            "nivel_riesgo": incidente.nivel_riesgo,
        }
        for incidente in db.scalars(select(Incidente).where(Incidente.nivel_riesgo.is_not(None)))
    ]

    if len(rows) < 12:
        bundle = bootstrap_bundle()
    else:
        bundle = train_bundle(rows, source_name="postgresql")

    save_bundle(bundle)
    predictor.reload()
    return bundle


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", model_loaded=True, model_version=predictor.model_version)


@app.post("/auth/register", response_model=AuthResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    existing_user = db.scalar(select(Usuario).where(Usuario.email == payload.email))
    if existing_user:
        raise HTTPException(status_code=400, detail="Ya existe un usuario con ese correo")

    user = Usuario(
        nombre=payload.nombre,
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        rol=payload.rol,
        estado=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return AuthResponse(access_token=token, user=to_user_out(user))


@app.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.scalar(select(Usuario).where(Usuario.email == payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    user.ultimo_login = datetime.utcnow()
    db.commit()

    token = create_access_token(user.id)
    return AuthResponse(access_token=token, user=to_user_out(user))


@app.get("/auth/me", response_model=UsuarioOut)
def me(current_user: Usuario = Depends(get_current_user)) -> UsuarioOut:
    return to_user_out(current_user)


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
    _: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[IncidenteOut]:
    incidentes = fetch_incidentes_with_relations(db, limit)
    return [to_incidente_out(incidente) for incidente in incidentes]


@app.post("/incidentes", response_model=IncidenteOut, status_code=201)
def create_incidente(
    payload: IncidentePayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IncidenteOut:
    incidente = Incidente(
        aeropuerto_id=payload.aeropuerto_id,
        tipo_incidente_id=payload.tipo_incidente_id,
        aeronave_id=payload.aeronave_id,
        fecha_hora=payload.fecha_hora,
        descripcion=payload.descripcion,
        nivel_riesgo=payload.nivel_riesgo,
        fase_vuelo=payload.fase_vuelo,
        latitud=payload.latitud,
        longitud=payload.longitud,
        reportado_por=current_user.id,
    )
    db.add(incidente)
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
    _: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IncidenteOut:
    incidente = db.get(Incidente, incidente_id)
    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")

    incidente.aeropuerto_id = payload.aeropuerto_id
    incidente.tipo_incidente_id = payload.tipo_incidente_id
    incidente.aeronave_id = payload.aeronave_id
    incidente.fecha_hora = payload.fecha_hora
    incidente.descripcion = payload.descripcion
    incidente.nivel_riesgo = payload.nivel_riesgo
    incidente.fase_vuelo = payload.fase_vuelo
    incidente.latitud = payload.latitud
    incidente.longitud = payload.longitud
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
    _: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AlertaOut]:
    alertas = fetch_alertas_with_relations(db, estado, limit)
    return [to_alerta_out(alerta) for alerta in alertas]


@app.post("/alertas", response_model=AlertaOut, status_code=201)
def create_alerta(
    payload: AlertaCreate,
    _: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertaOut:
    alerta = Alerta(
        aeropuerto_id=payload.aeropuerto_id,
        tipo_alerta=payload.tipo_alerta,
        nivel_criticidad=payload.nivel_criticidad,
        mensaje=payload.mensaje,
        score_predictivo=payload.score_predictivo,
        estado=payload.estado,
    )
    db.add(alerta)
    db.commit()
    db.refresh(alerta)
    alerta = db.scalar(select(Alerta).options(joinedload(Alerta.aeropuerto)).where(Alerta.id == alerta.id))
    return to_alerta_out(alerta)


@app.post("/alertas/{alerta_id}/resolve", response_model=AlertaOut)
def resolve_alerta(
    alerta_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertaOut:
    alerta = db.get(Alerta, alerta_id)
    if not alerta:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")

    alerta.estado = "Resuelta"
    alerta.atendido_por = current_user.id
    alerta.fecha_resolucion = datetime.utcnow()
    db.commit()

    alerta = db.scalar(select(Alerta).options(joinedload(Alerta.aeropuerto)).where(Alerta.id == alerta_id))
    return to_alerta_out(alerta)


@app.get("/dashboard/summary", response_model=DashboardSummaryResponse)
def dashboard_summary(
    _: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardSummaryResponse:
    recent_incidentes = fetch_incidentes_with_relations(db, 5)
    all_incidentes = fetch_incidentes_with_relations(db, 200)
    alertas = fetch_alertas_with_relations(db, "Pendiente", 10)

    total_incidentes = db.scalar(select(func.count()).select_from(Incidente)) or 0
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


@app.post("/train")
def train_model(
    _: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str | int]:
    bundle = train_predictive_model_from_db(db)
    return {
        "status": "ok",
        "training_rows": int(bundle["training_rows"]),
        "model_version": predictor.model_version,
    }
