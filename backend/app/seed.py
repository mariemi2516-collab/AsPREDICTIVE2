from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Aeronave, Aeropuerto, TipoIncidente, Usuario
from .security import get_password_hash


def seed_initial_data(db: Session) -> None:
    if not db.scalar(select(Usuario.id).limit(1)):
        db.add(
            Usuario(
                nombre="Administrador Demo",
                email="admin@aspredictive.local",
                password_hash=get_password_hash("Admin12345"),
                rol="administrador",
                estado=True,
            )
        )

    if not db.scalar(select(Aeropuerto.id).limit(1)):
        db.add_all(
            [
                Aeropuerto(codigo_iata="AEP", codigo_icao="SABE", nombre="Aeroparque Jorge Newbery", ciudad="Buenos Aires", provincia="Buenos Aires", categoria="Internacional"),
                Aeropuerto(codigo_iata="EZE", codigo_icao="SAEZ", nombre="Ministro Pistarini", ciudad="Ezeiza", provincia="Buenos Aires", categoria="Internacional"),
                Aeropuerto(codigo_iata="COR", codigo_icao="SACO", nombre="Ingeniero Taravella", ciudad="Cordoba", provincia="Cordoba", categoria="Internacional"),
            ]
        )

    if not db.scalar(select(Aeronave.id).limit(1)):
        db.add_all(
            [
                Aeronave(matricula="LV-FPS", modelo="B737-800", fabricante="Boeing", operador="Aerolíneas Argentinas"),
                Aeronave(matricula="LV-KHQ", modelo="A320", fabricante="Airbus", operador="Jetsmart"),
                Aeronave(matricula="LV-GKO", modelo="EMB-190", fabricante="Embraer", operador="Austral"),
            ]
        )

    if not db.scalar(select(TipoIncidente.id).limit(1)):
        db.add_all(
            [
                TipoIncidente(codigo_oaci="REIN", nombre="Reingreso Pista", categoria="Pista"),
                TipoIncidente(codigo_oaci="BIRD", nombre="Colisión con Fauna", categoria="Fauna"),
                TipoIncidente(codigo_oaci="ENGINE", nombre="Falla de Motor", categoria="Técnico"),
                TipoIncidente(codigo_oaci="RUNWAY", nombre="Incursión de Pista", categoria="Pista"),
            ]
        )

    db.commit()
