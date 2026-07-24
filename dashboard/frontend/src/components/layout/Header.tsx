import React, { useRef, useState } from 'react';
import { Link } from 'react-router';
import { ArrowPathIcon, SunIcon, MoonIcon } from '@heroicons/react/24/outline';
import { useTheme } from '../../contexts/ThemeContext';
import { useAuth } from '../../contexts/AuthContext';
import api from '../../services/api';

interface HeaderProps {
  dataDate?: string;
  onRefreshComplete?: () => void;
  onQuickRefresh?: () => void;
  /** True when app is fetching latest data in background (no user action) */
  backgroundFetching?: boolean;
}

const Header: React.FC<HeaderProps> = ({ dataDate, onRefreshComplete, onQuickRefresh, backgroundFetching }) => {
  const { theme, toggleTheme } = useTheme();
  const { user, multiUserEnabled, logout } = useAuth();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState('');
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastMessageRef = useRef<string>('');

  const updateMessage = (message: string) => {
    if (lastMessageRef.current === message) return;
    lastMessageRef.current = message;
    setRefreshMessage(message);
  };

  const handleQuickRefresh = () => {
    updateMessage('Reloading data...');
    onQuickRefresh?.();
    setTimeout(() => {
      if (!isRefreshing) {
        updateMessage('');
      }
    }, 1000);
  };

  const handleFullRefresh = async () => {
    setIsRefreshing(true);
    updateMessage('Reloading latest saved data...');
    onQuickRefresh?.();

    try {
      // Trigger refresh
      const response = await api.post('/api/refresh');
      updateMessage(response.data.message);

      const pollMs = 2000;
      const maxWaitMs = 15 * 60 * 1000;
      const pollStarted = Date.now();

      const finishPolling = () => {
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
      };

      // Poll for status
      pollIntervalRef.current = setInterval(async () => {
        try {
          if (Date.now() - pollStarted > maxWaitMs) {
            finishPolling();
            setIsRefreshing(false);
            updateMessage('Refresh is taking too long. Check server logs or try Cancel.');
            setTimeout(() => updateMessage(''), 8000);
            return;
          }

          const statusRes = await api.get('/api/refresh/status');
          const status = statusRes.data;

          if (status.progress) {
            updateMessage(status.progress);
          }

          if (!status.is_running) {
            finishPolling();
            setIsRefreshing(false);

            if (status.last_status === 'success') {
              updateMessage('Data refreshed successfully!');
              setTimeout(() => {
                updateMessage('');
                onRefreshComplete?.();
              }, 2000);
            } else if (status.last_status === 'idle') {
              updateMessage('');
            } else {
              updateMessage('Refresh failed. Please try again.');
              setTimeout(() => updateMessage(''), 5000);
            }
          }
        } catch (err) {
          console.error('Status poll error:', err);
        }
      }, pollMs);

    } catch (error) {
      console.error('Refresh error:', error);
      updateMessage('Failed to start refresh');
      setIsRefreshing(false);
      setTimeout(() => updateMessage(''), 5000);
    }
  };

  const handleCancelRefresh = async () => {
    updateMessage('Cancelling refresh...');
    try {
      await api.post('/api/refresh/cancel');
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      setIsRefreshing(false);
      updateMessage('Refresh cancelled.');
      setTimeout(() => updateMessage(''), 3000);
    } catch (error) {
      console.error('Cancel refresh error:', error);
      updateMessage('Failed to cancel refresh.');
      setTimeout(() => updateMessage(''), 5000);
    }
  };

  return (
    <header className="bg-white border-b border-slate-200 dark:bg-slate-800 dark:border-slate-700 sticky top-0 z-10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center space-x-4">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
              📊 MarketHelm
            </h1>
            {dataDate && (
              <div className="text-sm text-slate-600 dark:text-slate-400">
                <span className="font-medium">Data from:</span>{' '}
                <span className="font-semibold">{dataDate}</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2 sm:gap-4 flex-wrap">
            <div
              className={`text-sm text-slate-600 dark:text-slate-400 max-w-xs truncate transition-opacity duration-200 ${
                refreshMessage || backgroundFetching ? 'opacity-100' : 'opacity-0'
              }`}
            >
              {refreshMessage || (backgroundFetching ? 'Updating data...' : 'Status')}
            </div>
            <button
              onClick={handleQuickRefresh}
              className="flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium bg-green-500 text-white hover:bg-green-600 transition-colors"
              title="Reload data from files (instant)"
            >
              <ArrowPathIcon className="h-5 w-5" />
              <span>Reload</span>
            </button>
            <button
              onClick={handleFullRefresh}
              disabled={isRefreshing}
              className={`flex items-center space-x-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                isRefreshing
                  ? 'bg-slate-300 text-slate-600 cursor-not-allowed dark:bg-slate-600 dark:text-slate-400'
                  : 'bg-blue-500 text-white hover:bg-blue-600 dark:bg-blue-600 dark:hover:bg-blue-700'
              }`}
              title="Reload saved data instantly and fetch fresh data in background"
            >
              <ArrowPathIcon className={`h-5 w-5 ${isRefreshing ? 'animate-spin' : ''}`} />
              <span>{isRefreshing ? 'Fetching...' : 'Fetch New'}</span>
            </button>
            {isRefreshing && (
              <button
                onClick={handleCancelRefresh}
                className="flex items-center space-x-2 px-4 py-2 rounded-md text-sm font-medium bg-red-500 text-white hover:bg-red-600 transition-colors"
                title="Cancel the current refresh job"
              >
                <span>Cancel</span>
              </button>
            )}
            <button
              onClick={toggleTheme}
              className="p-2 rounded-md text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700 transition-colors"
              title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
              aria-label="Toggle theme"
            >
              {theme === 'dark' ? (
                <SunIcon className="h-5 w-5" />
              ) : (
                <MoonIcon className="h-5 w-5" />
              )}
            </button>
            {multiUserEnabled && (
              user ? (
                <div className="flex items-center gap-2">
                  <span
                    className="hidden max-w-[10rem] truncate text-sm text-slate-600 dark:text-slate-400 sm:inline"
                    title={user.email}
                  >
                    {user.email}
                  </span>
                  <button
                    type="button"
                    onClick={logout}
                    className="rounded-md px-3 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
                  >
                    Sign out
                  </button>
                </div>
              ) : (
                <Link
                  to="/sign-in?return=%2Falerts"
                  className="rounded-md px-3 py-2 text-sm font-medium text-teal-700 transition hover:bg-teal-50 dark:text-teal-400 dark:hover:bg-slate-700"
                >
                  Sign in
                </Link>
              )
            )}
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
