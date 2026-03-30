import { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { LockKeyhole, Plane } from 'lucide-react';

export default function Login() {
  const { signIn } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await signIn(email, password);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'No se pudo iniciar sesion.';
      setError(message || 'No se pudo iniciar sesion.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-sky-50 via-blue-50 to-cyan-50 p-4">
      <div className="w-full max-w-md">
        <div className="rounded-2xl bg-white p-8 shadow-xl">
          <div className="mb-6 flex justify-center">
            <div className="rounded-xl bg-gradient-to-br from-sky-500 to-blue-600 p-4">
              <Plane className="h-10 w-10 text-white" />
            </div>
          </div>

          <h1 className="mb-2 text-center text-3xl font-bold text-gray-900">AsPREDICTIVE</h1>
          <p className="mb-8 text-center text-gray-600">
            Plataforma de seguridad operacional y analitica predictiva
          </p>

          <form onSubmit={handleSubmit} className="space-y-6">
            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <div>
              <label htmlFor="email" className="mb-2 block text-sm font-medium text-gray-700">
                Correo electronico
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full rounded-lg border border-gray-300 px-4 py-3 transition focus:border-transparent focus:ring-2 focus:ring-blue-500"
                placeholder="usuario@ejemplo.com"
              />
            </div>

            <div>
              <label htmlFor="password" className="mb-2 block text-sm font-medium text-gray-700">
                Contrasena
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full rounded-lg border border-gray-300 px-4 py-3 transition focus:border-transparent focus:ring-2 focus:ring-blue-500"
                placeholder="Ingresa tu contrasena"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-gradient-to-r from-sky-500 to-blue-600 px-4 py-3 font-semibold text-white shadow-lg shadow-blue-500/30 transition duration-200 hover:from-sky-600 hover:to-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? 'Iniciando sesion...' : 'Iniciar sesion'}
            </button>
          </form>

          <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
              Acceso institucional
            </p>
            <div className="mt-3 space-y-2 text-sm text-slate-700">
              <p className="flex items-center gap-2">
                <LockKeyhole className="h-4 w-4 text-sky-700" />
                Ingresa con credenciales provistas por la administracion del sistema.
              </p>
            </div>
          </div>

          <p className="mt-6 text-center text-sm text-gray-600">
            Sistema de gestion de seguridad aeronautica
          </p>
        </div>
      </div>
    </div>
  );
}
