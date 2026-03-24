import { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import {
  Activity,
  AlertTriangle,
  LogOut,
  MapPin,
  Plane,
  Shield,
  TrendingUp,
} from 'lucide-react';
import { api } from '../lib/api';
import type { Alerta, Incidente } from '../lib/types';
import { getPrediccionRiesgo, type PredictiveResult } from '../services/predictiveService';
import AlertasPanel from './AlertasPanel';
import IncidentesTable from './IncidentesTable';
import InstitutionalPanel from './InstitutionalPanel';

type IncidentPrediction = PredictiveResult & {
  incidentId: number;
};

async function generarAlertasPredictivas() {
  const incidentes = await api.listIncidentes(20);
  if (!incidentes?.length) return;

  const alertasPendientes = await api.listAlertasPendientes(50);

  await Promise.all(
    incidentes.map(async (incidente) => {
      const pred = await getPrediccionRiesgo(incidente);
      if (pred.score <= 70) return;

      const resumenFactores = pred.factores?.slice(0, 2).join(', ');
      const mensaje = resumenFactores
        ? `Alto riesgo detectado en incidente ${incidente.id}. Factores: ${resumenFactores}.`
        : `Alto riesgo detectado en incidente ${incidente.id}`;

      const alertaExistente = alertasPendientes.find(
        (alerta) =>
          alerta.tipo_alerta === 'Riesgo Predictivo' &&
          (alerta.mensaje || '').includes(`incidente ${incidente.id}`),
      );
      if (alertaExistente) return;

      await api.createAlerta({
        tipo_alerta: 'Riesgo Predictivo',
        mensaje,
        nivel_criticidad: pred.score > 85 ? 'Critico' : 'Alta',
        estado: 'Pendiente',
        score_predictivo: pred.score,
        aeropuerto_id: incidente.aeropuerto_id,
      });
    }),
  );
}

function getRiesgoColor(nivel: string | null) {
  switch (nivel) {
    case 'Critico':
    case 'Crítico':
      return 'bg-red-100 text-red-800 border-red-200';
    case 'Alto':
      return 'bg-orange-100 text-orange-800 border-orange-200';
    case 'Medio':
      return 'bg-amber-100 text-amber-800 border-amber-200';
    case 'Bajo':
      return 'bg-emerald-100 text-emerald-800 border-emerald-200';
    default:
      return 'bg-slate-100 text-slate-700 border-slate-200';
  }
}

function StatCard({
  title,
  value,
  subtitle,
  icon,
}: {
  title: string;
  value: string | number;
  subtitle: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white/95 p-5 shadow-sm shadow-slate-200/60">
      <div className="mb-4 flex items-start justify-between">
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-slate-700">{icon}</div>
        <span className="text-3xl font-semibold tracking-tight text-slate-900">{value}</span>
      </div>
      <p className="text-sm font-medium text-slate-900">{title}</p>
      <p className="mt-1 text-xs text-slate-500">{subtitle}</p>
    </div>
  );
}

export default function Dashboard() {
  const { usuario, signOut } = useAuth();

  const [stats, setStats] = useState({
    totalIncidentes: 0,
    alertasActivas: 0,
    aeropuertos: 0,
    riesgoPromedio: 0,
    riesgoFuturo: 0,
  });
  const [recentIncidentes, setRecentIncidentes] = useState<Incidente[]>([]);
  const [alertas, setAlertas] = useState<Alerta[]>([]);
  const [incidentPredictions, setIncidentPredictions] = useState<Record<number, IncidentPrediction>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboardData();
  }, []);

  async function loadDashboardData() {
    try {
      await generarAlertasPredictivas();
      const summary = await api.getDashboardSummary();
      const predictions = await Promise.all(
        summary.recentIncidentes.map(async (incidente) => ({
          incidentId: incidente.id,
          ...(await getPrediccionRiesgo(incidente)),
        })),
      );

      setRecentIncidentes(summary.recentIncidentes);
      setAlertas(summary.alertas);
      setStats(summary.stats);
      setIncidentPredictions(
        predictions.reduce<Record<number, IncidentPrediction>>((acc, prediction) => {
          acc[prediction.incidentId] = prediction;
          return acc;
        }, {}),
      );
    } catch (error) {
      console.error('Error loading dashboard:', error);
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,_#dbeafe,_#eff6ff_42%,_#f8fafc_72%)]">
        <div className="rounded-2xl border border-slate-200 bg-white/90 px-8 py-6 text-center shadow-xl shadow-slate-200/50">
          <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-b-2 border-sky-700" />
          <p className="text-sm font-medium text-slate-700">Cargando tablero operativo...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_#dbeafe,_#eff6ff_42%,_#f8fafc_72%)] text-slate-900">
      <nav className="border-b border-white/60 bg-white/80 backdrop-blur-xl">
        <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-4">
            <div className="rounded-2xl bg-[linear-gradient(135deg,#0f172a,#0369a1)] p-3 shadow-lg shadow-sky-900/20">
              <Plane className="h-7 w-7 text-white" />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.28em] text-sky-700">
                Centro de control operativo
              </p>
              <h1 className="text-xl font-semibold tracking-tight text-slate-950">
                AsPREDICTIVE Seguridad Operacional
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="hidden rounded-2xl border border-slate-200 bg-white/90 px-4 py-2 text-right md:block">
              <p className="text-sm font-semibold text-slate-900">{usuario?.nombre}</p>
              <p className="text-xs uppercase tracking-[0.18em] text-slate-500">{usuario?.rol}</p>
            </div>
            <button
              onClick={() => signOut()}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
            >
              <LogOut className="h-4 w-4" />
              Salir
            </button>
          </div>
        </div>
      </nav>

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <section className="mb-8 overflow-hidden rounded-[28px] border border-slate-200 bg-[linear-gradient(135deg,rgba(15,23,42,0.96),rgba(3,105,161,0.92))] px-6 py-7 text-white shadow-2xl shadow-sky-900/20 lg:px-8">
          <div className="grid gap-8 lg:grid-cols-[1.7fr_1fr]">
            <div>
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-sky-100">
                <Shield className="h-3.5 w-3.5" />
                Vigilancia predictiva
              </div>
              <h2 className="max-w-3xl text-3xl font-semibold tracking-tight">
                Centro de control para incidentes, alertas y trazabilidad institucional.
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-6 text-sky-50/90">
                El tablero integra riesgo operacional, analitica predictiva, auditorias, acciones correctivas,
                alertas y seguimiento regulatorio en una sola vista.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
              <div className="rounded-2xl border border-white/15 bg-white/10 p-4">
                <p className="text-xs uppercase tracking-[0.22em] text-sky-100/80">Riesgo 24h</p>
                <p className="mt-2 text-3xl font-semibold">{stats.riesgoFuturo}%</p>
              </div>
              <div className="rounded-2xl border border-white/15 bg-white/10 p-4">
                <p className="text-xs uppercase tracking-[0.22em] text-sky-100/80">Alertas activas</p>
                <p className="mt-2 text-3xl font-semibold">{stats.alertasActivas}</p>
              </div>
              <div className="rounded-2xl border border-white/15 bg-white/10 p-4">
                <p className="text-xs uppercase tracking-[0.22em] text-sky-100/80">Aeropuertos</p>
                <p className="mt-2 text-3xl font-semibold">{stats.aeropuertos}</p>
              </div>
            </div>
          </div>
        </section>

        <section className="mb-8 grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-4">
          <StatCard
            title="Incidentes registrados"
            value={stats.totalIncidentes}
            subtitle="Volumen total de eventos operacionales trazados"
            icon={<AlertTriangle className="h-5 w-5" />}
          />
          <StatCard
            title="Alertas activas"
            value={stats.alertasActivas}
            subtitle="Eventos que requieren seguimiento inmediato"
            icon={<Activity className="h-5 w-5" />}
          />
          <StatCard
            title="Aeropuertos monitoreados"
            value={stats.aeropuertos}
            subtitle="Cobertura operacional del despliegue"
            icon={<MapPin className="h-5 w-5" />}
          />
          <StatCard
            title="Indice de riesgo"
            value={`${stats.riesgoPromedio}%`}
            subtitle="Promedio consolidado de severidad observada"
            icon={<TrendingUp className="h-5 w-5" />}
          />
        </section>

        <section className="mb-8 grid gap-8 xl:grid-cols-[1.25fr_0.95fr]">
          <div className="rounded-2xl border border-slate-200 bg-white/95 p-6 shadow-sm shadow-slate-200/60">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold tracking-tight text-slate-950">Incidentes recientes</h3>
                <p className="text-sm text-slate-500">Eventos priorizados con lectura operacional y explicabilidad del modelo.</p>
              </div>
            </div>

            <div className="space-y-4">
              {recentIncidentes.map((incidente) => (
                <article key={incidente.id} className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-base font-semibold text-slate-900">{incidente.tipos_incidente?.nombre || 'Incidente'}</p>
                      <p className="mt-1 text-sm text-slate-500">{incidente.aeropuertos?.nombre || 'Aeropuerto no identificado'}</p>
                    </div>
                    {incidentPredictions[incidente.id] && (
                      <div className="text-right">
                        <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Puntaje IA</p>
                        <p className="text-2xl font-semibold text-sky-700">{incidentPredictions[incidente.id].score}%</p>
                      </div>
                    )}
                  </div>

                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${getRiesgoColor(incidente.nivel_riesgo)}`}>
                      {incidente.nivel_riesgo || 'Sin clasificar'}
                    </span>
                    {incidente.fase_vuelo && (
                      <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-600">
                        {incidente.fase_vuelo}
                      </span>
                    )}
                  </div>

                  {incidentPredictions[incidente.id] && (
                    <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
                      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
                        <span className="rounded-full bg-sky-100 px-2.5 py-1 font-medium text-sky-800">
                          Modelo: {incidentPredictions[incidente.id].modelo || 'No disponible'}
                        </span>
                        <span className="rounded-full bg-slate-100 px-2.5 py-1 font-medium text-slate-700">
                          Origen: {incidentPredictions[incidente.id].fuente === 'api' ? 'Produccion' : 'Contingencia local'}
                        </span>
                      </div>
                      <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Factores principales</p>
                      <div className="flex flex-wrap gap-2">
                        {(incidentPredictions[incidente.id].factores?.slice(0, 3) || ['Sin factores disponibles']).map((factor) => (
                          <span key={factor} className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-700">
                            {factor}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </article>
              ))}
            </div>
          </div>

          <div className="space-y-6">
            <section className="rounded-2xl border border-slate-200 bg-white/95 p-6 shadow-sm shadow-slate-200/60">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold tracking-tight text-slate-950">Riesgo proximas 24 h</h3>
                  <p className="text-sm text-slate-500">Estimacion basada en narrativa, clima, fase de vuelo y contexto operacional.</p>
                </div>
                <span className="text-3xl font-semibold text-sky-700">{stats.riesgoFuturo}%</span>
              </div>

              <div className="space-y-4">
                <div className="rounded-xl border border-sky-100 bg-sky-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-sky-800">Explicabilidad IA</p>
                  <p className="mt-2 text-sm leading-6 text-sky-900">
                    El motor pondera narrativa del incidente, fase de vuelo, condiciones de luz, visibilidad,
                    viento y otras señales operacionales para priorizar riesgo.
                  </p>
                </div>
                <div className="rounded-xl border border-emerald-100 bg-emerald-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-800">Motor desplegado</p>
                  <p className="mt-2 text-sm leading-6 text-emerald-900">
                    Entrenado con datos oficiales NTSB y base local expandible con JST Argentina e incidentes operativos propios.
                  </p>
                </div>
              </div>
            </section>

            <AlertasPanel alertas={alertas} onUpdate={loadDashboardData} />
          </div>
        </section>

        <IncidentesTable onUpdate={loadDashboardData} />

        <div className="mt-8">
          <InstitutionalPanel onUpdate={loadDashboardData} />
        </div>
      </main>
    </div>
  );
}
