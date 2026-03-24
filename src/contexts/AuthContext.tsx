import { createContext, useContext, useEffect, useState } from 'react';
import { api } from '../lib/api';
import type { AuthSession, RolUsuario, Usuario } from '../lib/types';

interface AuthContextType {
  user: Usuario | null;
  usuario: Usuario | null;
  session: AuthSession | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, nombre: string, rol: RolUsuario) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<Usuario | null>(null);
  const [session, setSession] = useState<AuthSession | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = api.getToken();

    if (!token) {
      setLoading(false);
      return;
    }

    setSession({ access_token: token });
    void loadCurrentUser();
  }, []);

  async function loadCurrentUser() {
    try {
      const currentUser = await api.getMe();
      setUser(currentUser);
    } catch (error) {
      console.error('Error loading authenticated user:', error);
      api.clearToken();
      setSession(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  async function signIn(email: string, password: string) {
    const response = await api.signIn(email, password);
    api.setToken(response.access_token);
    setSession({ access_token: response.access_token });
    setUser(response.user);
  }

  async function signUp(email: string, password: string, nombre: string, rol: RolUsuario) {
    const response = await api.signUp(email, password, nombre, rol);
    api.setToken(response.access_token);
    setSession({ access_token: response.access_token });
    setUser(response.user);
  }

  async function signOut() {
    api.clearToken();
    setSession(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, usuario: user, session, loading, signIn, signUp, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
