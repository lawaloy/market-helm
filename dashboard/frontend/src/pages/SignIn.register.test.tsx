import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router';
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

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname + location.search}</span>;
}

describe('SignIn registration and recovery entry', () => {
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

  it('links forgot-password from sign-in and hides it on sign-up', () => {
    render(
      <MemoryRouter initialEntries={['/sign-in']}>
        <SignIn />
      </MemoryRouter>,
    );

    expect(screen.getByRole('link', { name: 'Forgot your password?' }).getAttribute('href')).toBe(
      '/forgot-password',
    );

    fireEvent.click(screen.getByRole('button', { name: 'Sign up' }));
    expect(screen.queryByRole('link', { name: 'Forgot your password?' })).toBeNull();
  });

  it('stays on sign-in and shows API detail when registration fails', async () => {
    authMocks.register.mockRejectedValueOnce({
      isAxiosError: true,
      response: { data: { detail: 'An account with this email already exists.' } },
    });
    render(
      <MemoryRouter initialEntries={['/sign-in?return=%2Falerts']}>
        <SignIn />
        <LocationProbe />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Sign up' }));
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'password123' } });
    fireEvent.submit(screen.getByRole('form', { name: 'Authentication form' }));

    await waitFor(() => {
      expect(screen.getByText('An account with this email already exists.')).toBeTruthy();
    });
    expect(authMocks.register).toHaveBeenCalledWith('user@example.com', 'password123');
    expect(authMocks.login).not.toHaveBeenCalled();
    expect(screen.getByTestId('location').textContent).toBe('/sign-in?return=%2Falerts');
  });
});
