"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { api, setAuthToken, setUnauthorizedHandler } from "@/lib/api";

const TOKEN_KEY = "sb_token";
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  const persist = useCallback((value) => {
    setToken(value);
    setAuthToken(value); // attach/detach on the api client
    if (typeof window !== "undefined") {
      if (value) localStorage.setItem(TOKEN_KEY, value);
      else localStorage.removeItem(TOKEN_KEY);
    }
  }, []);

  const logout = useCallback(() => {
    persist(null);
    setUser(null);
  }, [persist]);

  // Restore token on first load; wire 401 -> auto logout (expired token).
  useEffect(() => {
    const stored = typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;
    if (stored) persist(stored);
    setReady(true);
    setUnauthorizedHandler(logout);
  }, [persist, logout]);

  // Resolve the current user whenever we hold a token.
  useEffect(() => {
    if (!token) {
      setUser(null);
      return;
    }
    api.get("/auth/me").then(setUser).catch(() => {});
  }, [token]);

  const login = useCallback(
    async (email, password) => {
      const res = await api.post("/auth/login", { email, password });
      persist(res.access_token);
    },
    [persist],
  );

  const signup = useCallback(
    async (email, password) => {
      const res = await api.post("/auth/signup", { email, password });
      persist(res.access_token);
    },
    [persist],
  );

  return (
    <AuthContext.Provider value={{ token, user, ready, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
