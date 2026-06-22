import React, { useState } from 'react';
import axios from 'axios';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { fieldClass } from '../components/alerts/alertsUtils';
import { useAuth } from '../contexts/AuthContext';

type AuthMode = 'sign-in' | 'sign-up';

const SignIn: React.FC = () => {
  const { login, register, multiUserEnabled, loading } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [mode, setMode] = useState<AuthMode>('sign-in');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const returnTo = searchParams.get('return') || '/alerts';

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      if (mode === 'sign-in') {
        await login(email.trim(), password);
      } else {
        await register(email.trim(), password);
      }
      navigate(returnTo, { replace: true });
    } catch (err) {
      const detail =
        axios.isAxiosError(err) &&
        (err.response?.data as { detail?: string } | undefined)?.detail;
      setError(typeof detail === 'string' ? detail : 'Authentication failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="alerts-page mx-auto max-w-md px-4 py-16 sm:px-6">
        <div className="h-8 w-40 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-700" />
      </div>
    );
  }

  if (!multiUserEnabled) {
    return (
      <div className="alerts-page mx-auto max-w-md px-4 py-16 sm:px-6">
        <div className="alerts-card p-8 text-center">
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
            Sign-in not required
          </h1>
          <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
            This server runs in single-user mode. Helmtower uses the local alerts config without an
            account.
          </p>
          <Link to="/alerts" className="alerts-cta mt-6 inline-flex">
            Go to Helmtower
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="alerts-page mx-auto max-w-md px-4 py-12 sm:px-6">
      <div className="alerts-card p-8">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-600 dark:text-teal-400">
          Helmtower
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-50">
          {mode === 'sign-in' ? 'Sign in' : 'Create account'}
        </h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
          {mode === 'sign-in'
            ? 'Access your private watches and delivery settings.'
            : 'Register to save watches on this hosted MarketHelm instance.'}
        </p>

        <div className="mt-6 flex rounded-xl bg-slate-100 p-1 dark:bg-slate-800">
          <button
            type="button"
            onClick={() => {
              setMode('sign-in');
              setError(null);
            }}
            className={`flex-1 rounded-lg px-3 py-2 text-sm font-medium transition ${
              mode === 'sign-in'
                ? 'bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-slate-100'
                : 'text-slate-600 dark:text-slate-400'
            }`}
          >
            Sign in
          </button>
          <button
            type="button"
            onClick={() => {
              setMode('sign-up');
              setError(null);
            }}
            className={`flex-1 rounded-lg px-3 py-2 text-sm font-medium transition ${
              mode === 'sign-up'
                ? 'bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-slate-100'
                : 'text-slate-600 dark:text-slate-400'
            }`}
          >
            Sign up
          </button>
        </div>

        <form className="mt-6 space-y-4" aria-label="Authentication form" onSubmit={(event) => void handleSubmit(event)}>
          <div>
            <label htmlFor="auth-email" className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
              Email
            </label>
            <input
              id="auth-email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={fieldClass}
            />
          </div>
          <div>
            <label
              htmlFor="auth-password"
              className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300"
            >
              Password
            </label>
            <input
              id="auth-password"
              type="password"
              autoComplete={mode === 'sign-in' ? 'current-password' : 'new-password'}
              required
              minLength={8}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className={fieldClass}
            />
            {mode === 'sign-up' && (
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                At least 8 characters.
              </p>
            )}
          </div>

          {error && (
            <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-300">
              {error}
            </p>
          )}

          <button type="submit" disabled={submitting} className="alerts-cta w-full">
            {submitting ? 'Please wait…' : mode === 'sign-in' ? 'Sign in' : 'Create account'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default SignIn;
