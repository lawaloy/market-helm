import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import AccountRecovery from './AccountRecovery';
import { authApi } from '../services/api';
import { MAX_PASSWORD_LENGTH } from './SignIn';

describe('AccountRecovery', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('requests a password reset for the trimmed email', async () => {
    const request = vi.spyOn(authApi, 'requestPasswordReset').mockResolvedValueOnce({
      data: { message: 'If the account exists, a password reset email has been sent.' },
    } as never);
    render(
      <MemoryRouter>
        <AccountRecovery mode="forgot" />
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: '  user@example.com  ' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    await waitFor(() => expect(request).toHaveBeenCalledWith('user@example.com'));
    expect(screen.getByText('If the account exists, a password reset email has been sent.')).toBeTruthy();
  });

  it('disables reset and verify continue without a token', () => {
    const { rerender } = render(
      <MemoryRouter>
        <AccountRecovery mode="reset" />
      </MemoryRouter>,
    );
    expect((screen.getByRole('button', { name: 'Continue' }) as HTMLButtonElement).disabled).toBe(true);

    rerender(
      <MemoryRouter>
        <AccountRecovery mode="verify" />
      </MemoryRouter>,
    );
    expect((screen.getByRole('button', { name: 'Continue' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('confirms a password reset from the token query param', async () => {
    const confirm = vi.spyOn(authApi, 'confirmPasswordReset').mockResolvedValueOnce({
      data: { message: 'Password updated. You can now sign in.' },
    } as never);
    render(
      <MemoryRouter initialEntries={['/reset-password?token=reset-token-value']}>
        <AccountRecovery mode="reset" />
      </MemoryRouter>,
    );
    const password = screen.getByLabelText('New password');
    expect(password.getAttribute('maxLength')).toBe(String(MAX_PASSWORD_LENGTH));
    fireEvent.change(password, { target: { value: 'new-password-123' } });
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    await waitFor(() => expect(confirm).toHaveBeenCalledWith('reset-token-value', 'new-password-123'));
  });

  it('surfaces a generic error when the forgot-password request fails', async () => {
    vi.spyOn(authApi, 'requestPasswordReset').mockRejectedValueOnce(new Error('mail down'));
    render(
      <MemoryRouter>
        <AccountRecovery mode="forgot" />
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: 'user@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    await waitFor(() => {
      expect(
        screen.getByText('This request could not be completed. The link may be invalid or expired.'),
      ).toBeTruthy();
    });
  });

  it('confirms email verification and surfaces expired-link errors', async () => {
    const confirm = vi.spyOn(authApi, 'confirmEmailVerification').mockRejectedValueOnce(
      new Error('expired'),
    );
    render(
      <MemoryRouter initialEntries={['/verify-email?token=verify-token-value']}>
        <AccountRecovery mode="verify" />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    await waitFor(() => expect(confirm).toHaveBeenCalledWith('verify-token-value'));
    expect(
      screen.getByText('This request could not be completed. The link may be invalid or expired.'),
    ).toBeTruthy();
  });

  it('hides Continue after a successful email verification', async () => {
    const confirm = vi.spyOn(authApi, 'confirmEmailVerification').mockResolvedValueOnce({
      data: { message: 'Email verified. You can now sign in.' },
    } as never);
    render(
      <MemoryRouter initialEntries={['/verify-email?token=verify-token-value']}>
        <AccountRecovery mode="verify" />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    await waitFor(() => expect(confirm).toHaveBeenCalledWith('verify-token-value'));
    expect(screen.getByText('Email verified. You can now sign in.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Continue' })).toBeNull();
  });
});
