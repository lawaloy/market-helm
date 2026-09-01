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

  it('treats a 500 /me probe as multi-user mode so RequireAuth stays gated', async () => {
    const me = vi.spyOn(authApi, 'me').mockRejectedValueOnce(axiosStatus(500));

    render(
      <AuthProvider>
        <AuthState />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth-state').textContent).toBe('multi-user:anonymous');
    });
    expect(me).toHaveBeenCalledTimes(1);
  });

  it('treats a 503 /me probe as multi-user mode so RequireAuth stays gated', async () => {
    const me = vi.spyOn(authApi, 'me').mockRejectedValueOnce(axiosStatus(503));

    render(
      <AuthProvider>
        <AuthState />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth-state').textContent).toBe('multi-user:anonymous');
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

  it('keeps a stored token when /me returns 500 so a blip does not sign the user out', async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, 'good-token');
    const me = vi.spyOn(authApi, 'me').mockRejectedValueOnce(axiosStatus(500));

    render(
      <AuthProvider>
        <AuthState />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth-state').textContent).toBe('multi-user:anonymous');
    });
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe('good-token');
    expect(me).toHaveBeenCalledTimes(1);
  });

  it('keeps a stored token when /me returns 503 so RequireAuth stays gated', async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, 'good-token');
    const me = vi.spyOn(authApi, 'me').mockRejectedValueOnce(axiosStatus(503));

    render(
      <AuthProvider>
        <AuthState />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth-state').textContent).toBe('multi-user:anonymous');
    });
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe('good-token');
    expect(me).toHaveBeenCalledTimes(1);
  });

  it('keeps a stored token on network /me failure while staying in hosted mode', async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, 'good-token');
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
      expect(screen.getByTestId('auth-state').textContent).toBe('multi-user:anonymous');
    });
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe('good-token');
    expect(me).toHaveBeenCalledTimes(1);
  });

  it('clears a stored token on 403 and probes hosted mode', async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, 'forbidden-token');
    const me = vi
      .spyOn(authApi, 'me')
      .mockRejectedValueOnce(axiosStatus(403))
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

  it('drops a stored token on 501 and leaves single-user mode', async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, 'stale-token');
    const me = vi.spyOn(authApi, 'me').mockRejectedValueOnce(axiosStatus(501));

    render(
      <AuthProvider>
        <AuthState />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth-state').textContent).toBe('single-user:anonymous');
    });
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
    expect(me).toHaveBeenCalledTimes(1);
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
    const logout = vi.spyOn(authApi, 'logout').mockResolvedValueOnce({
      data: { message: 'Signed out from all sessions.' },
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

    await waitFor(() => {
      expect(screen.getByTestId('auth-state').textContent).toBe('multi-user:anonymous');
    });
    expect(logout).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
  });

  it('preserves the active session when server-side logout fails', async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, 'good-token');
    vi.spyOn(authApi, 'me').mockResolvedValueOnce({
      data: { id: 'u1', email: 'user@example.com' },
    } as never);
    vi.spyOn(authApi, 'logout').mockRejectedValueOnce(axiosStatus(503));

    function LogoutProbe() {
      const { loading, user, logout } = useAuth();
      return <button type="button" disabled={loading} onClick={() => void logout().catch(() => undefined)}>
        {user?.email ?? 'anonymous'}
      </button>;
    }

    render(<AuthProvider><LogoutProbe /></AuthProvider>);
    await waitFor(() => expect(screen.getByRole('button').textContent).toBe('user@example.com'));
    fireEvent.click(screen.getByRole('button'));
    await waitFor(() => expect(authApi.logout).toHaveBeenCalledTimes(1));
    expect(screen.getByRole('button').textContent).toBe('user@example.com');
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe('good-token');
  });

  it('clearSession drops the token and user while keeping hosted mode gated', async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, 'revoked-token');
    vi.spyOn(authApi, 'me').mockResolvedValueOnce({
      data: { id: 'u1', email: 'user@example.com' },
    } as never);

    function ClearSessionProbe() {
      const { loading, multiUserEnabled, user, clearSession } = useAuth();
      return (
        <div>
          <span data-testid="auth-state">
            {loading
              ? 'loading'
              : `${multiUserEnabled ? 'multi-user' : 'single-user'}:${user?.email ?? 'anonymous'}`}
          </span>
          <button type="button" onClick={() => clearSession()}>
            clear-session
          </button>
        </div>
      );
    }

    render(
      <AuthProvider>
        <ClearSessionProbe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth-state').textContent).toBe(
        'multi-user:user@example.com',
      );
    });

    fireEvent.click(screen.getByRole('button', { name: 'clear-session' }));

    expect(screen.getByTestId('auth-state').textContent).toBe('multi-user:anonymous');
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
  });

  it('clears a revoked session locally when logout returns 401', async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, 'revoked-token');
    vi.spyOn(authApi, 'me').mockResolvedValueOnce({
      data: { id: 'u1', email: 'user@example.com' },
    } as never);
    vi.spyOn(authApi, 'logout').mockRejectedValueOnce(axiosStatus(401));

    function LogoutProbe() {
      const { loading, multiUserEnabled, user, logout } = useAuth();
      return (
        <div>
          <span data-testid="auth-state">
            {loading
              ? 'loading'
              : `${multiUserEnabled ? 'multi-user' : 'single-user'}:${user?.email ?? 'anonymous'}`}
          </span>
          <button type="button" onClick={() => void logout()}>
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

    await waitFor(() => {
      expect(screen.getByTestId('auth-state').textContent).toBe('multi-user:anonymous');
    });
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
  });

  it('preserves the active session when logout returns 403', async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, 'unverified-token');
    vi.spyOn(authApi, 'me').mockResolvedValueOnce({
      data: { id: 'u1', email: 'user@example.com' },
    } as never);
    vi.spyOn(authApi, 'logout').mockRejectedValueOnce(axiosStatus(403));

    function LogoutProbe() {
      const { loading, user, logout } = useAuth();
      return (
        <button
          type="button"
          disabled={loading}
          onClick={() => void logout().catch(() => undefined)}
        >
          {user?.email ?? 'anonymous'}
        </button>
      );
    }

    render(
      <AuthProvider>
        <LogoutProbe />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByRole('button').textContent).toBe('user@example.com'));
    fireEvent.click(screen.getByRole('button'));
    await waitFor(() => expect(authApi.logout).toHaveBeenCalledTimes(1));
    expect(screen.getByRole('button').textContent).toBe('user@example.com');
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe('unverified-token');
  });

  it('preserves the active session when logout is rate-limited with 429', async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, 'good-token');
    vi.spyOn(authApi, 'me').mockResolvedValueOnce({
      data: { id: 'u1', email: 'user@example.com' },
    } as never);
    vi.spyOn(authApi, 'logout').mockRejectedValueOnce(axiosStatus(429));

    function LogoutProbe() {
      const { loading, user, logout } = useAuth();
      return (
        <button
          type="button"
          disabled={loading}
          onClick={() => void logout().catch(() => undefined)}
        >
          {user?.email ?? 'anonymous'}
        </button>
      );
    }

    render(
      <AuthProvider>
        <LogoutProbe />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByRole('button').textContent).toBe('user@example.com'));
    fireEvent.click(screen.getByRole('button'));
    await waitFor(() => expect(authApi.logout).toHaveBeenCalledTimes(1));
    expect(screen.getByRole('button').textContent).toBe('user@example.com');
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe('good-token');
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

  it('does not store a token when login is rejected', async () => {
    vi.spyOn(authApi, 'me').mockRejectedValueOnce(axiosStatus(401));
    const login = vi.spyOn(authApi, 'login').mockRejectedValueOnce(axiosStatus(401));

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
              void doLogin('new@example.com', 'secret').catch(() => undefined);
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
      expect(screen.getByTestId('auth-state').textContent).toBe('multi-user:anonymous');
    });

    fireEvent.click(screen.getByRole('button', { name: 'login' }));

    await waitFor(() => expect(login).toHaveBeenCalledTimes(1));
    expect(screen.getByTestId('auth-state').textContent).toBe('multi-user:anonymous');
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
  });

  it('register enables multi-user mode and stores the session user', async () => {
    vi.spyOn(authApi, 'me').mockRejectedValueOnce(axiosStatus(501));
    const register = vi.spyOn(authApi, 'register').mockResolvedValueOnce({
      data: {
        access_token: 'reg-token',
        user: { id: 'u3', email: 'reg@example.com' },
      },
    } as never);

    function RegisterProbe() {
      const { loading, multiUserEnabled, user, register: doRegister } = useAuth();
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
              void doRegister('reg@example.com', 'secret');
            }}
          >
            register
          </button>
        </div>
      );
    }

    render(
      <AuthProvider>
        <RegisterProbe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth-state').textContent).toBe('single-user:anonymous');
    });

    fireEvent.click(screen.getByRole('button', { name: 'register' }));

    await waitFor(() => {
      expect(screen.getByTestId('auth-state').textContent).toBe('multi-user:reg@example.com');
    });
    expect(register).toHaveBeenCalledWith({
      email: 'reg@example.com',
      password: 'secret',
    });
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe('reg-token');
  });

  it('does not store a token when register is rejected', async () => {
    vi.spyOn(authApi, 'me').mockRejectedValueOnce(axiosStatus(401));
    const register = vi.spyOn(authApi, 'register').mockRejectedValueOnce(axiosStatus(400));

    function RegisterProbe() {
      const { loading, multiUserEnabled, user, register: doRegister } = useAuth();
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
              void doRegister('reg@example.com', 'secret').catch(() => undefined);
            }}
          >
            register
          </button>
        </div>
      );
    }

    render(
      <AuthProvider>
        <RegisterProbe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth-state').textContent).toBe('multi-user:anonymous');
    });

    fireEvent.click(screen.getByRole('button', { name: 'register' }));

    await waitFor(() => expect(register).toHaveBeenCalledTimes(1));
    expect(screen.getByTestId('auth-state').textContent).toBe('multi-user:anonymous');
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
  });
});
