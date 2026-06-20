"use client";

import { useAuth } from "@/lib/auth";
import { LoginScreen } from "@/components/login-screen";

/** Gates the app: shows the login/signup screen until a token is present. */
export function AuthGate({ children }) {
  const { ready, token } = useAuth();
  if (!ready) return null; // brief flash while restoring the token from storage
  if (!token) return <LoginScreen />;
  return children;
}
