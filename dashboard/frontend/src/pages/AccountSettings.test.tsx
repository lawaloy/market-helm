import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import AccountSettings from './AccountSettings';
import { authApi } from '../services/api';

const mocks = vi.hoisted(() => ({ clearSession: vi.fn(), navigate: vi.fn() }));

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ user: { id: 'u1', email: 'user@example.com' }, clearSession: mocks.clearSession }),
}));
vi.mock('react-router', async () => {
  const actual = await vi.importActual<typeof import('react-router')>('react-router');
  return { ...actual, useNavigate: () => mocks.navigate };
});

function axiosDetail(detail: unknown) {
  return {
    isAxiosError: true,
    response: { data: { detail } },
  };
}

describe('AccountSettings', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    mocks.clearSession.mockClear();
    mocks.navigate.mockClear();
  });

  it('changes password, clears the revoked session, and returns to sign in', async () => {
    const change = vi.spyOn(authApi, 'changePassword').mockResolvedValueOnce({
      data: { message: 'Password changed.' },
    } as never);
    render(<MemoryRouter><AccountSettings /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText('Current password'), { target: { value: 'password123' } });
    fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'new-password-123' } });
    fireEvent.click(screen.getByRole('button', { name: 'Change password' }));
    await waitFor(() => expect(change).toHaveBeenCalledWith('password123', 'new-password-123'));
    expect(mocks.clearSession).toHaveBeenCalled();
    expect(mocks.navigate).toHaveBeenCalledWith('/sign-in', { replace: true });
  });

  it('requires exact DELETE confirmation before account deletion', async () => {
    const remove = vi.spyOn(authApi, 'deleteAccount').mockResolvedValueOnce({
      data: { message: 'Account permanently deleted.' },
    } as never);
    render(<MemoryRouter><AccountSettings /></MemoryRouter>);
    const button = screen.getByRole('button', { name: 'Delete account permanently' }) as HTMLButtonElement;
    fireEvent.change(screen.getByLabelText('Password for deletion'), { target: { value: 'password123' } });
    fireEvent.change(screen.getByLabelText('Type DELETE to confirm'), { target: { value: 'delete' } });
    expect(button.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Type DELETE to confirm'), { target: { value: 'DELETE' } });
    expect(button.disabled).toBe(false);
    fireEvent.click(button);
    await waitFor(() => expect(remove).toHaveBeenCalledWith('password123', 'DELETE'));
    expect(mocks.clearSession).toHaveBeenCalled();
  });

  it('surfaces password-change API errors without signing the user out', async () => {
    vi.spyOn(authApi, 'changePassword').mockRejectedValueOnce(
      axiosDetail('Current password is incorrect.'),
    );
    render(<MemoryRouter><AccountSettings /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText('Current password'), { target: { value: 'wrong-password' } });
    fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'new-password-123' } });
    fireEvent.click(screen.getByRole('button', { name: 'Change password' }));
    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toBe('Current password is incorrect.');
    });
    expect(mocks.clearSession).not.toHaveBeenCalled();
    expect(mocks.navigate).not.toHaveBeenCalled();
  });

  it('keeps the session when account deletion fails', async () => {
    vi.spyOn(authApi, 'deleteAccount').mockRejectedValueOnce(
      axiosDetail('Current password is incorrect.'),
    );
    render(<MemoryRouter><AccountSettings /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText('Password for deletion'), { target: { value: 'wrong-password' } });
    fireEvent.change(screen.getByLabelText('Type DELETE to confirm'), { target: { value: 'DELETE' } });
    fireEvent.click(screen.getByRole('button', { name: 'Delete account permanently' }));
    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toBe('Current password is incorrect.');
    });
    expect(mocks.clearSession).not.toHaveBeenCalled();
    expect(mocks.navigate).not.toHaveBeenCalled();
  });

  it('falls back to a generic error for non-Axios failures without navigating', async () => {
    vi.spyOn(authApi, 'changePassword').mockRejectedValueOnce(new Error('network down'));
    render(<MemoryRouter><AccountSettings /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText('Current password'), { target: { value: 'password123' } });
    fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'new-password-123' } });
    fireEvent.click(screen.getByRole('button', { name: 'Change password' }));
    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toBe('Request failed. Please try again.');
    });
    expect(mocks.clearSession).not.toHaveBeenCalled();
    expect(mocks.navigate).not.toHaveBeenCalled();
  });
});
