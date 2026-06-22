import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SignIn from './SignIn';

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
});
