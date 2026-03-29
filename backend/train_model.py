from __future__ import annotations

from dotenv import load_dotenv

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.db import SessionLocal
from app.model_service import (
    MODEL_PATH,
    bootstrap_bundle,
    build_training_trace,
    combine_training_rows,
    load_jst_training_rows,
    load_ntsb_training_rows,
    save_bundle,
    train_bundle,
)
from app.models import Incidente


def main() -> None:
    load_dotenv()
    ntsb_rows = load_ntsb_training_rows()
    jst_rows = load_jst_training_rows()
    postgres_rows = []
    try:
        with SessionLocal() as db:
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
    except SQLAlchemyError as error:
        print(f"Advertencia: no se pudo leer PostgreSQL local, se continua con CSVs disponibles. Detalle: {error}")

    training_rows, source_name = combine_training_rows([*ntsb_rows, *jst_rows], postgres_rows)

    if len(training_rows) >= 12:
        traceability = build_training_trace(training_rows, source_name=source_name, postgres_rows=postgres_rows)
        bundle = train_bundle(training_rows, source_name=source_name, traceability=traceability)
    else:
        bundle = bootstrap_bundle()

    path = save_bundle(bundle, MODEL_PATH)
    trace_path = bundle.get("traceability", {}).get("trace_file")
    print(f"Modelo guardado en: {path}")
    if trace_path:
        print(f"Trazabilidad de entrenamiento guardada en: {trace_path}")
    print(f"Version: {bundle['model_version']}")
    print(f"Registros de entrenamiento: {bundle['training_rows']}")
    if bundle.get("traceability"):
        traceability = bundle["traceability"]
        print(f"Fuente compuesta: {traceability.get('source_name')}")
        print(f"Distribucion de etiquetas: {traceability.get('risk_label_distribution')}")
    if bundle.get("metrics"):
        print(f"Accuracy holdout: {bundle['metrics']['accuracy']:.4f}")
        print(f"Train/Test: {bundle['metrics']['samples_train']}/{bundle['metrics']['samples_test']}")


if __name__ == "__main__":
    main()
