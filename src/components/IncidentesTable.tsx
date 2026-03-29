import { useEffect, useState } from 'react';
import { Plus, Search } from 'lucide-react';
import IncidenteModal from './IncidenteModal';
import { api } from '../lib/api';
import { formatCoordinates, formatDateTime, formatWeatherSummary, summarizeDescription } from '../lib/presentation';
import type { Incidente } from '../lib/types';

interface Props {
  onUpdate: () => void;
}

export default function IncidentesTable({ onUpdate }: Props) {
  const [incidentes, setIncidentes] = useState<Incidente[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filtroRiesgo, setFiltroRiesgo] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [selectedIncidente, setSelectedIncidente] = useState<Incidente | null>(null);

  useEffect(() => {
    loadIncidentes();
  }, []);

  async function loadIncidentes() {
    try {
      const data = await api.listIncidentes(50);
      setIncidentes(data || []);
    } catch (error) {
      console.error('Error loading incidents:', error);
    } finally {
      setLoading(false);
    }
  }

  function handleCreateNew() {
    setSelectedIncidente(null);
    setShowModal(true);
  }

  function handleEdit(incidente: Incidente) {
    setSelectedIncidente(incidente);
    setShowModal(true);
  }

  async function handleModalClose() {
    setShowModal(false);
    setSelectedIncidente(null);
    await loadIncidentes();
    onUpdate();
  }

  function getRiesgoColor(nivel: string | null) {
    switch (nivel) {
      case 'Crítico': return 'bg-red-100 text-red-800 border-red-300';
      case 'Alto': return 'bg-orange-100 text-orange-800 border-orange-300';
      case 'Medio': return 'bg-yellow-100 text-yellow-800 border-yellow-300';
      case 'Bajo': return 'bg-green-100 text-green-800 border-green-300';
      default: return 'bg-gray-100 text-gray-800 border-gray-300';
    }
  }

  const filteredIncidentes = incidentes.filter((inc) => {
    const searchLower = searchTerm.toLowerCase();
    const matchesSearch =
      inc.aeropuertos?.nombre?.toLowerCase().includes(searchLower) ||
      inc.tipos_incidente?.nombre?.toLowerCase().includes(searchLower) ||
      inc.aeronaves?.matricula?.toLowerCase().includes(searchLower) ||
      inc.descripcion?.toLowerCase().includes(searchLower);
    const matchesRiesgo = filtroRiesgo ? inc.nivel_riesgo === filtroRiesgo : true;

    return (
      Boolean(matchesSearch) && matchesRiesgo
    );
  });

  if (loading) {
    return (
      <div className="bg-white rounded-xl shadow-lg border border-gray-100 p-8">
        <div className="flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="bg-white rounded-xl shadow-lg border border-gray-100 overflow-hidden">
        <div className="p-6 border-b border-gray-200">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <h2 className="text-lg font-bold text-gray-900">Gestión de Incidentes</h2>
            <div className="flex gap-3">
              <div className="relative flex-1 sm:w-64">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Buscar incidentes..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <select
                value={filtroRiesgo}
                onChange={(e) => setFiltroRiesgo(e.target.value)}
                className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">Todos los riesgos</option>
                <option value="Bajo">Bajo</option>
                <option value="Medio">Medio</option>
                <option value="Alto">Alto</option>
                <option value="Crítico">Crítico</option>
              </select>
              <button
                onClick={handleCreateNew}
                className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-sky-500 to-blue-600 text-white rounded-lg hover:from-sky-600 hover:to-blue-700 transition shadow-lg shadow-blue-500/30"
              >
                <Plus className="w-4 h-4" />
                <span className="hidden sm:inline">Nuevo</span>
              </button>
            </div>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                  Fecha/Hora
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                  Operacion
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                  Resumen operacional
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                  Condiciones
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                  Riesgo
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                  Fase
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredIncidentes.map((incidente) => (
                <tr
                  key={incidente.id}
                  onClick={() => handleEdit(incidente)}
                  className="hover:bg-gray-50 cursor-pointer transition"
                >
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {formatDateTime(incidente.fecha_hora)}
                  </td>
                  <td className="px-6 py-4">
                    <div>
                      <div className="text-sm font-medium text-gray-900">
                        {incidente.aeropuertos?.nombre || 'Aeropuerto no informado'}
                      </div>
                      <div className="text-xs text-gray-500">
                        {incidente.tipos_incidente?.nombre || 'Tipo sin especificar'}
                      </div>
                      <div className="text-xs text-gray-500">
                        {incidente.aeronaves?.matricula || 'Aeronave no informada'}
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900">
                    <p className="max-w-md leading-6 text-gray-900">
                      {summarizeDescription(incidente.descripcion)}
                    </p>
                    <p className="mt-2 text-xs text-gray-500">
                      Coordenadas: {formatCoordinates(incidente.latitud, incidente.longitud)}
                    </p>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900">
                    <p className="max-w-xs leading-6 text-gray-700">
                      {formatWeatherSummary(incidente)}
                    </p>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-3 py-1 inline-flex text-xs leading-5 font-semibold rounded-full border ${getRiesgoColor(incidente.nivel_riesgo)}`}>
                      {incidente.nivel_riesgo || 'N/A'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900">
                    {incidente.fase_vuelo || 'N/A'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filteredIncidentes.length === 0 && (
            <div className="text-center py-12">
              <p className="text-gray-500">No se encontraron incidentes</p>
            </div>
          )}
        </div>
      </div>

      {showModal && (
        <IncidenteModal
          incidente={selectedIncidente}
          onClose={handleModalClose}
        />
      )}
    </>
  );
}
