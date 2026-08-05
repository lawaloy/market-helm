import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
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

  it('treats a 500 /me probe as single-user mode (fail-closed)', async () => {
    const me = vi.spyOn(authApi, 'me').mockRejectedValueOnce(axiosStatus(500));

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

  it('treats a network /me probe failure as single-user mode (fail-closed)', async () => {
    const networkErr = {
      isAxiosError: true,
      message: 'Network Error',
      response: undefined,
    };
    const me = vi.spyOn(authApi, 'me').mockRejectedValueOnce(networkErr);

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

  it('treats a non-axios probe failure as single-user mode (fail-closed)', async () => {
    const me = vi.spyOn(authApi, 'me').mockRejectedValueOnce(new Error('boom'));

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

  it('restores a valid session and enables multi-user mode', async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, 'good-token');
    const me = vi.spyOn(authApi, 'me').mockResolvedValueOnce({
      data: { id: 'u1', email: 'user@example.com' },
    } as never);

    render(
      <AuthProvider>
        <AuthState />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth-state').textContent).toBe(
        'multi-user:user@example.com',
      );
    });
    expect(me).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe('good-token');
  });

  it('keeps multi-user mode enabled after logout so RequireAuth still gates', async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, 'good-token');
    vi.spyOn(authApi, 'me').mockResolvedValueOnce({
      data: { id: 'u1', email: 'user@example.com' },
    } as never);

    function LogoutProbe() {
      const { loading, multiUserEnabled, user, logout } = useAuth();
      return (
        <div>
          <span data-testid="auth-state">
            {loading
              ? 'loading'
              : `${multiUserEnabled ? 'multi-user' : 'single-user'}:${user?.email ?? 'anonymous'}`}
          </span>
          <button type="button" onClick={() => logout()}>
            logout
          </button>
        </div>
      );
    }

    render(
      <AuthProvider>
        <LogoutProbe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth-state').textContent).toBe(
        'multi-user:user@example.com',
      );
    });

    fireEvent.click(screen.getByRole('button', { name: 'logout' }));

    expect(screen.getByTestId('auth-state').textContent).toBe('multi-user:anonymous');
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
  });

  it('login enables multi-user mode and stores the session user', async () => {
    vi.spyOn(authApi, 'me').mockRejectedValueOnce(axiosStatus(501));
    const login = vi.spyOn(authApi, 'login').mockResolvedValueOnce({
      data: {
        access_token: 'new-token',
        user: { id: 'u2', email: 'new@example.com' },
      },
    } as never);

    function LoginProbe() {
      const { loading, multiUserEnabled, user, login: doLogin } = useAuth();
      return (
        <div>
          <span data-testid="auth-state">
            {loading
              ? 'loading'
              : `${multiUserEnabled ? 'multi-user' : 'single-user'}:${user?.email ?? 'anonymous'}`}
          </span>
          <button
            type="button"
            onClick={() => {
              void doLogin('new@example.com', 'secret');
            }}
          >
            login
          </button>
        </div>
      );
    }

    render(
      <AuthProvider>
        <LoginProbe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth-state').textContent).toBe('single-user:anonymous');
    });

    fireEvent.click(screen.getByRole('button', { name: 'login' }));

    await waitFor(() => {
      expect(screen.getByTestId('auth-state').textContent).toBe('multi-user:new@example.com');
    });
    expect(login).toHaveBeenCalledWith({ email: 'new@example.com', password: 'secret' });
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe('new-token');
  });
});
