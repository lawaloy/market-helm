import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider, useAuth } from './AuthContext';
import { AUTH_TOKEN_KEY, authApi } from '../services/api';

function AuthState() {
  const { loading, multiUserEnabled, user } = useAuth();
  return (
    <span data-testid="auth-state">
      {loading
        ? 'loading'
        : `${multiUserEnabled ? 'multi-user' : 'single-user'}:${user?.email ?? 'anonymous'}`}
    </span>
  );
}

describe('AuthProvider init cancel', () => {
  afterEach(() => {
    cleanup();
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('ignores a late /me session restore after unmount', async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, 'good-token');
    let resolveMe: ((value: Awaited<ReturnType<typeof authApi.me>>) => void) | undefined;
    vi.spyOn(authApi, 'me').mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveMe = resolve;
        }),
    );

    render(
      <AuthProvider>
        <AuthState />
      </AuthProvider>,
    );
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByTestId('auth-state').textContent).toBe('loading');

    cleanup();

    await act(async () => {
      resolveMe?.({
        data: { id: 'u1', email: 'stale@example.com' },
      } as Awaited<ReturnType<typeof authApi.me>>);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.queryByTestId('auth-state')).toBeNull();
    expect(screen.queryByText(/stale@example.com/)).toBeNull();
  });

  it('ignores a late multi-user probe after unmount when no token is stored', async () => {
    let rejectMe: ((reason?: unknown) => void) | undefined;
    vi.spyOn(authApi, 'me').mockImplementation(
      () =>
        new Promise((_resolve, reject) => {
          rejectMe = reject;
        }),
    );

    render(
      <AuthProvider>
        <AuthState />
      </AuthProvider>,
    );
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByTestId('auth-state').textContent).toBe('loading');

    cleanup();

    await act(async () => {
      rejectMe?.({
        isAxiosError: true,
        response: { status: 401 },
      });
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.queryByTestId('auth-state')).toBeNull();
    expect(screen.queryByText(/multi-user/)).toBeNull();
  });
});
