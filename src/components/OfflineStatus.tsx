import { useEffect, useState } from 'react';
import { CloudOff, RefreshCcw, Wifi } from 'lucide-react';
import { api } from '../lib/api';
import { subscribeOfflineQueue } from '../lib/offlineQueue';

export default function OfflineStatus() {
  const [online, setOnline] = useState(navigator.onLine);
  const [pending, setPending] = useState(api.getOfflineQueueSize());
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    const handleOnline = async () => {
      setOnline(true);
      setSyncing(true);
      try {
        const result = await api.syncOfflineQueue();
        setPending(result.pendientes);
      } finally {
        setSyncing(false);
      }
    };

    const handleOffline = () => setOnline(false);
    const unsubscribe = subscribeOfflineQueue(() => setPending(api.getOfflineQueueSize()));

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      unsubscribe();
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  if (online && pending === 0 && !syncing) return null;

  return (
    <div className="border-b border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          {online ? <Wifi className="h-4 w-4 text-emerald-700" /> : <CloudOff className="h-4 w-4 text-amber-700" />}
          <div>
            <p className="font-medium">
              {online ? 'Conexion recuperada' : 'Modo offline activo'}
            </p>
            <p className="text-xs text-amber-900/80">
              {online
                ? `${pending} operaciones pendientes de sincronizacion`
                : 'Los cambios compatibles se guardaran localmente y se enviaran al reconectar.'}
            </p>
          </div>
        </div>
        {online && pending > 0 && (
          <button
            onClick={async () => {
              setSyncing(true);
              try {
                const result = await api.syncOfflineQueue();
                setPending(result.pendientes);
              } finally {
                setSyncing(false);
              }
            }}
            className="inline-flex items-center gap-2 rounded-xl border border-amber-300 bg-white px-3 py-2 text-xs font-medium text-amber-900 transition hover:bg-amber-100"
          >
            <RefreshCcw className={`h-3.5 w-3.5 ${syncing ? 'animate-spin' : ''}`} />
            {syncing ? 'Sincronizando...' : 'Sincronizar ahora'}
          </button>
        )}
      </div>
    </div>
  );
}
