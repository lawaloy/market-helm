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
    if (axios.isAxiosError(err) && err.response?.status === 501) {
      return false;
    }
    if (axios.isAxiosError(err) && err.response?.status === 401) {
      return true;
    }
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
          } catch {
            clearAuthToken();
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
