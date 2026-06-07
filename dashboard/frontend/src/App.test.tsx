import { cleanup, fireEvent, render, screen } from '@testing-library/react';
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
});
