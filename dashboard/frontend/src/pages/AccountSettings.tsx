import React, { useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router';
import { fieldClass } from '../components/alerts/alertsUtils';
import { useAuth } from '../contexts/AuthContext';
import { authApi } from '../services/api';
import { MAX_PASSWORD_LENGTH } from './SignIn';

function detail(error: unknown): string {
  const value = axios.isAxiosError(error)
    ? (error.response?.data as { detail?: unknown } | undefined)?.detail
    : undefined;
  return typeof value === 'string' ? value : 'Request failed. Please try again.';
}

const AccountSettings: React.FC = () => {
  const { user, clearSession } = useAuth();
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [deletePassword, setDeletePassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const finish = () => {
    clearSession();
    navigate('/sign-in', { replace: true });
  };

  const changePassword = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError(''); setMessage('');
    try {
      const response = await authApi.changePassword(currentPassword, newPassword);
      setMessage(response.data.message);
      finish();
    } catch (err) { setError(detail(err)); } finally { setBusy(false); }
  };

  const deleteAccount = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError(''); setMessage('');
    try {
      const response = await authApi.deleteAccount(deletePassword, confirmation);
      setMessage(response.data.message);
      finish();
    } catch (err) { setError(detail(err)); } finally { setBusy(false); }
  };

  return <main className="alerts-page mx-auto max-w-2xl px-4 py-10 sm:px-6">
    <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-50">Account</h1>
    <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">Signed in as {user?.email}</p>
    {error && <p role="alert" className="mt-4 text-sm text-red-700">{error}</p>}
    {message && <p role="status" className="mt-4 text-sm text-emerald-700">{message}</p>}

    <section className="alerts-card mt-6 p-6">
      <h2 className="text-lg font-semibold">Change password</h2>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">This signs out every active device.</p>
      <form className="mt-4 space-y-3" onSubmit={(event) => void changePassword(event)}>
        <input aria-label="Current password" type="password" required maxLength={MAX_PASSWORD_LENGTH} value={currentPassword} onChange={e => setCurrentPassword(e.target.value)} className={fieldClass} />
        <input aria-label="New password" type="password" required minLength={8} maxLength={MAX_PASSWORD_LENGTH} value={newPassword} onChange={e => setNewPassword(e.target.value)} className={fieldClass} />
        <button disabled={busy} className="alerts-cta">Change password</button>
      </form>
    </section>

    <section className="alerts-card mt-6 border-red-300 p-6">
      <h2 className="text-lg font-semibold text-red-700">Delete account</h2>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">Permanently deletes your account, watches, settings, and delivery history.</p>
      <form className="mt-4 space-y-3" onSubmit={(event) => void deleteAccount(event)}>
        <input aria-label="Password for deletion" type="password" required maxLength={MAX_PASSWORD_LENGTH} value={deletePassword} onChange={e => setDeletePassword(e.target.value)} className={fieldClass} />
        <input aria-label="Type DELETE to confirm" required value={confirmation} onChange={e => setConfirmation(e.target.value)} className={fieldClass} />
        <button disabled={busy || confirmation !== 'DELETE'} className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Delete account permanently</button>
      </form>
    </section>
  </main>;
};

export default AccountSettings;
