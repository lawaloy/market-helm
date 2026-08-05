import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import axios from 'axios';
import { authApi, clearAuthToken, getAuthToken, setAuthToken } from '../services/api';
import type { User } from '../types';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  multiUserEnabled: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

async function probeMultiUserMode(): Promise<boolean> {
  try {
    await authApi.me();
    return true;
  } catch (err) {
    // Only an explicit 501 means single-user / auth disabled.
    if (axios.isAxiosError(err) && err.response?.status === 501) {
      return false;
    }
    // Any other HTTP response (401, 5xx, …) means the multi-user API is
    // present — keep RequireAuth gated so a transient backend error cannot
    // open hosted routes while the API still requires a bearer token.
    if (axios.isAxiosError(err) && err.response) {
      return true;
    }
    // Network / non-HTTP failures: prefer local single-user UX.
    return false;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [multiUserEnabled, setMultiUserEnabled] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const init = async () => {
      const token = getAuthToken();
      try {
        if (token) {
          try {
            const { data } = await authApi.me();
            if (!cancelled) {
              setUser(data);
              setMultiUserEnabled(true);
            }
            return;
          } catch (err) {
            // Auth disabled while a stale token remains — drop it and leave
            // single-user mode (do not fall through to a second /me probe).
            if (axios.isAxiosError(err) && err.response?.status === 501) {
              clearAuthToken();
              if (!cancelled) {
                setMultiUserEnabled(false);
              }
              return;
            }
            // Only clear on explicit auth rejection. Transient 5xx / network
            // failures must keep the session so a blip cannot bounce a signed-in
            // user to SignIn while RequireAuth still expects a bearer.
            if (
              axios.isAxiosError(err) &&
              (err.response?.status === 401 || err.response?.status === 403)
            ) {
              clearAuthToken();
            } else {
              if (!cancelled) {
                setMultiUserEnabled(true);
              }
              return;
            }
          }
        }

        const enabled = await probeMultiUserMode();
        if (!cancelled) {
          setMultiUserEnabled(enabled);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void init();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { data } = await authApi.login({ email, password });
    setAuthToken(data.access_token);
    setUser(data.user);
    setMultiUserEnabled(true);
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const { data } = await authApi.register({ email, password });
    setAuthToken(data.access_token);
    setUser(data.user);
    setMultiUserEnabled(true);
  }, []);

  const logout = useCallback(() => {
    clearAuthToken();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{ user, loading, multiUserEnabled, login, register, logout }}
    >
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
