import { act, cleanup, render, screen } from '@testing-library/react';
import type React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';

const apiMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  runCheck: vi.fn(),
  fetchingLog: [] as boolean[],
}));

vi.mock('./contexts/ThemeContext', () => ({
  ThemeProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('./contexts/AuthContext', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuth: () => ({
    user: null,
    loading: false,
    multiUserEnabled: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }),
}));

vi.mock('./components/layout/Header', () => ({
  default: ({ backgroundFetching }: { backgroundFetching: boolean }) => {
    apiMocks.fetchingLog.push(backgroundFetching);
    return (
      <header>
        MarketHelm
        <span data-testid="background-fetching">
          {backgroundFetching ? 'fetching' : 'idle'}
        </span>
      </header>
    );
  },
}));

vi.mock('./pages/Dashboard', () => ({
  default: ({ refreshKey }: { refreshKey: number }) => (
    <main>
      <h1>Dashboard route</h1>
      <span data-testid="dashboard-refresh-key">{refreshKey}</span>
    </main>
  ),
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
}));

describe('App background autofetch races', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/');
    apiMocks.fetchingLog.length = 0;
    apiMocks.get.mockResolvedValue({ data: { needs_fetch: false } });
    apiMocks.post.mockResolvedValue({ data: {} });
    apiMocks.runCheck.mockResolvedValue({ data: {} });
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('does not start refresh after unmount when data-info resolves late', async () => {
    let resolveDataInfo: ((value: unknown) => void) | undefined;
    apiMocks.get.mockImplementation((url: string) => {
      if (url === '/api/data-info') {
        return new Promise((resolve) => {
          resolveDataInfo = resolve;
        });
      }
      return Promise.reject(new Error(`Unexpected GET ${url}`));
    });

    render(<App />);
    await act(async () => {
      await Promise.resolve();
    });

    cleanup();

    await act(async () => {
      resolveDataInfo?.({ data: { needs_fetch: true } });
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(apiMocks.post).not.toHaveBeenCalled();
  });

  it('ignores a late successful refresh status after unmount', async () => {
    vi.useFakeTimers();
    let resolveStatus: ((value: unknown) => void) | undefined;

    apiMocks.get.mockImplementation((url: string) => {
      if (url === '/api/data-info') {
        return Promise.resolve({ data: { needs_fetch: true } });
      }
      if (url === '/api/refresh/status') {
        return new Promise((resolve) => {
          resolveStatus = resolve;
        });
      }
      return Promise.reject(new Error(`Unexpected GET ${url}`));
    });

    render(<App />);

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(apiMocks.post).toHaveBeenCalledWith('/api/refresh');
    expect(screen.getByTestId('background-fetching').textContent).toBe('fetching');
    expect(screen.getByTestId('dashboard-refresh-key').textContent).toBe('0');

    const runCheckBeforeUnmount = apiMocks.runCheck.mock.calls.length;
    cleanup();

    await act(async () => {
      resolveStatus?.({
        data: { is_running: false, last_status: 'success' },
      });
      await Promise.resolve();
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(0);
    });

    // Late success must not call onRefreshComplete (which rechecks alerts).
    expect(apiMocks.runCheck.mock.calls.length).toBe(runCheckBeforeUnmount);
    expect(apiMocks.fetchingLog.filter((v) => v === true).length).toBeGreaterThan(0);
  });
});
