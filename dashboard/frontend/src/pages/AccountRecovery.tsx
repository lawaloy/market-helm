import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { fieldClass } from '../components/alerts/alertsUtils';
import { authApi } from '../services/api';
import { MAX_PASSWORD_LENGTH } from './SignIn';

type Props = { mode: 'forgot' | 'reset' | 'verify' };

const AccountRecovery: React.FC<Props> = ({ mode }) => {
  const [params] = useSearchParams();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const token = params.get('token') || '';

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true); setError(null);
    try {
      const response = mode === 'forgot'
        ? await authApi.requestPasswordReset(email.trim())
        : mode === 'reset'
          ? await authApi.confirmPasswordReset(token, password)
          : await authApi.confirmEmailVerification(token);
      setMessage(response.data.message);
    } catch {
      setError('This request could not be completed. The link may be invalid or expired.');
    } finally { setBusy(false); }
  };

  const title = mode === 'forgot' ? 'Reset your password' : mode === 'reset' ? 'Choose a new password' : 'Verify your email';
  return <div className="alerts-page mx-auto max-w-md px-4 py-12 sm:px-6"><div className="alerts-card p-8">
    <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-50">{title}</h1>
    <form className="mt-6 space-y-4" onSubmit={(event) => void submit(event)}>
      {mode === 'forgot' && <input aria-label="Email" type="email" required value={email} onChange={e => setEmail(e.target.value)} className={fieldClass} />}
      {mode === 'reset' && <input aria-label="New password" type="password" required minLength={8} maxLength={MAX_PASSWORD_LENGTH} value={password} onChange={e => setPassword(e.target.value)} className={fieldClass} />}
      {message && <p className="text-sm text-emerald-700">{message}</p>}
      {error && <p className="text-sm text-red-700">{error}</p>}
      {!message && <button className="alerts-cta w-full" disabled={busy || (mode !== 'forgot' && !token)}>{busy ? 'Please wait…' : 'Continue'}</button>}
    </form>
    <Link to="/sign-in" className="mt-5 block text-center text-sm text-teal-600 hover:underline">Back to sign in</Link>
  </div></div>;
};

export default AccountRecovery;
