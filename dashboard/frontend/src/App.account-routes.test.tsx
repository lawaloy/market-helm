import { cleanup, render, screen } from '@testing-library/react';
import type React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';

const apiMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  runCheck: vi.fn(),
}));

const authMocks = vi.hoisted(() => ({
  user: null as { id: string; email: string } | null,
  multiUserEnabled: false,
  clearSession: vi.fn(),
}));

vi.mock('./contexts/ThemeContext', () => ({
  ThemeProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('./contexts/AuthContext', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuth: () => ({
    user: authMocks.user,
    loading: false,
    multiUserEnabled: authMocks.multiUserEnabled,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    clearSession: authMocks.clearSession,
  }),
}));

vi.mock('./components/layout/Header', () => ({
  default: () => <header>MarketHelm</header>,
}));

vi.mock('./pages/Dashboard', () => ({
  default: () => <main><h1>Dashboard route</h1></main>,
}));

vi.mock('./pages/HistoricalTrends', () => ({
  default: () => <main><h1>Historical Trends route</h1></main>,
}));

vi.mock('./pages/Summary', () => ({
  default: () => <main><h1>Summary route</h1></main>,
}));

vi.mock('./pages/AlertsSettings', () => ({
  default: () => <main><h1>Helmtower route</h1></main>,
}));

vi.mock('./services/api', () => ({
  default: {
    get: apiMocks.get,
    post: apiMocks.post,
  },
  alertsApi: {
    runCheck: apiMocks.runCheck,
  },
  authApi: {
    login: vi.fn(),
    register: vi.fn(),
    me: vi.fn(),
    logout: vi.fn(),
    changePassword: vi.fn(),
    deleteAccount: vi.fn(),
    requestPasswordReset: vi.fn(),
    confirmPasswordReset: vi.fn(),
    requestEmailVerification: vi.fn(),
    confirmEmailVerification: vi.fn(),
  },
}));

describe('App account and recovery routes', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/');
    authMocks.user = null;
    authMocks.multiUserEnabled = false;
    apiMocks.get.mockResolvedValue({ data: { needs_fetch: false } });
    apiMocks.post.mockResolvedValue({ data: {} });
    apiMocks.runCheck.mockResolvedValue({ data: {} });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it.each([
    ['/forgot-password', 'Reset your password'],
    ['/reset-password', 'Choose a new password'],
    ['/verify-email', 'Verify your email'],
  ])('renders %s so account-email links do not 404', (path, heading) => {
    window.history.pushState({}, '', path);

    render(<App />);

    expect(screen.getByRole('heading', { name: heading })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Back to sign in' }).getAttribute('href')).toBe(
      '/sign-in',
    );
  });

  it('keeps /account behind RequireAuth for hosted anonymous users', () => {
    authMocks.multiUserEnabled = true;
    window.history.pushState({}, '', '/account');

    render(<App />);

    expect(screen.queryByRole('heading', { name: 'Account' })).toBeNull();
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeTruthy();
    expect(window.location.pathname).toBe('/sign-in');
    expect(window.location.search).toBe('?return=%2Faccount');
  });

  it('renders account settings for a signed-in hosted user', () => {
    authMocks.multiUserEnabled = true;
    authMocks.user = { id: 'u1', email: 'user@example.com' };
    window.history.pushState({}, '', '/account');

    render(<App />);

    expect(screen.getByRole('heading', { name: 'Account' })).toBeTruthy();
    expect(screen.getByText('Signed in as user@example.com')).toBeTruthy();
  });
});
