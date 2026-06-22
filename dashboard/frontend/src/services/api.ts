import axios from 'axios';
import type {
  MarketOverview,
  MoversResponse,
  ProjectionsSummary,
  OpportunitiesResponse,
  StockDetail,
  HistoricalData,
  HistoricalSummaryResponse,
  MarketSummaryResponse,
  ProjectionAccuracyResponse,
  AlertsConfigResponse,
  AlertsConfig,
  AlertTestResponse,
  AlertsStatus,
  AlertsRunResponse,
  AuthResponse,
  User,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

export const AUTH_TOKEN_KEY = 'market-helm-token';

export function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

export function setAuthToken(token: string): void {
  localStorage.setItem(AUTH_TOKEN_KEY, token);
}

export function clearAuthToken(): void {
  localStorage.removeItem(AUTH_TOKEN_KEY);
}

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
});

api.interceptors.request.use((config) => {
  const token = getAuthToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Log API failures in development only
if (import.meta.env.DEV) {
  api.interceptors.response.use(
    (res) => res,
    (err) => {
      console.error('[API] Request failed:', err.config?.url, err.response?.status, err.message);
      return Promise.reject(err);
    }
  );
}

// Market endpoints
export const marketApi = {
  getOverview: () => api.get<MarketOverview>('/api/market/overview'),
  getMovers: (type: 'gainers' | 'losers', limit: number = 10) =>
    api.get<MoversResponse>('/api/market/movers', { params: { type, limit } }),
};

// Projections endpoints
export const projectionsApi = {
  getSummary: () => api.get<ProjectionsSummary>('/api/projections/summary'),
  getOpportunities: (type: string, limit: number = 10) =>
    api.get<OpportunitiesResponse>('/api/projections/opportunities', {
      params: { type, limit },
    }),
};

// Summary endpoint (market AI/demo summary)
export const summaryApi = {
  getSummary: () => api.get<MarketSummaryResponse>('/api/summary'),
};

// History endpoints
export const historyApi = {
  getDates: () => api.get<{ dates: string[] }>('/api/history/dates'),
  getSummary: (days: number = 30) =>
    api.get<HistoricalSummaryResponse>('/api/history/summary', { params: { days } }),
  getAccuracy: (days: number = 90) =>
    api.get<ProjectionAccuracyResponse>('/api/history/accuracy', { params: { days } }),
  getSymbols: () =>
    api.get<{ symbols: string[]; names: Record<string, string>; date: string }>('/api/history/symbols'),
};

// Stocks endpoints
export const stocksApi = {
  getDetail: (symbol: string) => api.get<StockDetail>(`/api/stocks/${symbol}`),
  getHistorical: (symbol: string, days: number = 30) =>
    api.get<HistoricalData>(`/api/stocks/${symbol}/historical`, {
      params: { days },
    }),
};

export const alertsApi = {
  getConfig: () => api.get<AlertsConfigResponse>('/api/alerts/config'),
  saveConfig: (config: AlertsConfig) => api.put<AlertsConfigResponse>('/api/alerts/config', config),
  initConfig: (force = false) =>
    api.post<{ message: string }>('/api/alerts/init', null, {
      params: force ? { force: true } : undefined,
    }),
  testAlert: (id: string, dryRun = false) =>
    api.post<AlertTestResponse>(
      '/api/alerts/test',
      { id, dry_run: dryRun },
      { timeout: 30000 },
    ),
  getSymbols: () =>
    api.get<{
      symbols: string[];
      names: Record<string, string>;
      count: number;
      tracked_symbols?: string[];
      prices?: Record<string, number>;
    }>('/api/alerts/symbols'),
  getQuotes: (symbols: string[]) =>
    api.get<{ prices: Record<string, number> }>('/api/alerts/quotes', {
      params: { symbols: symbols.join(',') },
      timeout: 45000,
    }),
  getStatus: () => api.get<AlertsStatus>('/api/alerts/status'),
  runCheck: () => api.post<AlertsRunResponse>('/api/alerts/run'),
};

export const authApi = {
  register: (body: { email: string; password: string }) =>
    api.post<AuthResponse>('/api/auth/register', body),
  login: (body: { email: string; password: string }) =>
    api.post<AuthResponse>('/api/auth/login', body),
  me: () => api.get<User>('/api/auth/me'),
};

export default api;
