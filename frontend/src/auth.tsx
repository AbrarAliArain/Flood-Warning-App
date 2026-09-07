import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

const STORAGE_KEY = "aquashield.auth";
const DEMO_PASSWORD = "AquaShieldDemo2026!";

interface AuthUser {
  id: number;
  full_name: string;
  role: string;
  phone?: string | null;
  email?: string | null;
  ngo_id?: number | null;
  ngo_name?: string | null;
  is_demo?: boolean;
}

interface AuthState {
  token: string | null;
  user: AuthUser | null;
}

interface AuthContextValue extends AuthState {
  loginDemoCitizen: () => Promise<void>;
  loginDemoResponder: () => Promise<void>;
  logout: () => void;
  isLoading: boolean;
  error: string | null;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function readStored(): AuthState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { token: null, user: null };
    const parsed = JSON.parse(raw) as AuthState;
    if (parsed.token && parsed.user) return parsed;
  } catch {
    // ignore corrupt storage
  }
  return { token: null, user: null };
}

function writeStored(state: AuthState) {
  if (state.token && state.user) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } else {
    localStorage.removeItem(STORAGE_KEY);
  }
}

async function loginWith(identifier: string): Promise<AuthState> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ identifier, password: DEMO_PASSWORD }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? `Login failed (${res.status})`);
  }
  const data = await res.json();
  return { token: data.access_token, user: data.user };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(() => readStored());
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    writeStored(state);
  }, [state]);

  const loginDemoCitizen = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setState(await loginWith("citizen@demo.example"));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loginDemoResponder = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setState(await loginWith("responder@demo.example"));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    setState({ token: null, user: null });
    setError(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      loginDemoCitizen,
      loginDemoResponder,
      logout,
      isLoading,
      error,
    }),
    [state, loginDemoCitizen, loginDemoResponder, logout, isLoading, error],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}

export function authHeaders(): Record<string, string> {
  const raw = readStored();
  return raw.token ? { Authorization: `Bearer ${raw.token}` } : {};
}
