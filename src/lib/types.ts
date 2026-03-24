export type RolUsuario = 'administrador' | 'inspector' | 'analista' | 'supervisor';

export interface Usuario {
  id: string;
  nombre: string;
  email: string;
  rol: RolUsuario;
  estado: boolean;
  ultimo_login: string | null;
  created_at: string;
}

export interface AuthSession {
  access_token: string;
}

export interface Aeropuerto {
  id: number;
  codigo_iata: string | null;
  codigo_icao: string;
  nombre: string;
  ciudad: string | null;
  provincia: string | null;
  categoria: string | null;
  estado: string;
  latitud: number | null;
  longitud: number | null;
  created_at: string;
}

export interface TipoIncidente {
  id: number;
  codigo_oaci: string | null;
  nombre: string;
  categoria: string | null;
}

export interface Aeronave {
  id: number;
  matricula: string;
  modelo: string | null;
  fabricante: string | null;
  anio_fabricacion: number | null;
  operador: string | null;
  tipo_aeronave: string | null;
  peso_maximo_despegue: number | null;
  ultima_revision_mtto: string | null;
}

export type NivelRiesgo = 'Bajo' | 'Medio' | 'Alto' | 'Crítico';

export interface Incidente {
  id: number;
  aeropuerto_id: number | null;
  pista_id: number | null;
  aeronave_id: number | null;
  tipo_incidente_id: number | null;
  fecha_hora: string;
  descripcion: string | null;
  nivel_riesgo: NivelRiesgo | null;
  fase_vuelo: string | null;
  latitud: number | null;
  longitud: number | null;
  reportado_por: string | null;
  created_at: string;
  aeropuertos?: Pick<Aeropuerto, 'nombre' | 'codigo_icao'> | null;
  tipos_incidente?: Pick<TipoIncidente, 'nombre'> | null;
  aeronaves?: Pick<Aeronave, 'matricula'> | null;
}

export interface Alerta {
  id: number;
  aeropuerto_id: number | null;
  fecha_generacion: string;
  tipo_alerta: string | null;
  nivel_criticidad: string | null;
  mensaje: string | null;
  score_predictivo: number | null;
  ejecucion_agente_id: number | null;
  estado: string;
  atendido_por: string | null;
  fecha_resolucion: string | null;
  aeropuertos?: Pick<Aeropuerto, 'nombre'> | null;
}

export interface DashboardSummary {
  stats: {
    totalIncidentes: number;
    alertasActivas: number;
    aeropuertos: number;
    riesgoPromedio: number;
    riesgoFuturo: number;
  };
  recentIncidentes: Incidente[];
  alertas: Alerta[];
}

export interface FormCatalogs {
  aeropuertos: Aeropuerto[];
  tipos_incidente: TipoIncidente[];
  aeronaves: Aeronave[];
}
