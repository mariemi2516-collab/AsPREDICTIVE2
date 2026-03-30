from __future__ import annotations

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def normalize_database_url(url: str) -> str:
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


engine = create_engine(normalize_database_url(settings.database_url), future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def ensure_runtime_columns() -> None:
    inspector = inspect(engine)
    if not inspector.has_table("usuarios") or not inspector.has_table("incidentes") or not inspector.has_table("alertas") or not inspector.has_table("audit_logs"):
        return

    user_columns = {column["name"] for column in inspector.get_columns("usuarios")}
    incident_columns = {column["name"] for column in inspector.get_columns("incidentes")}
    alert_columns = {column["name"] for column in inspector.get_columns("alertas")}
    audit_columns = {column["name"] for column in inspector.get_columns("audit_logs")}

    statements: list[str] = []
    if "organization_key" not in user_columns:
        statements.append("ALTER TABLE usuarios ADD COLUMN organization_key VARCHAR(100) DEFAULT 'default'")
    if "organization_key" not in incident_columns:
        statements.append("ALTER TABLE incidentes ADD COLUMN organization_key VARCHAR(100) DEFAULT 'default'")
    if "organization_key" not in alert_columns:
        statements.append("ALTER TABLE alertas ADD COLUMN organization_key VARCHAR(100) DEFAULT 'default'")
    if "organization_key" not in audit_columns:
        statements.append("ALTER TABLE audit_logs ADD COLUMN organization_key VARCHAR(100) DEFAULT 'default'")

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))

        if "organization_key" in user_columns or statements:
            connection.execute(text("UPDATE usuarios SET organization_key = 'default' WHERE organization_key IS NULL"))
        if "organization_key" in incident_columns or statements:
            connection.execute(text("UPDATE incidentes SET organization_key = 'default' WHERE organization_key IS NULL"))
        if "organization_key" in alert_columns or statements:
            connection.execute(text("UPDATE alertas SET organization_key = 'default' WHERE organization_key IS NULL"))
        if "organization_key" in audit_columns or statements:
            connection.execute(text("UPDATE audit_logs SET organization_key = 'default' WHERE organization_key IS NULL"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
