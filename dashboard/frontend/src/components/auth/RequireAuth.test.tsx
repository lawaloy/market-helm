import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import RequireAuth from './RequireAuth';

const authMocks = vi.hoisted(() => ({
  useAuthImpl: vi.fn(),
}));

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => authMocks.useAuthImpl(),
}));

function LocationDisplay() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname + location.search}</span>;
}

function renderProtectedRoute(initialEntry = '/alerts') {
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route
          path="/alerts"
          element={
            <RequireAuth>
              <h1>Private Helmtower</h1>
            </RequireAuth>
          }
        />
        <Route
          path="/sign-in"
          element={
            <main>
              <h1>Sign In Route</h1>
              <LocationDisplay />
            </main>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe('RequireAuth', () => {
  beforeEach(() => {
    authMocks.useAuthImpl.mockReturnValue({
      user: null,
      loading: false,
      multiUserEnabled: true,
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('redirects unauthenticated hosted users and preserves the requested alerts route', () => {
    renderProtectedRoute('/alerts?symbol=AAPL');

    expect(screen.queryByRole('heading', { name: 'Private Helmtower' })).toBeNull();
    expect(screen.getByRole('heading', { name: 'Sign In Route' })).toBeTruthy();
    expect(screen.getByTestId('location').textContent).toBe(
      '/sign-in?return=%2Falerts%3Fsymbol%3DAAPL',
    );
  });

  it('allows unauthenticated access when the server is in single-user mode', () => {
    authMocks.useAuthImpl.mockReturnValue({
      user: null,
      loading: false,
      multiUserEnabled: false,
    });

    renderProtectedRoute();

    expect(screen.getByRole('heading', { name: 'Private Helmtower' })).toBeTruthy();
  });
});
