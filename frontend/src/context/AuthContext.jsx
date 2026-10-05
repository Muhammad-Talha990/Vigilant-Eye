import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import {
  fetchCurrentUser,
  googleLoginRequest,
  loginRequest,
} from "../services/api";

const AuthContext = createContext(null);

const TOKEN_KEY = "ve_token";
const USER_KEY = "ve_user";

/** Roles are DB uppercase strings; normalize so nav never misses ADMINISTRATOR. */
function normalizeUser(raw) {
  if (!raw || typeof raw !== "object") return null;
  const role = typeof raw.role === "string" ? raw.role.trim().toUpperCase() : raw.role;
  return { ...raw, role };
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    try {
      return normalizeUser(JSON.parse(raw));
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(Boolean(token));
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        const me = normalizeUser(await fetchCurrentUser());
        if (!cancelled) {
          setUser(me);
          localStorage.setItem(USER_KEY, JSON.stringify(me));
        }
      } catch {
        if (!cancelled) {
          localStorage.removeItem(TOKEN_KEY);
          localStorage.removeItem(USER_KEY);
          setToken(null);
          setUser(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    restoreSession();
    return () => {
      cancelled = true;
    };
  }, [token]);

  const applySession = useCallback((data) => {
    const nextUser = normalizeUser(data.user);
    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(nextUser));
    setToken(data.access_token);
    setUser(nextUser);
    return nextUser;
  }, []);

  const login = useCallback(
    async (email, password) => {
      setError("");
      const data = await loginRequest(email, password);
      return applySession(data);
    },
    [applySession]
  );

  const loginWithGoogle = useCallback(
    async (idToken) => {
      setError("");
      const data = await googleLoginRequest(idToken);
      return applySession(data);
    },
    [applySession]
  );

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setToken(null);
    setUser(null);
  }

  const value = useMemo(
    () => ({
      token,
      user,
      loading,
      error,
      setError,
      login,
      loginWithGoogle,
      logout,
      isAuthenticated: Boolean(token && user),
    }),
    [token, user, loading, error, login, loginWithGoogle]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return ctx;
}
