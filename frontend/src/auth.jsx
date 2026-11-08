import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { api, getToken, setToken } from "./api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(() => Boolean(getToken()));

  // On load, turn a stored token back into a signed-in user (or drop it if it expired).
  useEffect(() => {
    if (!getToken()) return;
    api
      .me()
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setChecking(false));
  }, []);

  const signIn = useCallback(async (email, password) => {
    const { access_token } = await api.login(email, password);
    setToken(access_token);
    setUser(await api.me());
  }, []);

  const signUp = useCallback(async (email, password, fullName) => {
    const { access_token } = await api.register(email, password, fullName);
    setToken(access_token);
    setUser(await api.me());
  }, []);

  const signOut = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, checking, signIn, signUp, signOut }), [user, checking, signIn, signUp, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}

export function RequireAuth({ children }) {
  const { user, checking } = useAuth();
  const location = useLocation();
  if (checking) return <p className="loading">Loading…</p>;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return children;
}
