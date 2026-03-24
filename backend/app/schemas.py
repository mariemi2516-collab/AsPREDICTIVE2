from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


NivelRiesgo = Literal["Bajo", "Medio", "Alto", "Crítico"]


class IncidentePayload(BaseModel):
    aeropuerto_id: int | None = None
    tipo_incidente_id: int | None = None
    aeronave_id: int | None = None
    fase_vuelo: str | None = ""
    descripcion: str | None = ""
    latitud: float | None = None
    longitud: float | None = None
    fecha_hora: str | None = None


class PredictionResponse(BaseModel):
    score: int = Field(ge=0, le=100)
    nivel: NivelRiesgo
    factores: list[str] = Field(default_factory=list)
    modelo: str


class HealthResponse(BaseModel):
    status: Literal["ok"]
    model_loaded: bool
    model_version: str
