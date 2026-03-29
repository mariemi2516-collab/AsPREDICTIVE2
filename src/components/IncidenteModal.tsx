import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../lib/api';
import { formatCoordinates, formatWeatherSummary, summarizeDescription } from '../lib/presentation';
import type { Aeronave, Aeropuerto, Incidente, NivelRiesgo, TipoIncidente } from '../lib/types';
import { getPrediccionRiesgo } from '../services/predictiveService';

const FASES_VUELO = [
  'Plataforma',
  'Rodaje de salida',
  'Despegue',
  'Ascenso inicial',
  'Ascenso',
  'Crucero',
  'Descenso',
  'Aproximacion',
  'Aterrizaje',
  'Rodaje de llegada',
  'Estacionamiento',
];

const NIVELES_RIESGO = ['Bajo', 'Medio', 'Alto', 'Critico'];
const CONDICIONES_METEOROLOGICAS = ['VMC', 'IMC', 'Lluvia', 'Tormenta', 'Niebla', 'Viento fuerte', 'Ceniza', 'Nieve'];
const CONDICIONES_LUZ = ['Dia', 'Noche', 'Crepusculo', 'Amanecer'];

interface Props {
  incidente: Incidente | null;
  onClose: () => void;
}

export default function IncidenteModal({ incidente, onClose }: Props) {
  const { user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [aeropuertos, setAeropuertos] = useState<Aeropuerto[]>([]);
  const [tiposIncidente, setTiposIncidente] = useState<TipoIncidente[]>([]);
  const [aeronaves, setAeronaves] = useState<Aeronave[]>([]);

  const [formData, setFormData] = useState({
    aeropuerto_id: incidente?.aeropuerto_id || '',
    tipo_incidente_id: incidente?.tipo_incidente_id || '',
    aeronave_id: incidente?.aeronave_id || '',
    fecha_hora: incidente?.fecha_hora ? new Date(incidente.fecha_hora).toISOString().slice(0, 16) : '',
    descripcion: incidente?.descripcion || '',
    nivel_riesgo: (incidente?.nivel_riesgo || 'Bajo') as NivelRiesgo,
    fase_vuelo: incidente?.fase_vuelo || '',
    condicion_meteorologica: incidente?.condicion_meteorologica || '',
    condicion_luz: incidente?.condicion_luz || '',
    visibilidad_millas: incidente?.visibilidad_millas || '',
    viento_kt: incidente?.viento_kt || '',
    latitud: incidente?.latitud || '',
    longitud: incidente?.longitud || '',
  });

  useEffect(() => {
    loadFormData();
  }, []);

  async function loadFormData() {
    try {
      const data = await api.getFormCatalogs();
      setAeropuertos(data.aeropuertos);
      setTiposIncidente(data.tipos_incidente);
      setAeronaves(data.aeronaves);
    } catch (error) {
      console.error('Error loading form data:', error);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);

    try {
      const payloadBase = {
        ...formData,
        aeropuerto_id: formData.aeropuerto_id ? parseInt(formData.aeropuerto_id as string, 10) : null,
        tipo_incidente_id: formData.tipo_incidente_id ? parseInt(formData.tipo_incidente_id as string, 10) : null,
        aeronave_id: formData.aeronave_id ? parseInt(formData.aeronave_id as string, 10) : null,
      };

      const prediccion = await getPrediccionRiesgo(payloadBase);

      const dataToSave = {
        aeropuerto_id: payloadBase.aeropuerto_id,
        tipo_incidente_id: payloadBase.tipo_incidente_id,
        aeronave_id: payloadBase.aeronave_id,
        fecha_hora: formData.fecha_hora,
        descripcion: formData.descripcion,
        nivel_riesgo: prediccion.nivel,
        fase_vuelo: formData.fase_vuelo,
        condicion_meteorologica: formData.condicion_meteorologica || null,
        condicion_luz: formData.condicion_luz || null,
        visibilidad_millas: formData.visibilidad_millas ? parseFloat(formData.visibilidad_millas as string) : null,
        viento_kt: formData.viento_kt ? parseFloat(formData.viento_kt as string) : null,
        latitud: formData.latitud ? parseFloat(formData.latitud as string) : null,
        longitud: formData.longitud ? parseFloat(formData.longitud as string) : null,
        reportado_por: user?.id || null,
      };

      if (incidente) {
        await api.updateIncidente(incidente.id, dataToSave);
      } else {
        await api.createIncidente(dataToSave);
      }

      onClose();
    } catch (error) {
      console.error('Error saving incident:', error);
      alert('Error al guardar el incidente');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white shadow-2xl">
        <div className="sticky top-0 flex items-center justify-between border-b border-gray-200 bg-white p-6">
          <h2 className="text-xl font-bold text-gray-900">
            {incidente ? 'Editar incidente' : 'Nuevo incidente'}
          </h2>
          <button onClick={onClose} className="text-gray-400 transition hover:text-gray-600">
            <X className="h-6 w-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6 p-6">
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700">Aeropuerto</label>
              <select
                value={formData.aeropuerto_id}
                onChange={(e) => setFormData({ ...formData, aeropuerto_id: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-transparent focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Seleccionar aeropuerto</option>
                {aeropuertos.map((aeropuerto) => (
                  <option key={aeropuerto.id} value={aeropuerto.id}>
                    {aeropuerto.codigo_icao} - {aeropuerto.nombre}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700">Tipo de incidente</label>
              <select
                value={formData.tipo_incidente_id}
                onChange={(e) => setFormData({ ...formData, tipo_incidente_id: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-transparent focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Seleccionar tipo</option>
                {tiposIncidente.map((tipo) => (
                  <option key={tipo.id} value={tipo.id}>
                    {tipo.categoria ? `${tipo.nombre} (${tipo.categoria})` : tipo.nombre}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700">Aeronave</label>
              <select
                value={formData.aeronave_id}
                onChange={(e) => setFormData({ ...formData, aeronave_id: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-transparent focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Seleccionar aeronave</option>
                {aeronaves.map((aeronave) => (
                  <option key={aeronave.id} value={aeronave.id}>
                    {[aeronave.matricula, aeronave.modelo, aeronave.tipo_aeronave].filter(Boolean).join(' - ')}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700">Fecha y hora</label>
              <input
                type="datetime-local"
                value={formData.fecha_hora}
                onChange={(e) => setFormData({ ...formData, fecha_hora: e.target.value })}
                required
                className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-transparent focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700">Nivel de referencia</label>
              <select
                value={formData.nivel_riesgo}
                onChange={(e) => setFormData({ ...formData, nivel_riesgo: e.target.value as NivelRiesgo })}
                required
                className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-transparent focus:ring-2 focus:ring-blue-500"
              >
                {NIVELES_RIESGO.map((nivel) => (
                  <option key={nivel} value={nivel}>
                    {nivel}
                  </option>
                ))}
              </select>
              <p className="mt-2 text-xs text-gray-500">
                Este valor es orientativo. El nivel final se recalcula automaticamente con el motor predictivo al guardar.
              </p>
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700">Fase de vuelo</label>
              <select
                value={formData.fase_vuelo}
                onChange={(e) => setFormData({ ...formData, fase_vuelo: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-transparent focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Seleccionar fase</option>
                {FASES_VUELO.map((fase) => (
                  <option key={fase} value={fase}>
                    {fase}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700">Condicion meteorologica</label>
              <select
                value={formData.condicion_meteorologica}
                onChange={(e) => setFormData({ ...formData, condicion_meteorologica: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-transparent focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Seleccionar condicion</option>
                {CONDICIONES_METEOROLOGICAS.map((condicion) => (
                  <option key={condicion} value={condicion}>
                    {condicion}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700">Condicion de luz</label>
              <select
                value={formData.condicion_luz}
                onChange={(e) => setFormData({ ...formData, condicion_luz: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-transparent focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Seleccionar condicion</option>
                {CONDICIONES_LUZ.map((condicion) => (
                  <option key={condicion} value={condicion}>
                    {condicion}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700">Visibilidad (millas)</label>
              <input
                type="number"
                step="0.1"
                value={formData.visibilidad_millas}
                onChange={(e) => setFormData({ ...formData, visibilidad_millas: e.target.value })}
                placeholder="10"
                className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-transparent focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700">Viento (kt)</label>
              <input
                type="number"
                step="1"
                value={formData.viento_kt}
                onChange={(e) => setFormData({ ...formData, viento_kt: e.target.value })}
                placeholder="18"
                className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-transparent focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700">Latitud</label>
              <input
                type="number"
                step="0.000001"
                value={formData.latitud}
                onChange={(e) => setFormData({ ...formData, latitud: e.target.value })}
                placeholder="-34.123456"
                className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-transparent focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700">Longitud</label>
              <input
                type="number"
                step="0.000001"
                value={formData.longitud}
                onChange={(e) => setFormData({ ...formData, longitud: e.target.value })}
                placeholder="-58.123456"
                className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-transparent focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">Descripcion</label>
            <textarea
              value={formData.descripcion}
              onChange={(e) => setFormData({ ...formData, descripcion: e.target.value })}
              rows={4}
              className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-transparent focus:ring-2 focus:ring-blue-500"
              placeholder="Describe el incidente en detalle..."
            />
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Vista previa de carga</p>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <div>
                <p className="text-xs font-semibold text-slate-500">Descripcion</p>
                <p className="mt-1 text-sm leading-6 text-slate-700">{summarizeDescription(formData.descripcion)}</p>
              </div>
              <div>
                <p className="text-xs font-semibold text-slate-500">Ubicacion</p>
                <p className="mt-1 text-sm leading-6 text-slate-700">
                  {formatCoordinates(
                    formData.latitud ? parseFloat(String(formData.latitud)) : null,
                    formData.longitud ? parseFloat(String(formData.longitud)) : null,
                  )}
                </p>
              </div>
              <div className="md:col-span-2">
                <p className="text-xs font-semibold text-slate-500">Clima y condiciones</p>
                <p className="mt-1 text-sm leading-6 text-slate-700">
                  {formatWeatherSummary({
                    condicion_meteorologica: formData.condicion_meteorologica || null,
                    condicion_luz: formData.condicion_luz || null,
                    visibilidad_millas: formData.visibilidad_millas ? parseFloat(String(formData.visibilidad_millas)) : null,
                    viento_kt: formData.viento_kt ? parseFloat(String(formData.viento_kt)) : null,
                  })}
                </p>
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-3 border-t border-gray-200 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-gray-300 px-6 py-2 text-gray-700 transition hover:bg-gray-50"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading}
              className="rounded-lg bg-gradient-to-r from-sky-500 to-blue-600 px-6 py-2 text-white shadow-lg shadow-blue-500/30 transition hover:from-sky-600 hover:to-blue-700 disabled:opacity-50"
            >
              {loading ? 'Guardando...' : 'Guardar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
