import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider, useAuth } from './AuthContext';
import { AUTH_TOKEN_KEY, authApi } from '../services/api';

function axiosStatus(status: number) {
  return {
    isAxiosError: true,
    response: { status },
  };
}

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

describe('AuthProvider', () => {
  afterEach(() => {
    cleanup();
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('treats a 501 /me probe as single-user mode', async () => {
    const me = vi.spyOn(authApi, 'me').mockRejectedValueOnce(axiosStatus(501));

    render(
      <AuthProvider>
        <AuthState />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth-state').textContent).toBe('single-user:anonymous');
    });
    expect(me).toHaveBeenCalledTimes(1);
  });

  it('clears an invalid stored token and keeps hosted mode enabled after a 401 probe', async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, 'stale-token');
    const me = vi
      .spyOn(authApi, 'me')
      .mockRejectedValueOnce(axiosStatus(401))
      .mockRejectedValueOnce(axiosStatus(401));

    render(
      <AuthProvider>
        <AuthState />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth-state').textContent).toBe('multi-user:anonymous');
    });
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
    expect(me).toHaveBeenCalledTimes(2);
  });
});
