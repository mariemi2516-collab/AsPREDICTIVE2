import { useEffect, useState } from 'react';
import { AlertTriangle, RefreshCcw, Trash2 } from 'lucide-react';
import { getOfflineConflicts, removeOfflineConflict, retryOfflineConflict, subscribeOfflineQueue, type OfflineConflict } from '../lib/offlineQueue';

export default function OfflineConflictsPanel() {
  const [conflicts, setConflicts] = useState<OfflineConflict[]>([]);

  useEffect(() => {
    const load = async () => setConflicts(await getOfflineConflicts());
    void load();
    return subscribeOfflineQueue(() => {
      void load();
    });
  }, []);

  if (!conflicts.length) return null;

  return (
    <div className="border-b border-red-200 bg-red-50 px-4 py-3 text-sm text-red-950">
      <div className="mx-auto max-w-7xl">
        <div className="mb-3 flex items-center gap-3">
          <AlertTriangle className="h-4 w-4 text-red-700" />
          <div>
            <p className="font-medium">Conflictos de sincronizacion</p>
            <p className="text-xs text-red-900/80">
              Hay {conflicts.length} operaciones que no pudieron aplicarse en el servidor.
            </p>
          </div>
        </div>

        <div className="space-y-2">
          {conflicts.slice(0, 5).map((conflict) => (
            <div key={conflict.id} className="rounded-xl border border-red-200 bg-white/80 px-4 py-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium text-slate-900">{conflict.label}</p>
                  <p className="mt-1 text-xs uppercase tracking-[0.16em] text-slate-400">
                    {conflict.method} {conflict.path}
                  </p>
                  <p className="mt-2 text-sm text-red-800">{conflict.message}</p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      void retryOfflineConflict(conflict.id);
                    }}
                    className="inline-flex items-center gap-1 rounded-lg border border-red-300 bg-white px-3 py-2 text-xs font-medium text-red-800 transition hover:bg-red-100"
                  >
                    <RefreshCcw className="h-3.5 w-3.5" />
                    Reintentar
                  </button>
                  <button
                    onClick={() => {
                      void removeOfflineConflict(conflict.id);
                    }}
                    className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-700 transition hover:bg-slate-100"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Descartar
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
