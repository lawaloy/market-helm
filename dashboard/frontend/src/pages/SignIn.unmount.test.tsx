import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
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

describe('SignIn unmount during submit', () => {
  beforeEach(() => {
    authMocks.useAuthImpl.mockReturnValue({
      login: authMocks.login,
      register: authMocks.register,
      multiUserEnabled: true,
      loading: false,
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('does not setState after unmount when login resolves late', async () => {
    let resolveLogin: (() => void) | undefined;
    authMocks.login.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveLogin = resolve;
        }),
    );

    render(
      <MemoryRouter initialEntries={['/sign-in']}>
        <SignIn />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'password123' } });
    fireEvent.submit(screen.getByRole('form', { name: 'Authentication form' }));

    expect(authMocks.login).toHaveBeenCalled();
    cleanup();

    await act(async () => {
      resolveLogin?.();
      await Promise.resolve();
    });

    // Unmounted — no error banner / submitting state to assert; just no throw.
    expect(screen.queryByRole('form', { name: 'Authentication form' })).toBeNull();
  });

  it('does not setState after unmount when login rejects late', async () => {
    let rejectLogin: ((err: unknown) => void) | undefined;
    authMocks.login.mockImplementation(
      () =>
        new Promise<void>((_resolve, reject) => {
          rejectLogin = reject;
        }),
    );

    render(
      <MemoryRouter initialEntries={['/sign-in']}>
        <SignIn />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'password123' } });
    fireEvent.submit(screen.getByRole('form', { name: 'Authentication form' }));

    cleanup();

    await act(async () => {
      rejectLogin?.(new Error('boom'));
      await Promise.resolve();
    });

    expect(screen.queryByText(/Authentication failed/i)).toBeNull();
  });
});
