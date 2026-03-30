from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any
import warnings

import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report, f1_score
from sklearn.exceptions import ConvergenceWarning

from .schemas import IncidentePayload, NivelRiesgo


ROOT_DIR = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT_DIR / "models"
MODEL_PATH = MODEL_DIR / "risk_model.joblib"
TRACE_DIR = MODEL_DIR / "traces"
PROJECT_ROOT = ROOT_DIR.parent
NTSB_TRAINING_PATH = PROJECT_ROOT / "data" / "processed" / "ntsb_training_base.csv"
JST_TRAINING_PATH = PROJECT_ROOT / "data" / "processed" / "jst_training_base.csv"
JST_NORMALIZED_PATH = PROJECT_ROOT / "data" / "processed" / "jst_incidentes_template.csv"
JST_EVENT_CODE_MAPPING_PATH = PROJECT_ROOT / "data" / "processed" / "jst_event_code_mapping.csv"
JST_EVENT_CODE_AUDIT_PATH = PROJECT_ROOT / "data" / "processed" / "jst_event_code_audit.csv"
RISK_ORDER: list[NivelRiesgo] = ["Bajo", "Medio", "Alto", "Crítico"]
RISK_WEIGHTS = np.array([25.0, 50.0, 75.0, 100.0])
MAX_SYNCHRONOUS_TRAINING_ROWS = 4000
RISK_LABEL_ALIASES = {
    "bajo": "Bajo",
    "medio": "Medio",
    "alto": "Alto",
    "critico": "Crítico",
    "crítico": "Crítico",
    "crã­tico": "Crítico",
    "crĂ­tico": "Crítico",
}


def _normalize_text(value: str | None) -> str:
    return (value or "").strip().lower()


def normalize_risk_label(value: Any) -> str | None:
    if value is None:
        return None
    normalized_value = str(value).strip()
    if not normalized_value:
        return None
    return RISK_LABEL_ALIASES.get(normalized_value.lower(), normalized_value)


def _safe_isoformat(timestamp: float | None) -> str | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()


def _file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_csv_row_count(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        return int(len(pd.read_csv(path, low_memory=False)))
    except Exception:
        return None


def _file_metadata(path: Path, label: str, source_kind: str) -> dict[str, Any]:
    exists = path.exists()
    stat = path.stat() if exists else None
    return {
        "label": label,
        "path": str(path),
        "source_kind": source_kind,
        "exists": exists,
        "size_bytes": stat.st_size if stat else None,
        "modified_at": _safe_isoformat(stat.st_mtime if stat else None),
        "sha256": _file_sha256(path) if exists else None,
        "rows": _read_csv_row_count(path) if exists and path.suffix.lower() == ".csv" else None,
    }


def _label_distribution(rows: list[dict[str, Any]]) -> dict[str, int]:
    labels = [normalize_risk_label(row.get("nivel_riesgo")) for row in rows if normalize_risk_label(row.get("nivel_riesgo"))]
    if not labels:
        return {}
    series = pd.Series(labels)
    return {str(index): int(value) for index, value in series.value_counts().sort_index().items()}


def _field_coverage(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, float]:
    if not rows:
        return {field: 0.0 for field in fields}
    frame = pd.DataFrame(rows)
    coverage: dict[str, float] = {}
    for field in fields:
        if field not in frame.columns:
            coverage[field] = 0.0
            continue
        values = frame[field]
        present = values.notna() & values.astype(str).str.strip().ne("")
        coverage[field] = round(float(present.mean()), 4)
    return coverage


def _unknown_label_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    unknown_labels: dict[str, int] = {}
    for row in rows:
        normalized_label = normalize_risk_label(row.get("nivel_riesgo"))
        if not normalized_label or normalized_label in RISK_ORDER:
            continue
        unknown_labels[normalized_label] = unknown_labels.get(normalized_label, 0) + 1
    return dict(sorted(unknown_labels.items(), key=lambda item: (-item[1], item[0])))


def _jst_traceability_summary() -> dict[str, Any]:
    if not JST_NORMALIZED_PATH.exists():
        return {"available": False}

    frame = pd.read_csv(JST_NORMALIZED_PATH, low_memory=False)
    total = int(len(frame))
    if total == 0:
        return {"available": True, "rows": 0}

    mapped_present = frame.get("mapped_event_codes", pd.Series("", index=frame.index)).fillna("").astype(str).str.strip().ne("")
    unknown_present = frame.get("unknown_event_codes", pd.Series("", index=frame.index)).fillna("").astype(str).str.strip().ne("")
    rule_source = frame.get("mapping_rule_source", pd.Series("", index=frame.index)).fillna("").astype(str)

    unknown_codes: dict[str, int] = {}
    for raw_value in frame.get("unknown_event_codes", pd.Series("", index=frame.index)).fillna("").astype(str):
        for code in [item for item in raw_value.split("|") if item]:
            unknown_codes[code] = unknown_codes.get(code, 0) + 1

    return {
        "available": True,
        "rows": total,
        "rows_with_catalog_mapping": int(mapped_present.sum()),
        "rows_with_unknown_codes": int(unknown_present.sum()),
        "catalog_mapping_coverage": round(float(mapped_present.mean()), 4),
        "unknown_code_coverage": round(float(unknown_present.mean()), 4),
        "mapping_rule_distribution": {str(index): int(value) for index, value in rule_source.value_counts().items()},
        "unknown_codes_top": dict(sorted(unknown_codes.items(), key=lambda item: (-item[1], item[0]))[:10]),
        "mapping_catalog_file": str(JST_EVENT_CODE_MAPPING_PATH),
        "mapping_catalog_sha256": _file_sha256(JST_EVENT_CODE_MAPPING_PATH) if JST_EVENT_CODE_MAPPING_PATH.exists() else None,
    }


def build_training_trace(
    training_rows: list[dict[str, Any]],
    source_name: str,
    postgres_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    postgres_rows = postgres_rows or []
    feature_fields = [
        "descripcion",
        "fase_vuelo",
        "condicion_meteorologica",
        "condicion_luz",
        "latitud",
        "longitud",
        "visibilidad_millas",
        "viento_kt",
        "fecha_hora",
    ]
    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "source_name": source_name,
        "training_rows_total": len(training_rows),
        "postgres_rows_used": len(postgres_rows),
        "risk_label_distribution": _label_distribution(training_rows),
        "unknown_risk_labels": _unknown_label_summary(training_rows),
        "feature_coverage": _field_coverage(training_rows, feature_fields),
        "sources": [
            _file_metadata(NTSB_TRAINING_PATH, "ntsb_training_base", "csv"),
            _file_metadata(JST_TRAINING_PATH, "jst_training_base", "csv"),
            _file_metadata(JST_NORMALIZED_PATH, "jst_normalized", "csv"),
            _file_metadata(JST_EVENT_CODE_MAPPING_PATH, "jst_event_code_mapping", "csv"),
            _file_metadata(JST_EVENT_CODE_AUDIT_PATH, "jst_event_code_audit", "csv"),
        ],
        "jst_traceability": _jst_traceability_summary(),
    }


def save_training_trace(bundle: dict[str, Any], trace_dir: Path = TRACE_DIR) -> Path | None:
    traceability = bundle.get("traceability")
    if not traceability:
        return None

    trace_dir.mkdir(parents=True, exist_ok=True)
    version_slug = str(bundle.get("model_version", "model")).replace("/", "-").replace("\\", "-")
    timestamp_slug = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    trace_path = trace_dir / f"{timestamp_slug}_{version_slug}.json"
    with trace_path.open("w", encoding="utf-8") as handle:
        json.dump(traceability, handle, ensure_ascii=True, indent=2)

    latest_path = trace_dir / "latest_training_trace.json"
    with latest_path.open("w", encoding="utf-8") as handle:
        json.dump(traceability, handle, ensure_ascii=True, indent=2)

    return trace_path


def build_feature_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        frame = pd.DataFrame([{}])

    def column(name: str, default: Any) -> pd.Series:
        if name in frame.columns:
            return frame[name]
        return pd.Series([default] * len(frame), index=frame.index)

    frame["descripcion"] = column("descripcion", "").fillna("").astype(str)
    frame["fase_vuelo"] = column("fase_vuelo", "").fillna("").astype(str)
    frame["condicion_meteorologica"] = column("condicion_meteorologica", "").fillna("").astype(str)
    frame["condicion_luz"] = column("condicion_luz", "").fillna("").astype(str)
    frame["cielo_sin_techo"] = column("cielo_sin_techo", "").fillna("").astype(str)
    frame["cielo_con_techo"] = column("cielo_con_techo", "").fillna("").astype(str)
    frame["aeropuerto_id"] = pd.to_numeric(column("aeropuerto_id", -1), errors="coerce").fillna(-1).astype(int).astype(str)
    frame["tipo_incidente_id"] = pd.to_numeric(column("tipo_incidente_id", -1), errors="coerce").fillna(-1).astype(int).astype(str)
    frame["aeronave_id"] = pd.to_numeric(column("aeronave_id", -1), errors="coerce").fillna(-1).astype(int).astype(str)
    raw_latitud = pd.to_numeric(column("latitud", np.nan), errors="coerce")
    raw_longitud = pd.to_numeric(column("longitud", np.nan), errors="coerce")
    frame["has_coordinates"] = (~raw_latitud.isna() & ~raw_longitud.isna()).astype(int)
    frame["latitud"] = raw_latitud.fillna(0.0)
    frame["longitud"] = raw_longitud.fillna(0.0)
    frame["visibilidad_millas"] = pd.to_numeric(column("visibilidad_millas", np.nan), errors="coerce").fillna(0.0)
    frame["viento_kt"] = pd.to_numeric(column("viento_kt", np.nan), errors="coerce").fillna(0.0)
    frame["viento_dir_deg"] = pd.to_numeric(column("viento_dir_deg", np.nan), errors="coerce").fillna(0.0)
    frame["temperatura_c"] = pd.to_numeric(column("temperatura_c", np.nan), errors="coerce").fillna(0.0)
    frame["punto_rocio_c"] = pd.to_numeric(column("punto_rocio_c", np.nan), errors="coerce").fillna(0.0)
    frame["techo_nubes_ft"] = pd.to_numeric(column("techo_nubes_ft", np.nan), errors="coerce").fillna(0.0)
    frame["precipitacion"] = column("intensidad_precipitacion", "").fillna("").astype(str).map(lambda value: 0 if value.strip() == "" else 1)

    fecha = pd.to_datetime(column("fecha_hora", None), errors="coerce", utc=True)
    frame["hour"] = fecha.dt.hour.fillna(12).astype(int)
    frame["day_of_week"] = fecha.dt.dayofweek.fillna(0).astype(int)
    frame["month"] = fecha.dt.month.fillna(1).astype(int)
    frame["is_night"] = frame["hour"].apply(lambda value: 1 if value >= 20 or value <= 5 else 0)

    frame["descripcion"] = frame["descripcion"].map(_normalize_text)
    frame["fase_vuelo"] = frame["fase_vuelo"].map(_normalize_text)
    frame["condicion_meteorologica"] = frame["condicion_meteorologica"].map(_normalize_text)
    frame["condicion_luz"] = frame["condicion_luz"].map(_normalize_text)
    frame["cielo_sin_techo"] = frame["cielo_sin_techo"].map(_normalize_text)
    frame["cielo_con_techo"] = frame["cielo_con_techo"].map(_normalize_text)

    return frame[
        [
            "descripcion",
            "fase_vuelo",
            "condicion_meteorologica",
            "condicion_luz",
            "cielo_sin_techo",
            "cielo_con_techo",
            "aeropuerto_id",
            "tipo_incidente_id",
            "aeronave_id",
            "latitud",
            "longitud",
            "visibilidad_millas",
            "viento_kt",
            "viento_dir_deg",
            "temperatura_c",
            "punto_rocio_c",
            "techo_nubes_ft",
            "precipitacion",
            "hour",
            "day_of_week",
            "month",
            "is_night",
            "has_coordinates",
        ]
    ]


def create_training_rows() -> list[dict[str, Any]]:
    base_rows = [
        {
            "descripcion": "colision con fauna durante aterrizaje con visibilidad reducida",
            "fase_vuelo": "Aterrizaje",
            "aeropuerto_id": 1,
            "tipo_incidente_id": 2,
            "aeronave_id": 11,
            "latitud": -34.81,
            "longitud": -58.53,
            "fecha_hora": "2026-03-18T22:10:00Z",
            "nivel_riesgo": "Crítico",
        },
        {
            "descripcion": "falla de motor en ascenso inicial con vibraciones",
            "fase_vuelo": "Despegue",
            "aeropuerto_id": 2,
            "tipo_incidente_id": 7,
            "aeronave_id": 8,
            "latitud": -31.29,
            "longitud": -64.21,
            "fecha_hora": "2026-03-02T04:25:00Z",
            "nivel_riesgo": "Crítico",
        },
        {
            "descripcion": "incursion de pista con aproximacion frustrada",
            "fase_vuelo": "Aterrizaje",
            "aeropuerto_id": 3,
            "tipo_incidente_id": 4,
            "aeronave_id": 19,
            "latitud": -32.91,
            "longitud": -60.79,
            "fecha_hora": "2026-02-21T23:55:00Z",
            "nivel_riesgo": "Alto",
        },
        {
            "descripcion": "condicion meteorologica adversa con viento cruzado fuerte",
            "fase_vuelo": "Aterrizaje",
            "aeropuerto_id": 5,
            "tipo_incidente_id": 6,
            "aeronave_id": 5,
            "latitud": -34.56,
            "longitud": -58.42,
            "fecha_hora": "2026-01-17T21:00:00Z",
            "nivel_riesgo": "Alto",
        },
        {
            "descripcion": "exceso de velocidad en rodaje sin daños reportados",
            "fase_vuelo": "Rodaje",
            "aeropuerto_id": 1,
            "tipo_incidente_id": 3,
            "aeronave_id": 9,
            "latitud": -34.82,
            "longitud": -58.54,
            "fecha_hora": "2026-03-11T14:00:00Z",
            "nivel_riesgo": "Medio",
        },
        {
            "descripcion": "reporte preventivo por objeto extraño cercano a pista",
            "fase_vuelo": "Rodaje",
            "aeropuerto_id": 4,
            "tipo_incidente_id": 1,
            "aeronave_id": 14,
            "latitud": -24.85,
            "longitud": -65.49,
            "fecha_hora": "2026-03-01T11:40:00Z",
            "nivel_riesgo": "Medio",
        },
        {
            "descripcion": "demora operacional menor durante crucero sin impacto",
            "fase_vuelo": "Crucero",
            "aeropuerto_id": 6,
            "tipo_incidente_id": 3,
            "aeronave_id": 12,
            "latitud": -38.0,
            "longitud": -57.56,
            "fecha_hora": "2026-02-12T16:30:00Z",
            "nivel_riesgo": "Bajo",
        },
        {
            "descripcion": "chequeo de mantenimiento por indicacion preventiva",
            "fase_vuelo": "En tierra",
            "aeropuerto_id": 7,
            "tipo_incidente_id": 8,
            "aeronave_id": 2,
            "latitud": None,
            "longitud": None,
            "fecha_hora": "2026-01-08T09:20:00Z",
            "nivel_riesgo": "Bajo",
        },
    ]

    rows: list[dict[str, Any]] = []
    variants = [
        ("Crítico", 22, "emergencia", "Despegue"),
        ("Alto", 14, "desviacion", "Aterrizaje"),
        ("Medio", 10, "precaucion", "Rodaje"),
        ("Bajo", 8, "preventivo", "Crucero"),
    ]

    for template in base_rows:
        rows.append(template)

    for risk, count, suffix, phase in variants:
        for index in range(count):
            base = base_rows[index % len(base_rows)].copy()
            base["nivel_riesgo"] = risk
            base["fase_vuelo"] = phase
            base["descripcion"] = f"{base['descripcion']} {suffix} caso {index + 1}"
            base["aeropuerto_id"] = (index % 7) + 1
            base["tipo_incidente_id"] = (index % 8) + 1
            base["aeronave_id"] = (index % 20) + 1
            base["fecha_hora"] = f"2026-02-{(index % 27) + 1:02d}T{(index % 24):02d}:00:00Z"
            rows.append(base)

    return rows


def create_model_pipeline() -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            ("descripcion", TfidfVectorizer(max_features=100, ngram_range=(1, 2)), "descripcion"),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore"),
                [
                    "fase_vuelo",
                    "condicion_meteorologica",
                    "condicion_luz",
                    "cielo_sin_techo",
                    "cielo_con_techo",
                    "aeropuerto_id",
                    "tipo_incidente_id",
                    "aeronave_id",
                ],
            ),
            (
                "numeric",
                StandardScaler(with_mean=False),
                [
                    "latitud",
                    "longitud",
                    "visibilidad_millas",
                    "viento_kt",
                    "viento_dir_deg",
                    "temperatura_c",
                    "punto_rocio_c",
                    "techo_nubes_ft",
                    "precipitacion",
                    "hour",
                    "day_of_week",
                    "month",
                    "is_night",
                    "has_coordinates",
                ],
            ),
        ]
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            (
                "classifier",
                SGDClassifier(
                    loss="log_loss",
                    max_iter=1000,
                    tol=1e-3,
                    early_stopping=True,
                    validation_fraction=0.1,
                    n_iter_no_change=5,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )


def sample_training_rows(rows: list[dict[str, Any]], limit: int = MAX_SYNCHRONOUS_TRAINING_ROWS) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if len(rows) <= limit:
        return rows, {"applied": False, "original_rows": len(rows), "sampled_rows": len(rows)}

    frame = pd.DataFrame(rows)
    sample_frame, _ = train_test_split(
        frame,
        train_size=limit,
        random_state=42,
        stratify=frame["nivel_riesgo"],
    )
    sampled_rows = sample_frame.to_dict(orient="records")
    return sampled_rows, {
        "applied": True,
        "original_rows": len(rows),
        "sampled_rows": len(sampled_rows),
        "strategy": "stratified_random_sample",
        "limit": limit,
    }


def load_ntsb_training_rows(path: Path = NTSB_TRAINING_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    frame = pd.read_csv(path, low_memory=False)
    if frame.empty:
        return []

    rows: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        rows.append(
            {
                "aeropuerto_id": None,
                "tipo_incidente_id": None,
                "aeronave_id": None,
                "fase_vuelo": row.get("fase_vuelo"),
                "condicion_meteorologica": row.get("condicion_meteorologica"),
                "condicion_luz": row.get("condicion_luz"),
                "cielo_sin_techo": row.get("cielo_sin_techo"),
                "cielo_con_techo": row.get("cielo_con_techo"),
                "descripcion": row.get("descripcion"),
                "latitud": row.get("latitud"),
                "longitud": row.get("longitud"),
                "visibilidad_millas": row.get("visibilidad_millas"),
                "viento_kt": row.get("viento_kt"),
                "viento_dir_deg": row.get("viento_dir_deg"),
                "temperatura_c": row.get("temperatura_c"),
                "punto_rocio_c": row.get("punto_rocio_c"),
                "techo_nubes_ft": row.get("techo_nubes_ft"),
                "intensidad_precipitacion": row.get("intensidad_precipitacion"),
                "fecha_hora": _combine_fecha_hora(row.get("fecha"), row.get("hora")),
                "nivel_riesgo": normalize_risk_label(row.get("nivel_riesgo")),
            }
        )

    return rows


def load_jst_training_rows(path: Path = JST_TRAINING_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    frame = pd.read_csv(path, low_memory=False)
    if frame.empty:
        return []

    rows: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        rows.append(
            {
                "aeropuerto_id": None,
                "tipo_incidente_id": None,
                "aeronave_id": None,
                "fase_vuelo": row.get("fase_vuelo"),
                "condicion_meteorologica": row.get("condicion_meteorologica"),
                "condicion_luz": row.get("condicion_luz"),
                "descripcion": row.get("descripcion"),
                "latitud": row.get("latitud"),
                "longitud": row.get("longitud"),
                "visibilidad_millas": row.get("visibilidad_millas"),
                "viento_kt": row.get("viento_kt"),
                "fecha_hora": row.get("fecha_hora"),
                "nivel_riesgo": normalize_risk_label(row.get("nivel_riesgo")),
            }
        )

    return rows


def combine_training_rows(
    ntsb_rows: list[dict[str, Any]] | None = None,
    postgres_rows: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], str]:
    ntsb_rows = ntsb_rows or []
    postgres_rows = postgres_rows or []

    if ntsb_rows and postgres_rows:
        return [*ntsb_rows, *postgres_rows], "ntsb-real-postgresql"
    if ntsb_rows:
        return ntsb_rows, "ntsb-real"
    if postgres_rows:
        return postgres_rows, "postgresql"

    return [], "bootstrap"


def _combine_fecha_hora(fecha: Any, hora: Any) -> str | None:
    if pd.isna(fecha):
        return None
    fecha_ts = pd.to_datetime(fecha, errors="coerce")
    if pd.isna(fecha_ts):
        return None

    if pd.isna(hora):
        return fecha_ts.isoformat()

    try:
        hour_value = int(float(hora))
        hours = hour_value // 100
        minutes = hour_value % 100
        fecha_ts = fecha_ts.replace(hour=hours, minute=minutes)
    except Exception:
        pass

    return fecha_ts.isoformat()


def build_train_test_split(
    frame: pd.DataFrame,
    target: list[str],
    raw_rows: list[dict[str, Any]],
) -> tuple[pd.DataFrame, pd.DataFrame, list[str], list[str], dict[str, Any]]:
    timestamps = pd.to_datetime([row.get("fecha_hora") for row in raw_rows], errors="coerce", utc=True)
    temporal_frame = frame.copy()
    temporal_frame["__target__"] = target
    temporal_frame["__timestamp__"] = timestamps
    valid_temporal_rows = temporal_frame["__timestamp__"].notna().sum()

    if valid_temporal_rows >= max(12, int(len(temporal_frame) * 0.6)):
        temporal_frame = temporal_frame.sort_values("__timestamp__").reset_index(drop=True)
        split_index = max(1, int(len(temporal_frame) * 0.8))
        if split_index >= len(temporal_frame):
            split_index = len(temporal_frame) - 1

        train_frame = temporal_frame.iloc[:split_index]
        test_frame = temporal_frame.iloc[split_index:]
        if not test_frame.empty and len(set(train_frame["__target__"])) >= 2 and len(set(test_frame["__target__"])) >= 2:
            return (
                train_frame.drop(columns=["__target__", "__timestamp__"]),
                test_frame.drop(columns=["__target__", "__timestamp__"]),
                train_frame["__target__"].tolist(),
                test_frame["__target__"].tolist(),
                {
                    "strategy": "temporal_holdout",
                    "samples_with_timestamp": int(valid_temporal_rows),
                    "samples_without_timestamp": int(len(temporal_frame) - valid_temporal_rows),
                },
            )

    x_train, x_test, y_train, y_test = train_test_split(
        frame,
        target,
        test_size=0.2,
        random_state=42,
        stratify=target,
    )
    return x_train, x_test, y_train, y_test, {"strategy": "stratified_random_holdout"}


def train_bundle(
    rows: list[dict[str, Any]],
    source_name: str,
    traceability: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_rows = [{**row, "nivel_riesgo": normalize_risk_label(row.get("nivel_riesgo"))} for row in rows]
    labeled_rows = [row for row in normalized_rows if row.get("nivel_riesgo") in RISK_ORDER]
    if len(labeled_rows) < 12:
        raise ValueError("Se requieren al menos 12 registros etiquetados para entrenar el modelo.")

    training_rows, sampling_info = sample_training_rows(labeled_rows)

    frame = build_feature_frame(training_rows)
    target = [row["nivel_riesgo"] for row in training_rows]

    pipeline = create_model_pipeline()
    x_train, x_test, y_train, y_test, split_info = build_train_test_split(frame, target, training_rows)
    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always", ConvergenceWarning)
        pipeline.fit(x_train, y_train)
    predictions = pipeline.predict(x_test)
    accuracy = float(accuracy_score(y_test, predictions))
    balanced_accuracy = float(balanced_accuracy_score(y_test, predictions))
    macro_f1 = float(f1_score(y_test, predictions, average="macro", zero_division=0))
    report = classification_report(y_test, predictions, output_dict=True, zero_division=0)
    convergence_warnings = [str(item.message) for item in caught_warnings if issubclass(item.category, ConvergenceWarning)]
    traceability_payload = traceability or build_training_trace(normalized_rows, source_name=source_name)
    traceability_payload["sampling"] = sampling_info
    traceability_payload["validation"] = split_info

    return {
        "pipeline": pipeline,
        "risk_order": RISK_ORDER,
        "risk_weights": RISK_WEIGHTS.tolist(),
        "model_version": f"sgd-logloss-{source_name}",
        "training_rows": len(training_rows),
        "traceability": traceability_payload,
        "metrics": {
            "accuracy": accuracy,
            "balanced_accuracy": balanced_accuracy,
            "macro_f1": macro_f1,
            "samples_train": len(x_train),
            "samples_test": len(x_test),
            "classification_report": report,
            "validation_strategy": split_info.get("strategy"),
            "converged": not convergence_warnings,
            "warnings": convergence_warnings,
        },
    }


def save_bundle(bundle: dict[str, Any], path: Path = MODEL_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path)
    trace_path = save_training_trace(bundle)
    if trace_path is not None:
        bundle.setdefault("traceability", {})["trace_file"] = str(trace_path)
        latest_path = TRACE_DIR / "latest_training_trace.json"
        bundle["traceability"]["latest_trace_file"] = str(latest_path)
        joblib.dump(bundle, path)
    return path


def bootstrap_bundle() -> dict[str, Any]:
    rows = create_training_rows()
    traceability = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "source_name": "bootstrap",
        "training_rows_total": len(rows),
        "postgres_rows_used": 0,
        "risk_label_distribution": _label_distribution(rows),
        "feature_coverage": _field_coverage(rows, ["descripcion", "fase_vuelo", "latitud", "longitud", "fecha_hora"]),
        "sources": [],
        "jst_traceability": {"available": False},
        "mode": "bootstrap_sintetico",
    }
    return train_bundle(rows, source_name="bootstrap", traceability=traceability)


def best_available_training_bundle() -> dict[str, Any]:
    ntsb_rows = load_ntsb_training_rows()
    jst_rows = load_jst_training_rows()
    training_rows, source_name = combine_training_rows(ntsb_rows, jst_rows)
    if len(training_rows) >= 12:
        traceability = build_training_trace(training_rows, source_name=source_name)
        return train_bundle(training_rows, source_name=source_name, traceability=traceability)
    return bootstrap_bundle()


@dataclass
class PredictionResult:
    score: int
    nivel: NivelRiesgo
    factores: list[str]
    modelo: str


class RiskPredictor:
    def __init__(self, model_path: Path = MODEL_PATH):
        self.model_path = model_path
        self.bundle = self._load_or_bootstrap()

    def _load_or_bootstrap(self) -> dict[str, Any]:
        if self.model_path.exists():
            return joblib.load(self.model_path)

        bundle = best_available_training_bundle()
        save_bundle(bundle, self.model_path)
        return bundle

    @property
    def model_version(self) -> str:
        return str(self.bundle["model_version"])

    def reload(self) -> None:
        self.bundle = self._load_or_bootstrap()

    def predict(self, payload: IncidentePayload) -> PredictionResult:
        row = build_feature_frame([payload.model_dump()])
        pipeline: Pipeline = self.bundle["pipeline"]
        classifier: SGDClassifier = pipeline.named_steps["classifier"]
        probabilities = pipeline.predict_proba(row)[0]
        class_weights = np.array(
            [self._risk_weight_for_label(str(label)) for label in classifier.classes_],
            dtype=float,
        )
        weighted_score = float(np.dot(probabilities, class_weights))
        predicted_label = self._score_to_level(weighted_score)
        factors = self._explain_prediction(row, probabilities)

        return PredictionResult(
            score=int(round(weighted_score)),
            nivel=predicted_label,
            factores=factors,
            modelo=self.model_version,
        )

    def _risk_weight_for_label(self, label: str) -> float:
        mapping = {
            "Bajo": 25.0,
            "Medio": 50.0,
            "Alto": 75.0,
            "Crítico": 100.0,
        }
        return mapping.get(label, 50.0)

    def _score_to_level(self, score: float) -> NivelRiesgo:
        if score >= 85:
            return "Crítico"
        if score >= 70:
            return "Alto"
        if score >= 50:
            return "Medio"
        return "Bajo"

    def _explain_prediction(self, row: pd.DataFrame, probabilities: np.ndarray) -> list[str]:
        pipeline: Pipeline = self.bundle["pipeline"]
        preprocessor: ColumnTransformer = pipeline.named_steps["preprocessor"]
        classifier: SGDClassifier = pipeline.named_steps["classifier"]
        transformed = preprocessor.transform(row)
        if not sparse.issparse(transformed):
            transformed = sparse.csr_matrix(transformed)

        class_index = int(np.argmax(probabilities))
        feature_names = preprocessor.get_feature_names_out()
        class_coef = classifier.coef_[class_index]
        row_values = transformed.toarray()[0]
        contributions = row_values * class_coef
        top_indexes = np.argsort(contributions)[-4:][::-1]

        explanations: list[str] = []
        for idx in top_indexes:
            contribution = contributions[idx]
            if contribution <= 0:
                continue
            name = feature_names[idx].replace("__", ": ").replace("_", " ")
            explanations.append(f"{name} (+{contribution:.2f})")

        if not explanations:
            explanations.append("sin factores dominantes identificados")

        return explanations
