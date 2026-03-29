from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import unicodedata

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.db import SessionLocal  # noqa: E402
from app.models import Aeronave, Aeropuerto, Incidente, TipoIncidente  # noqa: E402
from sqlalchemy import select  # noqa: E402


INPUT_PATH = ROOT / "data" / "processed" / "jst_incidentes_template.csv"
OUTPUT_PATH = ROOT / "data" / "processed" / "jst_training_base.csv"
NORMALIZED_OUTPUT_PATH = ROOT / "data" / "processed" / "jst_incidentes_template.csv"
EVENT_CODE_MAPPING_PATH = ROOT / "data" / "processed" / "jst_event_code_mapping.csv"
EVENT_CODE_AUDIT_PATH = ROOT / "data" / "processed" / "jst_event_code_audit.csv"


def normalize_text(value: object) -> str:
    return "" if pd.isna(value) else str(value).strip()


def normalize_nullable_text(value: object) -> str | None:
    text = normalize_text(value)
    return text or None


def normalize_float(value: object) -> float | None:
    if pd.isna(value) or value in ("", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_datetime(value: object) -> str | None:
    text = normalize_text(value)
    if not text:
        return None
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.isoformat()


def slugify(value: object) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = "".join(char if char.isalnum() else "-" for char in ascii_text.upper())
    return "-".join(part for part in cleaned.split("-") if part)


def normalize_risk_label(value: object) -> str | None:
    text = normalize_text(value)
    if not text:
        return None
    lowered = slugify(text).lower()
    mapping = {
        "bajo": "Bajo",
        "medio": "Medio",
        "alto": "Alto",
        "critico": "Critico",
        "critico-operacional": "Critico",
    }
    return mapping.get(lowered, text)


def risk_score(value: str | None) -> int:
    mapping = {"Bajo": 1, "Medio": 2, "Alto": 3, "Critico": 4}
    return mapping.get(normalize_risk_label(value) or "", 0)


def extract_event_codes(raw_event: str) -> set[str]:
    text = normalize_text(raw_event).upper()
    if not text:
        return set()
    return {match.group(1) for match in re.finditer(r"(?:^|,\s*)([A-Z]+(?:-[A-Z]+)?)\s*\(", text)}


def operation_profile(raw_operation: str) -> str:
    text = normalize_text(raw_operation).lower()
    if "commercial air transport" in text:
        return "comercial"
    if "flight training" in text or "instructional" in text or "acrobatic" in text:
        return "instruccion"
    if "aerial work" in text or "agricultural" in text or "specialised operations" in text:
        return "trabajo_aereo"
    if "firefighting" in text:
        return "emergencia"
    if "relocation" in text or "ferry" in text or "delivery" in text or "positioning" in text:
        return "reposicionamiento"
    if "pleasure" in text or "bussiness" in text or "business" in text:
        return "aviacion_general"
    return "desconocida"


def load_event_code_mapping(path: Path = EVENT_CODE_MAPPING_PATH) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}

    frame = pd.read_csv(path, low_memory=False)
    mapping: dict[str, dict[str, str]] = {}
    for _, row in frame.iterrows():
        event_code = normalize_text(row.get("event_code")).upper()
        if not event_code:
            continue
        mapping[event_code] = {
            "categoria_incidente": normalize_text(row.get("categoria_incidente")),
            "fase_vuelo": normalize_text(row.get("fase_vuelo")),
            "nivel_riesgo": normalize_risk_label(row.get("nivel_riesgo")) or "",
        }
    return mapping


EVENT_CODE_MAPPING = load_event_code_mapping()


def merge_code_defaults(codes: set[str]) -> dict[str, str]:
    defaults = {"categoria_incidente": "", "fase_vuelo": "", "nivel_riesgo": ""}
    if not codes:
        return defaults

    matched = [EVENT_CODE_MAPPING[code] for code in codes if code in EVENT_CODE_MAPPING]
    if not matched:
        return defaults

    non_operational_categories = [row["categoria_incidente"] for row in matched if row.get("categoria_incidente") and row.get("categoria_incidente") != "Operacion"]
    defaults["categoria_incidente"] = non_operational_categories[0] if non_operational_categories else next(
        (row["categoria_incidente"] for row in matched if row.get("categoria_incidente")),
        "",
    )

    phase_priority = ["Despegue", "Ascenso inicial", "Aproximacion", "Aterrizaje", "Rodaje", "En tierra", "Maniobra a baja altura", "En vuelo"]
    for phase in phase_priority:
        if any(row.get("fase_vuelo") == phase for row in matched):
            defaults["fase_vuelo"] = phase
            break
    if not defaults["fase_vuelo"]:
        defaults["fase_vuelo"] = next((row["fase_vuelo"] for row in matched if row.get("fase_vuelo")), "")

    highest_risk = max((row.get("nivel_riesgo") for row in matched), key=risk_score, default="")
    defaults["nivel_riesgo"] = highest_risk
    return defaults


def resolve_traceability(raw_type: str, raw_event: str, raw_operation: str) -> dict[str, str]:
    codes = extract_event_codes(raw_event)
    mapped_codes = sorted(code for code in codes if code in EVENT_CODE_MAPPING)
    unknown_codes = sorted(code for code in codes if code not in EVENT_CODE_MAPPING)
    categoria = infer_category(raw_type, raw_operation, raw_event)
    fase = infer_phase_from_raw(raw_event, raw_operation)
    riesgo = infer_risk_from_raw(raw_type, raw_event, raw_operation)

    if mapped_codes:
        rule_source = "tabla_jst_event_code_mapping"
    elif codes:
        rule_source = "heuristica_por_codigo_y_operacion"
    else:
        rule_source = "heuristica_textual"

    return {
        "event_codes": "|".join(sorted(codes)),
        "mapped_event_codes": "|".join(mapped_codes),
        "unknown_event_codes": "|".join(unknown_codes),
        "mapping_rule_source": rule_source,
        "mapping_version": EVENT_CODE_MAPPING_PATH.name,
        "categoria_incidente": categoria,
        "fase_vuelo": fase,
        "nivel_riesgo": riesgo,
    }


def infer_phase_from_raw(raw_event: str, raw_operation: str) -> str:
    text = f"{normalize_text(raw_event)} {normalize_text(raw_operation)}".lower()
    codes = extract_event_codes(raw_event)
    profile = operation_profile(raw_operation)
    mapped = merge_code_defaults(codes)

    if mapped["fase_vuelo"]:
        if mapped["fase_vuelo"] == "Aterrizaje" and "BIRD" in codes and profile == "comercial":
            return "Ascenso inicial"
        if mapped["fase_vuelo"] == "En vuelo" and "LALT" in codes and profile == "trabajo_aereo":
            return "Maniobra a baja altura"
        if mapped["fase_vuelo"] == "Ascenso inicial" and "SCF-NP" in codes and profile not in {"comercial", "instruccion"}:
            return "En vuelo"
        return mapped["fase_vuelo"]

    if {"ARC", "RE", "USOS"} & codes:
        return "Aterrizaje"
    if "CTOL" in codes:
        return "Despegue"
    if "RAMP" in codes:
        return "En tierra"
    if "GCOL" in codes:
        return "Rodaje"
    if "BIRD" in codes:
        return "Ascenso inicial" if profile == "comercial" else "Aterrizaje"
    if {"LOC-I", "CFIT", "LALT"} & codes:
        return "Maniobra a baja altura" if profile == "trabajo_aereo" else "En vuelo"
    if "LOC-G" in codes:
        return "Rodaje"
    if {"SCF-PP", "FUEL"} & codes:
        return "Ascenso inicial" if profile in {"comercial", "instruccion"} else "En vuelo"
    if {"SCF-NP", "ADRM"} & codes:
        return "Aproximacion" if profile == "comercial" else "En vuelo"
    if {"F-POST", "F-NI"} & codes:
        return "En vuelo" if "LOC-I" in codes else "En tierra"

    phase_rules = [
        ("Aterrizaje", ["runway", "landing", "undershoot", "overshoot", "abnormal runway contact"]),
        ("Ascenso inicial", ["initial climb", "takeoff", "despeg"]),
        ("Aproximacion", ["approach", "aproxim"]),
        ("Rodaje", ["taxi", "rodaje", "ground collision"]),
        ("Crucero", ["cruise", "crucero", "en route"]),
        ("Maniobra a baja altura", ["aerial work", "agricultural", "acrobatics"]),
        ("En tierra", ["ground", "parked", "maintenance"]),
    ]
    for phase, keywords in phase_rules:
        if any(keyword in text for keyword in keywords):
            return phase
    return "En vuelo"


def infer_category(raw_type: str, raw_operation: str, raw_event: str) -> str:
    text = f"{normalize_text(raw_type)} {normalize_text(raw_operation)} {normalize_text(raw_event)}".lower()
    codes = extract_event_codes(raw_event)
    mapped = merge_code_defaults(codes)
    if mapped["categoria_incidente"]:
        return mapped["categoria_incidente"]
    if {"SCF-PP", "SCF-NP", "FUEL"} & codes:
        return "Tecnico"
    if {"BIRD"} & codes:
        return "Fauna"
    if {"ARC", "RE", "USOS", "ADRM"} & codes:
        return "Pista"
    if {"LOC-I", "LOC-G", "CFIT", "CTOL", "GCOL"} & codes:
        return "Operacion"
    if {"F-POST", "F-NI"} & codes:
        return "Seguridad operacional"
    if "commercial air transport" in text:
        return "Operacion"
    if "flight training" in text or "instructional" in text:
        return "Operacion"
    if "aerial work" in text or "specialised" in text or "specialized" in text:
        return "Operacion"
    return "Operacion"


def infer_risk_from_raw(raw_type: str, raw_event: str, raw_operation: str) -> str:
    tipo = normalize_text(raw_type).lower()
    evento = normalize_text(raw_event).lower()
    codes = extract_event_codes(raw_event)
    profile = operation_profile(raw_operation)
    mapped = merge_code_defaults(codes)
    if mapped["nivel_riesgo"]:
        if mapped["nivel_riesgo"] == "Alto" and "accidente" in tipo and ("CFIT" in codes or "LOC-I" in codes or "F-POST" in codes):
            return "Critico"
        if mapped["nivel_riesgo"] == "Alto" and profile == "trabajo_aereo" and ({"LOC-I", "LALT", "GCOL"} & codes):
            return "Critico"
        return mapped["nivel_riesgo"]

    critical_codes = {"CFIT", "LOC-I", "F-POST", "CTOL"}
    high_codes = {"SCF-PP", "SCF-NP", "RE", "ARC", "USOS", "GCOL", "LOC-G", "F-NI", "FUEL", "BIRD", "LALT"}

    if "accidente" in tipo and critical_codes & codes:
        return "Critico"
    if "accidente" in tipo and profile == "trabajo_aereo" and ({"LOC-I", "LALT", "GCOL"} & codes):
        return "Critico"
    if "accidente" in tipo:
        return "Alto"
    if "incidente grave" in tipo:
        return "Alto"
    if profile == "comercial" and ({"SCF-PP", "SCF-NP", "BIRD", "RE", "ARC", "USOS"} & codes):
        return "Alto"
    if high_codes & codes:
        return "Alto"
    if "incidente" in tipo and ("unknown" in evento or "unk" in evento):
        return "Bajo"
    return "Medio"


def split_location(raw_location: object) -> tuple[str | None, str | None]:
    text = normalize_text(raw_location)
    if not text:
        return None, None
    parts = [part.strip() for part in text.split(",") if part.strip()]
    if len(parts) >= 2:
        return parts[0], parts[-1]
    return text, None


def raw_export_columns_present(frame: pd.DataFrame) -> bool:
    raw_columns = {"expediente", "fecha", "hora", "lugar", "suceso", "tipo", "matricula", "operacion"}
    return raw_columns.issubset(set(frame.columns))


def normalize_raw_export(frame: pd.DataFrame) -> pd.DataFrame:
    raw_records = frame.copy()
    raw_records = raw_records[
        raw_records.apply(
            lambda row: any(
                normalize_text(row.get(column))
                for column in ["expediente", "fecha", "suceso", "tipo", "matricula", "operacion"]
            ),
            axis=1,
        )
    ].copy()

    normalized_records: list[dict[str, object]] = []
    for _, row in raw_records.iterrows():
        expediente = normalize_text(row.get("expediente"))
        fecha = normalize_text(row.get("fecha"))
        hora = normalize_text(row.get("hora"))
        fecha_hora = normalize_datetime(f"{fecha} {hora}".strip()) or normalize_datetime(fecha)
        ciudad, provincia = split_location(row.get("lugar"))
        suceso = normalize_text(row.get("suceso"))
        tipo = normalize_text(row.get("tipo"))
        operacion = normalize_text(row.get("operacion"))
        traceability = resolve_traceability(tipo, suceso, operacion)
        descripcion_parts = [part for part in [tipo, suceso, operacion, normalize_text(row.get("lugar"))] if part]
        descripcion = " | ".join(descripcion_parts)
        source_record_id = f"JST-RAW-{slugify(expediente or fecha_hora or descripcion) or 'SIN-ID'}"
        normalized_records.append(
            {
                "source_record_id": source_record_id,
                "fecha_hora": fecha_hora,
                "aeropuerto_icao": None,
                "aeropuerto_nombre": normalize_nullable_text(row.get("Nombre:")),
                "ciudad": ciudad,
                "provincia": provincia,
                "tipo_incidente": suceso or tipo,
                "categoria_incidente": traceability["categoria_incidente"],
                "fase_vuelo": traceability["fase_vuelo"],
                "descripcion": descripcion or normalize_nullable_text(row.get("url")),
                "aeronave_modelo": None,
                "aeronave_matricula": normalize_nullable_text(row.get("matricula")),
                "tipo_aeronave": None,
                "condicion_meteorologica": None,
                "condicion_luz": None,
                "visibilidad_millas": None,
                "viento_kt": None,
                "latitud": normalize_float(row.get("Latitude")),
                "longitud": normalize_float(row.get("Longitude")),
                "lesionados": 0,
                "fatalidades": 0,
                "nivel_riesgo": traceability["nivel_riesgo"],
                "event_codes": traceability["event_codes"],
                "mapped_event_codes": traceability["mapped_event_codes"],
                "unknown_event_codes": traceability["unknown_event_codes"],
                "mapping_rule_source": traceability["mapping_rule_source"],
                "mapping_version": traceability["mapping_version"],
            }
        )

    output = pd.DataFrame(normalized_records)
    output = output.dropna(subset=["fecha_hora", "descripcion", "nivel_riesgo"], how="any")
    return output


def merge_normalized_rows(existing: pd.DataFrame, incoming: pd.DataFrame) -> pd.DataFrame:
    incoming_ids = {normalize_text(value) for value in incoming.get("source_record_id", pd.Series(dtype=str)).tolist() if normalize_text(value)}
    if incoming_ids and "source_record_id" in existing.columns:
        existing = existing[~existing["source_record_id"].fillna("").astype(str).isin(incoming_ids)].copy()

    combined = pd.concat([existing, incoming], ignore_index=True)
    combined["dedupe_key"] = combined.apply(
        lambda row: "||".join(
            [
                normalize_text(row.get("source_record_id")),
                normalize_text(row.get("fecha_hora")),
                normalize_text(row.get("aeronave_matricula")),
                normalize_text(row.get("descripcion")),
            ]
        ),
        axis=1,
    )
    combined = combined.drop_duplicates(subset=["dedupe_key"], keep="first").drop(columns=["dedupe_key"])
    combined = combined.sort_values(by=["fecha_hora", "source_record_id"], na_position="last").reset_index(drop=True)
    return combined


def export_normalized_csv(frame: pd.DataFrame, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False, encoding="utf-8")
    return output_path


def export_event_code_audit(frame: pd.DataFrame, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    audit_records: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        codes = [code for code in normalize_text(row.get("event_codes")).split("|") if code]
        mapped_codes = set(code for code in normalize_text(row.get("mapped_event_codes")).split("|") if code)
        unknown_codes = set(code for code in normalize_text(row.get("unknown_event_codes")).split("|") if code)
        for code in codes:
            audit_records.append(
                {
                    "event_code": code,
                    "mapped_in_catalog": code in mapped_codes,
                    "unknown_in_catalog": code in unknown_codes,
                    "source_record_id": normalize_text(row.get("source_record_id")),
                    "categoria_incidente": normalize_text(row.get("categoria_incidente")),
                    "fase_vuelo": normalize_text(row.get("fase_vuelo")),
                    "nivel_riesgo": normalize_text(row.get("nivel_riesgo")),
                    "mapping_rule_source": normalize_text(row.get("mapping_rule_source")),
                }
            )

    audit_frame = pd.DataFrame(audit_records)
    if audit_frame.empty:
        audit_frame = pd.DataFrame(
            columns=[
                "event_code",
                "mapped_in_catalog",
                "unknown_in_catalog",
                "source_record_id",
                "categoria_incidente",
                "fase_vuelo",
                "nivel_riesgo",
                "mapping_rule_source",
            ]
        )
    audit_frame.to_csv(output_path, index=False, encoding="utf-8")
    return output_path


def load_jst_input(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, low_memory=False)
    if raw_export_columns_present(frame):
        return normalize_raw_export(frame)

    required = [
        "source_record_id",
        "fecha_hora",
        "aeropuerto_icao",
        "aeropuerto_nombre",
        "tipo_incidente",
        "fase_vuelo",
        "descripcion",
        "nivel_riesgo",
    ]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Faltan columnas requeridas en JST CSV: {', '.join(missing)}")
    return frame


def to_training_frame(frame: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        records.append(
            {
                "fuente": "JST",
                "source_record_id": normalize_text(row.get("source_record_id")),
                "fecha_hora": normalize_datetime(row.get("fecha_hora")),
                "fecha": pd.to_datetime(row.get("fecha_hora"), errors="coerce").date().isoformat() if not pd.isna(pd.to_datetime(row.get("fecha_hora"), errors="coerce")) else None,
                "hora": pd.to_datetime(row.get("fecha_hora"), errors="coerce").strftime("%H%M") if not pd.isna(pd.to_datetime(row.get("fecha_hora"), errors="coerce")) else None,
                "aeropuerto_icao": normalize_nullable_text(row.get("aeropuerto_icao")),
                "aeropuerto_nombre": normalize_nullable_text(row.get("aeropuerto_nombre")),
                "ciudad": normalize_nullable_text(row.get("ciudad")),
                "provincia": normalize_nullable_text(row.get("provincia")),
                "fase_vuelo": normalize_nullable_text(row.get("fase_vuelo")),
                "descripcion": normalize_nullable_text(row.get("descripcion")),
                "tipo_incidente": normalize_nullable_text(row.get("tipo_incidente")),
                "categoria_incidente": normalize_nullable_text(row.get("categoria_incidente")),
                "aeronave_modelo": normalize_nullable_text(row.get("aeronave_modelo")),
                "aeronave_matricula": normalize_nullable_text(row.get("aeronave_matricula")),
                "tipo_aeronave": normalize_nullable_text(row.get("tipo_aeronave")),
                "condicion_meteorologica": normalize_nullable_text(row.get("condicion_meteorologica")),
                "condicion_luz": normalize_nullable_text(row.get("condicion_luz")),
                "visibilidad_millas": normalize_float(row.get("visibilidad_millas")),
                "viento_kt": normalize_float(row.get("viento_kt")),
                "latitud": normalize_float(row.get("latitud")),
                "longitud": normalize_float(row.get("longitud")),
                "lesionados": int(normalize_float(row.get("lesionados")) or 0),
                "fatalidades": int(normalize_float(row.get("fatalidades")) or 0),
                "nivel_riesgo": normalize_risk_label(row.get("nivel_riesgo")),
            }
        )

    output = pd.DataFrame(records)
    output = output.dropna(subset=["fecha_hora", "descripcion", "nivel_riesgo"], how="any")
    return output


def export_training_csv(frame: pd.DataFrame, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False, encoding="utf-8")
    return output_path


def resolve_airport(db, row: pd.Series) -> Aeropuerto | None:
    aeropuerto_icao = normalize_nullable_text(row.get("aeropuerto_icao"))
    aeropuerto_nombre = normalize_nullable_text(row.get("aeropuerto_nombre"))

    if aeropuerto_icao:
        airport = db.scalar(select(Aeropuerto).where(Aeropuerto.codigo_icao == aeropuerto_icao))
        if airport:
            return airport

    if aeropuerto_nombre:
        return db.scalar(select(Aeropuerto).where(Aeropuerto.nombre == aeropuerto_nombre))

    return None


def resolve_incident_type(db, row: pd.Series) -> TipoIncidente | None:
    nombre = normalize_nullable_text(row.get("tipo_incidente"))
    categoria = normalize_nullable_text(row.get("categoria_incidente"))
    if not nombre:
        return None

    incident_type = db.scalar(select(TipoIncidente).where(TipoIncidente.nombre == nombre))
    if incident_type:
        if categoria and not incident_type.categoria:
            incident_type.categoria = categoria
        return incident_type

    incident_type = TipoIncidente(nombre=nombre, categoria=categoria, codigo_oaci=None)
    db.add(incident_type)
    db.flush()
    return incident_type


def resolve_aircraft(db, row: pd.Series) -> Aeronave | None:
    matricula = normalize_nullable_text(row.get("aeronave_matricula"))
    modelo = normalize_nullable_text(row.get("aeronave_modelo"))
    tipo = normalize_nullable_text(row.get("tipo_aeronave"))

    if matricula:
        aircraft = db.scalar(select(Aeronave).where(Aeronave.matricula == matricula))
        if aircraft:
            if modelo and not aircraft.modelo:
                aircraft.modelo = modelo
            if tipo and not aircraft.tipo_aeronave:
                aircraft.tipo_aeronave = tipo
            return aircraft

        aircraft = Aeronave(matricula=matricula, modelo=modelo, tipo_aeronave=tipo)
        db.add(aircraft)
        db.flush()
        return aircraft

    return None


def import_into_postgres(frame: pd.DataFrame) -> int:
    inserted = 0
    with SessionLocal() as db:
        for _, row in frame.iterrows():
            fecha_hora = pd.to_datetime(row["fecha_hora"], errors="coerce")
            if pd.isna(fecha_hora):
                continue

            airport = resolve_airport(db, row)
            incident_type = resolve_incident_type(db, row)
            aircraft = resolve_aircraft(db, row)
            descripcion = normalize_nullable_text(row.get("descripcion"))

            duplicate = db.scalar(
                select(Incidente).where(
                    Incidente.fecha_hora == fecha_hora.to_pydatetime(),
                    Incidente.descripcion == descripcion,
                    Incidente.aeropuerto_id == (airport.id if airport else None),
                )
            )
            if duplicate:
                continue

            incidente = Incidente(
                aeropuerto_id=airport.id if airport else None,
                tipo_incidente_id=incident_type.id if incident_type else None,
                aeronave_id=aircraft.id if aircraft else None,
                fecha_hora=fecha_hora.to_pydatetime(),
                descripcion=descripcion,
                nivel_riesgo=normalize_nullable_text(row.get("nivel_riesgo")),
                fase_vuelo=normalize_nullable_text(row.get("fase_vuelo")),
                condicion_meteorologica=normalize_nullable_text(row.get("condicion_meteorologica")),
                condicion_luz=normalize_nullable_text(row.get("condicion_luz")),
                visibilidad_millas=normalize_float(row.get("visibilidad_millas")),
                viento_kt=normalize_float(row.get("viento_kt")),
                latitud=normalize_float(row.get("latitud")),
                longitud=normalize_float(row.get("longitud")),
            )
            db.add(incidente)
            inserted += 1

        db.commit()

    return inserted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Importa incidentes JST Argentina al dataset y opcionalmente a PostgreSQL.")
    parser.add_argument("--input", type=Path, default=INPUT_PATH, help="CSV fuente con incidentes JST normalizados.")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="CSV de salida listo para entrenamiento.")
    parser.add_argument(
        "--normalized-output",
        type=Path,
        default=NORMALIZED_OUTPUT_PATH,
        help="CSV normalizado consolidado para mantener actualizado el template JST.",
    )
    parser.add_argument(
        "--event-code-audit-output",
        type=Path,
        default=EVENT_CODE_AUDIT_PATH,
        help="CSV de auditoria por codigo de evento JST usado en la clasificacion.",
    )
    parser.add_argument("--skip-db", action="store_true", help="Solo exporta CSV de entrenamiento y no inserta en PostgreSQL.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = load_jst_input(args.input)
    normalized_source = source if "source_record_id" in source.columns else to_training_frame(source)

    if args.normalized_output.exists():
        existing = pd.read_csv(args.normalized_output, low_memory=False)
        normalized_source = merge_normalized_rows(existing, normalized_source)

    normalized_path = export_normalized_csv(normalized_source, args.normalized_output)
    event_code_audit_path = export_event_code_audit(normalized_source, args.event_code_audit_output)
    training_frame = to_training_frame(normalized_source)
    export_path = export_training_csv(training_frame, args.output)
    print(f"CSV JST normalizado actualizado en: {normalized_path}")
    print(f"Auditoria de codigos JST exportada a: {event_code_audit_path}")
    print(f"CSV JST exportado a: {export_path}")
    print(f"Registros JST listos para entrenamiento: {len(training_frame)}")

    if not args.skip_db:
        inserted = import_into_postgres(training_frame)
        print(f"Incidentes JST insertados en PostgreSQL: {inserted}")


if __name__ == "__main__":
    main()
