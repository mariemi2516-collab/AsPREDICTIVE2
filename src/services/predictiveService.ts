export interface PredictiveResult {
  score: number;
  nivel: 'Bajo' | 'Medio' | 'Alto' | 'Crítico';
  factores?: string[];
  modelo?: string;
  fuente?: 'api' | 'fallback';
}

const predictiveApiBaseUrl =
  import.meta.env.VITE_PREDICTIVE_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';

function getNivelDesdeScore(score: number): PredictiveResult['nivel'] {
  if (score > 85) return 'Crítico';
  if (score > 70) return 'Alto';
  if (score > 50) return 'Medio';
  return 'Bajo';
}

function getPrediccionLocal(data: unknown): PredictiveResult {
  const payload = (typeof data === 'object' && data !== null ? data : {}) as {
    descripcion?: unknown;
    fase_vuelo?: unknown;
  };
  const descripcion = String(payload.descripcion ?? '').toLowerCase();
  const faseVuelo = String(payload.fase_vuelo ?? '').toLowerCase();

  let score = 35;

  if (descripcion.length > 120) score += 8;
  if (/(falla|incendio|colisi[oó]n|emergencia|motor|p[ée]rdida|impacto)/.test(descripcion)) score += 30;
  if (/(despegue|aterrizaje)/.test(faseVuelo)) score += 18;
  if (/(crucero|rodaje)/.test(faseVuelo)) score += 8;

  score = Math.max(20, Math.min(95, score));

  return {
    score,
    nivel: getNivelDesdeScore(score)
  };
}

export async function getPrediccionRiesgo(data: unknown): Promise<PredictiveResult> {
  try {
    const response = await fetch(`${predictiveApiBaseUrl}/predict`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });

    if (!response.ok) {
      throw new Error('Error en predicción');
    }

    const result = await response.json();
    const score = Number(result?.score);

    if (!Number.isFinite(score)) {
      throw new Error('Respuesta inválida del servicio predictivo');
    }

    return {
      score,
      nivel: ['Bajo', 'Medio', 'Alto', 'Crítico'].includes(result?.nivel) ? result.nivel : getNivelDesdeScore(score),
      factores: Array.isArray(result?.factores) ? result.factores.map(String) : [],
      modelo: typeof result?.modelo === 'string' ? result.modelo : undefined,
      fuente: 'api'
    };
  } catch (error) {
    console.warn('Predictive service unavailable, using local fallback:', error);
    return {
      ...getPrediccionLocal(data),
      factores: ['Predicción local de contingencia'],
      modelo: 'fallback-heuristico',
      fuente: 'fallback'
    };
  }
}

