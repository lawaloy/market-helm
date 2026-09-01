import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SignIn, { MAX_PASSWORD_LENGTH } from './SignIn';

const authMocks = vi.hoisted(() => ({
  login: vi.fn(),
  register: vi.fn(),
  useAuthImpl: vi.fn(() => ({
    login: authMocks.login,
    register: authMocks.register,
    multiUserEnabled: true,
    loading: false,
  })),
}));

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => authMocks.useAuthImpl(),
}));

describe('SignIn', () => {
  beforeEach(() => {
    authMocks.useAuthImpl.mockReturnValue({
      login: authMocks.login,
      register: authMocks.register,
      multiUserEnabled: true,
      loading: false,
    });
    authMocks.login.mockResolvedValue(undefined);
    authMocks.register.mockResolvedValue(undefined);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('submits sign-in credentials', async () => {
    render(
      <MemoryRouter initialEntries={['/sign-in?return=%2Falerts']}>
        <SignIn />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'password123' } });
    fireEvent.submit(screen.getByRole('form', { name: 'Authentication form' }));

    await waitFor(() => {
      expect(authMocks.login).toHaveBeenCalledWith('user@example.com', 'password123');
    });
  });

  it('shows single-user message when auth is disabled', () => {
    authMocks.useAuthImpl.mockReturnValue({
      login: authMocks.login,
      register: authMocks.register,
      multiUserEnabled: false,
      loading: false,
    });

    render(
      <MemoryRouter>
        <SignIn />
      </MemoryRouter>,
    );

    expect(screen.getByText('Sign-in not required')).toBeTruthy();
  });

  it('does not offer the single-user Helmtower bypass while the session probe is loading', () => {
    // AuthProvider starts at loading=true and multiUserEnabled=false. Without the
    // loading gate, SignIn would flash "Sign-in not required" and a Helmtower
    // link during the hosted /me probe.
    authMocks.useAuthImpl.mockReturnValue({
      login: authMocks.login,
      register: authMocks.register,
      multiUserEnabled: false,
      loading: true,
    });

    render(
      <MemoryRouter initialEntries={['/sign-in?return=%2Falerts']}>
        <SignIn />
      </MemoryRouter>,
    );

    expect(screen.queryByText('Sign-in not required')).toBeNull();
    expect(screen.queryByRole('link', { name: 'Go to Helmtower' })).toBeNull();
    expect(screen.queryByRole('form', { name: 'Authentication form' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Sign in' })).toBeNull();
    expect(document.querySelector('.animate-pulse')).toBeTruthy();
  });

  it('caps password input length to match backend MAX_PASSWORD_LENGTH', () => {
    render(
      <MemoryRouter>
        <SignIn />
      </MemoryRouter>,
    );

    const password = screen.getByLabelText('Password');
    expect(password.getAttribute('maxLength')).toBe(String(MAX_PASSWORD_LENGTH));
    expect(MAX_PASSWORD_LENGTH).toBe(128);
  });
});

