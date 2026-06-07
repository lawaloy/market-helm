import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';

const apiMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  runCheck: vi.fn(),
}));

vi.mock('./contexts/ThemeContext', () => ({
  ThemeProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('./components/layout/Header', () => ({
  default: ({ backgroundFetching }: { backgroundFetching: boolean }) => (
    <header>
      MarketHelm
      <span data-testid="background-fetching">
        {backgroundFetching ? 'fetching' : 'idle'}
      </span>
    </header>
  ),
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

describe('App routing', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/');
    apiMocks.get.mockResolvedValue({ data: { needs_fetch: false } });
    apiMocks.post.mockResolvedValue({ data: {} });
    apiMocks.runCheck.mockResolvedValue({ data: {} });
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it.each([
    ['/', 'Dashboard', 'Dashboard route', 'border-blue-500'],
    ['/historical', 'Historical Trends', 'Historical Trends route', 'border-blue-500'],
    ['/summary', 'Summary', 'Summary route', 'border-blue-500'],
    ['/alerts', 'Helmtower', 'Helmtower route', 'border-teal-500'],
  ])('renders %s with the matching active nav link', (path, linkName, heading, activeClass) => {
    window.history.pushState({}, '', path);

    render(<App />);

    expect(screen.getByRole('heading', { name: heading })).toBeTruthy();
    expect(screen.getByRole('link', { name: linkName }).className).toContain(activeClass);
  });

  it('navigates between dashboard routes without a full reload', () => {
    render(<App />);

    fireEvent.click(screen.getByRole('link', { name: 'Summary' }));

    expect(window.location.pathname).toBe('/summary');
    expect(screen.getByRole('heading', { name: 'Summary route' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Summary' }).className).toContain('border-blue-500');
    expect(screen.getByRole('link', { name: 'Dashboard' }).className).toContain('border-transparent');
  });

  it('auto-fetches missing data, polls refresh status, and rechecks alerts after success', async () => {
    vi.useFakeTimers();
    let statusCalls = 0;

    apiMocks.get.mockImplementation((url: string) => {
      if (url === '/api/data-info') {
        return Promise.resolve({ data: { needs_fetch: true } });
      }

      if (url === '/api/refresh/status') {
        statusCalls += 1;
        return Promise.resolve({
          data: statusCalls === 1
            ? { is_running: true, last_status: 'running' }
            : { is_running: false, last_status: 'success' },
        });
      }

      return Promise.reject(new Error(`Unexpected GET ${url}`));
    });

    render(<App />);

    await waitFor(() => {
      expect(apiMocks.post).toHaveBeenCalledWith('/api/refresh');
    });
    expect(screen.getByTestId('background-fetching').textContent).toBe('fetching');
    expect(screen.getByTestId('dashboard-refresh-key').textContent).toBe('0');
    expect(apiMocks.get).toHaveBeenCalledWith('/api/refresh/status');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    await waitFor(() => {
      expect(screen.getByTestId('dashboard-refresh-key').textContent).toBe('1');
    });
    expect(screen.getByTestId('background-fetching').textContent).toBe('idle');
    expect(apiMocks.runCheck).toHaveBeenCalledTimes(2);
  });
});
