from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class FormTemplate(Base):
    __tablename__ = "form_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_key: Mapped[str] = mapped_column(String(100), index=True, default="default")
    nombre: Mapped[str] = mapped_column(String(150), index=True)
    modulo: Mapped[str] = mapped_column(String(50), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    estado: Mapped[str] = mapped_column(String(20), default="Activo", index=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FormTemplateField(Base):
    __tablename__ = "form_template_fields"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("form_templates.id"), index=True)
    clave: Mapped[str] = mapped_column(String(100))
    etiqueta: Mapped[str] = mapped_column(String(150))
    tipo_campo: Mapped[str] = mapped_column(String(50))
    requerido: Mapped[bool] = mapped_column(Boolean, default=False)
    opciones_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    orden: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_key: Mapped[str] = mapped_column(String(100), index=True, default="default")
    template_id: Mapped[int | None] = mapped_column(ForeignKey("form_templates.id"), nullable=True)
    aeropuerto_id: Mapped[int | None] = mapped_column(ForeignKey("aeropuertos.id"), nullable=True)
    titulo: Mapped[str] = mapped_column(String(200))
    alcance: Mapped[str | None] = mapped_column(String(200), nullable=True)
    estado: Mapped[str] = mapped_column(String(30), default="Pendiente", index=True)
    criticidad: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fecha_programada: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fecha_ejecucion: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    responsable_id: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    hallazgos_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CorrectiveAction(Base):
    __tablename__ = "corrective_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inspection_id: Mapped[int | None] = mapped_column(ForeignKey("inspections.id"), nullable=True, index=True)
    incidente_id: Mapped[int | None] = mapped_column(ForeignKey("incidentes.id"), nullable=True, index=True)
    organization_key: Mapped[str] = mapped_column(String(100), index=True, default="default")
    titulo: Mapped[str] = mapped_column(String(200))
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    prioridad: Mapped[str] = mapped_column(String(20), default="Media", index=True)
    estado: Mapped[str] = mapped_column(String(30), default="Abierta", index=True)
    fecha_vencimiento: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    responsable_id: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    evidencia_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TrainingCourse(Base):
    __tablename__ = "training_courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_key: Mapped[str] = mapped_column(String(100), index=True, default="default")
    nombre: Mapped[str] = mapped_column(String(200), index=True)
    categoria: Mapped[str | None] = mapped_column(String(100), nullable=True)
    modalidad: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vigencia_meses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    obligatorio_para_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    estado: Mapped[str] = mapped_column(String(20), default="Activo", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TrainingRecord(Base):
    __tablename__ = "training_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("training_courses.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    organization_key: Mapped[str] = mapped_column(String(100), index=True, default="default")
    estado: Mapped[str] = mapped_column(String(30), default="Pendiente", index=True)
    fecha_asignacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    fecha_completado: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fecha_vencimiento: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    puntaje: Mapped[float | None] = mapped_column(Float, nullable=True)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
