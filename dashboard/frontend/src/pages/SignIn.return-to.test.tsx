import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SignIn, { safeReturnPath } from './SignIn';

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

describe('safeReturnPath', () => {
  it('allows same-app relative paths', () => {
    expect(safeReturnPath('/alerts')).toBe('/alerts');
    expect(safeReturnPath('/alerts?symbol=AAPL')).toBe('/alerts?symbol=AAPL');
  });

  it('rejects open redirects', () => {
    expect(safeReturnPath('https://evil.example/phish')).toBe('/alerts');
    expect(safeReturnPath('//evil.example/phish')).toBe('/alerts');
    expect(safeReturnPath('\\\\evil.example')).toBe('/alerts');
    expect(safeReturnPath('/\\evil.example')).toBe('/alerts');
    expect(safeReturnPath('/alerts/..\\evil')).toBe('/alerts');
    expect(safeReturnPath(null)).toBe('/alerts');
    expect(safeReturnPath('')).toBe('/alerts');
  });
});

describe('SignIn return navigation', () => {
  beforeEach(() => {
    authMocks.useAuthImpl.mockReturnValue({
      login: authMocks.login,
      register: authMocks.register,
      multiUserEnabled: true,
      loading: false,
    });
    authMocks.login.mockResolvedValue(undefined);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('navigates to a safe same-app return path after sign-in', async () => {
    render(
      <MemoryRouter initialEntries={['/sign-in?return=%2Falerts%3Fsymbol%3DAAPL']}>
        <SignIn />
        <LocationProbe />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'password123' } });
    fireEvent.submit(screen.getByRole('form', { name: 'Authentication form' }));

    await waitFor(() => {
      expect(screen.getByTestId('location').textContent).toBe('/alerts?symbol=AAPL');
    });
  });

  it('falls back to /alerts when return is an open redirect', async () => {
    render(
      <MemoryRouter initialEntries={['/sign-in?return=https%3A%2F%2Fevil.example%2Fx']}>
        <SignIn />
        <LocationProbe />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'password123' } });
    fireEvent.submit(screen.getByRole('form', { name: 'Authentication form' }));

    await waitFor(() => {
      expect(screen.getByTestId('location').textContent).toBe('/alerts');
    });
  });

  it('falls back to /alerts for protocol-relative return values', async () => {
    render(
      <MemoryRouter initialEntries={['/sign-in?return=%2F%2Fevil.example%2Fx']}>
        <SignIn />
        <LocationProbe />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'password123' } });
    fireEvent.submit(screen.getByRole('form', { name: 'Authentication form' }));

    await waitFor(() => {
      expect(screen.getByTestId('location').textContent).toBe('/alerts');
    });
  });
});
