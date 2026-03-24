import type {
  Aeropuerto,
  Aeronave,
  Alerta,
  AuthSession,
  DashboardSummary,
  FormCatalogs,
  Incidente,
  NivelRiesgo,
  ReporteEjecutivo,
  RolUsuario,
  TipoIncidente,
  Usuario,
} from './types';

const apiBaseUrl = import.meta.env.VITE_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';
const TOKEN_KEY = 'aviation_auth_token';

type RequestOptions = RequestInit & {
  auth?: boolean;
};

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function buildHeaders(initHeaders?: HeadersInit, auth = true) {
  const headers = new Headers(initHeaders);
  headers.set('Content-Type', 'application/json');

  if (auth) {
    const token = getToken();
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
  }

  return headers;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers: buildHeaders(options.headers, options.auth !== false),
  });

  if (!response.ok) {
    let message = 'Error inesperado en la API';
    try {
      const errorBody = await response.json();
      message = errorBody.detail || errorBody.message || message;
    } catch {
      message = response.statusText || message;
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export const api = {
  getBaseUrl() {
    return apiBaseUrl;
  },
  setToken(token: string) {
    localStorage.setItem(TOKEN_KEY, token);
  },
  clearToken() {
    localStorage.removeItem(TOKEN_KEY);
  },
  getToken,
  async signIn(email: string, password: string) {
    return request<{ access_token: string; user: Usuario }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
      auth: false,
    });
  },
  async signUp(email: string, password: string, nombre: string, rol: RolUsuario) {
    return request<{ access_token: string; user: Usuario }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, nombre, rol }),
      auth: false,
    });
  },
  async getMe() {
    return request<Usuario>('/auth/me');
  },
  async getDashboardSummary() {
    return request<DashboardSummary>('/dashboard/summary');
  },
  async getFormCatalogs() {
    return request<FormCatalogs>('/catalogs/form-data');
  },
  async listIncidentes(limit = 50) {
    return request<Incidente[]>(`/incidentes?limit=${limit}`);
  },
  async createIncidente(payload: {
    aeropuerto_id: number | null;
    tipo_incidente_id: number | null;
    aeronave_id: number | null;
    fecha_hora: string;
    descripcion: string;
    nivel_riesgo: NivelRiesgo;
    fase_vuelo: string;
    condicion_meteorologica?: string | null;
    condicion_luz?: string | null;
    visibilidad_millas?: number | null;
    viento_kt?: number | null;
    latitud: number | null;
    longitud: number | null;
  }) {
    return request<Incidente>('/incidentes', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  async updateIncidente(id: number, payload: {
    aeropuerto_id: number | null;
    tipo_incidente_id: number | null;
    aeronave_id: number | null;
    fecha_hora: string;
    descripcion: string;
    nivel_riesgo: NivelRiesgo;
    fase_vuelo: string;
    condicion_meteorologica?: string | null;
    condicion_luz?: string | null;
    visibilidad_millas?: number | null;
    viento_kt?: number | null;
    latitud: number | null;
    longitud: number | null;
  }) {
    return request<Incidente>(`/incidentes/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },
  async listAlertasPendientes(limit = 10) {
    return request<Alerta[]>(`/alertas?estado=Pendiente&limit=${limit}`);
  },
  async createAlerta(payload: {
    aeropuerto_id: number | null;
    tipo_alerta: string;
    nivel_criticidad: string;
    mensaje: string;
    score_predictivo: number | null;
    estado?: string;
  }) {
    return request<Alerta>('/alertas', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  async resolveAlerta(alertaId: number) {
    return request<Alerta>(`/alertas/${alertaId}/resolve`, {
      method: 'POST',
      body: JSON.stringify({}),
    });
  },
  async countAeropuertos() {
    return request<{ total: number }>('/catalogs/aeropuertos/count');
  },
  async listAeropuertos() {
    return request<Aeropuerto[]>('/catalogs/aeropuertos');
  },
  async listTiposIncidente() {
    return request<TipoIncidente[]>('/catalogs/tipos-incidente');
  },
  async listAeronaves() {
    return request<Aeronave[]>('/catalogs/aeronaves');
  },
  async getReporteEjecutivo(periodoDias = 90) {
    return request<ReporteEjecutivo>(`/reports/executive?periodo_dias=${periodoDias}`);
  },
};
