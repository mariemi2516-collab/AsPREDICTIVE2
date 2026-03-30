import type { Incidente } from './types';

function formatNumber(value: number, digits = 2) {
  return new Intl.NumberFormat('es-AR', {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatDateTime(value: string) {
  return new Date(value).toLocaleString('es-AR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatCoordinates(latitud: number | null, longitud: number | null) {
  if (latitud === null || longitud === null) {
    return 'Sin coordenadas registradas';
  }

  return `${formatNumber(latitud, 4)}, ${formatNumber(longitud, 4)}`;
}

export function formatWeatherSummary(incidente: Pick<Incidente, 'condicion_meteorologica' | 'condicion_luz' | 'visibilidad_millas' | 'viento_kt'>) {
  const parts: string[] = [];

  if (incidente.condicion_meteorologica) {
    parts.push(`Meteorologia: ${incidente.condicion_meteorologica}`);
  }
  if (incidente.condicion_luz) {
    parts.push(`Luz: ${incidente.condicion_luz}`);
  }
  if (incidente.visibilidad_millas !== null) {
    parts.push(`Visibilidad: ${formatNumber(incidente.visibilidad_millas)} mi`);
  }
  if (incidente.viento_kt !== null) {
    parts.push(`Viento: ${formatNumber(incidente.viento_kt)} kt`);
  }

  return parts.length ? parts.join(' | ') : 'Sin datos meteorologicos cargados';
}

export function summarizeDescription(value: string | null | undefined, fallback = 'Sin descripcion operacional cargada') {
  if (!value) return fallback;
  const clean = value.trim();
  if (!clean) return fallback;
  return clean;
}

function normalizeModelToken(value: string) {
  return value
    .replace(/^descripcion:\s*/i, 'Descripcion del evento: ')
    .replace(/^numeric:\s*has coordinates/i, 'El incidente cuenta con coordenadas registradas')
    .replace(/^numeric:\s*viento kt/i, 'La velocidad del viento influyo en la evaluacion')
    .replace(/^numeric:\s*visibilidad millas/i, 'La visibilidad reportada influyo en la evaluacion')
    .replace(/^numeric:\s*is night/i, 'La operacion se realizo en horario nocturno')
    .replace(/^numeric:\s*hour/i, 'La franja horaria del evento influyo en la evaluacion')
    .replace(/^numeric:\s*day of week/i, 'El dia de ocurrencia influyo en la evaluacion')
    .replace(/^numeric:\s*month/i, 'La estacionalidad del mes influyo en la evaluacion')
    .replace(/^categorical:\s*fase vuelo/i, 'La fase de vuelo influyo en la evaluacion')
    .replace(/^categorical:\s*condicion meteorologica/i, 'La condicion meteorologica influyo en la evaluacion')
    .replace(/^categorical:\s*condicion luz/i, 'La condicion de luz influyo en la evaluacion');
}

function isLowSignalDescriptionToken(value: string) {
  const token = value.trim().toLowerCase();
  return ['no', 'si', 'sí', 'sin', 'con', 'y', 'o', 'de', 'del', 'la', 'el', 'en'].includes(token) || token.length <= 2;
}

export function humanizePredictiveFactor(value: string) {
  const cleaned = value.replace(/\(\+[0-9.]+\)/g, '').trim();
  if (!cleaned) {
    return 'Sin factores explicativos disponibles';
  }

  const normalized = normalizeModelToken(cleaned)
    .replace(/_/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  if (/^el incidente cuenta con coordenadas registradas$/i.test(normalized)) {
    return 'La ubicacion georreferenciada del evento aporto precision al analisis';
  }

  if (/^la velocidad del viento influyo en la evaluacion$/i.test(normalized)) {
    return 'La intensidad del viento reportada aumento la atencion del caso';
  }

  if (/^la visibilidad reportada influyo en la evaluacion$/i.test(normalized)) {
    return 'La visibilidad informada fue relevante para estimar el nivel de riesgo';
  }

  if (/^la operacion se realizo en horario nocturno$/i.test(normalized)) {
    return 'El evento ocurrio en una franja horaria de mayor exigencia operacional';
  }

  if (/^descripcion del evento:\s*no$/i.test(normalized)) {
    return 'La descripcion del evento aporta informacion limitada y requiere validacion humana';
  }

  if (/^descripcion del evento:/i.test(normalized)) {
    const fragment = normalized.replace(/^descripcion del evento:\s*/i, '').trim();
    if (!fragment || isLowSignalDescriptionToken(fragment)) {
      return 'La narrativa del incidente aporto contexto general al analisis';
    }
    return fragment
      ? `En la descripcion aparecen terminos relevantes como "${fragment}"`
      : 'La descripcion del evento aporto contexto al analisis';
  }

  if (/^la fase de vuelo influyo en la evaluacion$/i.test(normalized)) {
    return 'La fase de vuelo del evento incidio en la priorizacion del riesgo';
  }

  if (/^la condicion meteorologica influyo en la evaluacion$/i.test(normalized)) {
    return 'Las condiciones meteorologicas declaradas influyeron en la evaluacion';
  }

  if (/^la condicion de luz influyo en la evaluacion$/i.test(normalized)) {
    return 'La condicion de iluminacion del evento fue considerada en el analisis';
  }

  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

export function humanizePredictiveFactors(factores: string[] | undefined) {
  if (!factores?.length) {
    return ['Sin factores explicativos disponibles'];
  }

  return factores.map(humanizePredictiveFactor);
}

export function buildIncidentAlertMessage(incidente: Incidente, score: number, factores: string[]) {
  const criticidad = score > 85 ? 'critico' : score > 70 ? 'alto' : 'moderado';
  const lineas = [
    `Riesgo ${criticidad} detectado para el incidente ${incidente.id}.`,
    `Descripcion: ${summarizeDescription(incidente.descripcion)}.`,
    `Fase de vuelo: ${incidente.fase_vuelo || 'Sin fase informada'}.`,
    `Clima y condiciones: ${formatWeatherSummary(incidente)}.`,
    `Coordenadas: ${formatCoordinates(incidente.latitud, incidente.longitud)}.`,
    `Factores relevantes: ${humanizePredictiveFactors(factores).join(' | ')}.`,
  ];

  return lineas.join('\n');
}

export function parseAlertMessageSections(message: string | null | undefined) {
  const fallback = summarizeDescription(message, 'Sin detalles adicionales disponibles');
  const lines = fallback
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);

  const summary = lines[0] || fallback;
  const details = lines.slice(1).map((line) => {
    const separatorIndex = line.indexOf(':');
    if (separatorIndex === -1) {
      return { label: 'Detalle', value: line };
    }
    return {
      label: line.slice(0, separatorIndex).trim(),
      value: line.slice(separatorIndex + 1).trim().replace(/\.$/, ''),
    };
  });

  return { summary, details };
}
