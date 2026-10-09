import { useEffect, useRef, useState } from 'react';
import { BrowserRouter, Routes, Route, NavLink, Navigate, Link } from 'react-router';
import {
  BellAlertIcon,
  ChartBarSquareIcon,
  ChartPieIcon,
  ClockIcon,
} from '@heroicons/react/24/outline';
import { ThemeProvider } from './contexts/ThemeContext';
import { AuthProvider } from './contexts/AuthContext';
import Header from './components/layout/Header';
import RequireAuth from './components/auth/RequireAuth';
import Dashboard from './pages/Dashboard';
import HistoricalTrends from './pages/HistoricalTrends';
import AlertsSettings from './pages/AlertsSettings';
import SignIn from './pages/SignIn';
import AccountRecovery from './pages/AccountRecovery';
import AccountSettings from './pages/AccountSettings';
import api, { alertsApi } from './services/api';

function App() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [backgroundFetching, setBackgroundFetching] = useState(false);
  /** Bumped on unmount so StrictMode remount / navigation cannot apply late setState. */
  const autofetchGenerationRef = useRef(0);

  const runBackgroundAlertCheck = async () => {
    try {
      await alertsApi.runCheck();
    } catch {
      // No watches, no saved data, or alerts not configured yet.
    }
  };

  const handleRefreshComplete = () => {
    setRefreshKey((prev) => prev + 1);
    void runBackgroundAlertCheck();
  };

  const handleQuickRefresh = () => {
    setRefreshKey((prev) => prev + 1);
  };

  const refreshCompleteRef = useRef(handleRefreshComplete);
  refreshCompleteRef.current = handleRefreshComplete;

  // On first load: fetch latest trading day data if missing, then check watches.
  useEffect(() => {
    const generation = ++autofetchGenerationRef.current;
    const isActive = () => generation === autofetchGenerationRef.current;

    void runBackgroundAlertCheck();

    const fetchIfNeeded = async () => {
      let refreshSucceeded = false;
      try {
        const { data } = await api.get<{ needs_fetch: boolean }>('/api/data-info');
        if (!isActive() || !data.needs_fetch) return;

        setBackgroundFetching(true);
        await api.post('/api/refresh');
        if (!isActive()) return;

        const pollIntervalMs = 2000;
        const maxWaitMs = 15 * 60 * 1000;
        const started = Date.now();

        const poll = async (): Promise<void> => {
          if (!isActive()) return;
          if (Date.now() - started > maxWaitMs) {
            setBackgroundFetching(false);
            return;
          }
          const { data: status } = await api.get<{ is_running: boolean; last_status: string }>(
            '/api/refresh/status',
          );
          if (!isActive()) return;
          if (status.is_running) {
            await new Promise((r) => setTimeout(r, pollIntervalMs));
            return poll();
          }
          setBackgroundFetching(false);
          if (status.last_status === 'success') {
            refreshSucceeded = true;
            refreshCompleteRef.current();
          }
        };
        await poll();
      } catch {
        if (isActive()) setBackgroundFetching(false);
      } finally {
        if (isActive() && !refreshSucceeded) {
          await runBackgroundAlertCheck();
        }
      }
    };
    void fetchIfNeeded();

    return () => {
      autofetchGenerationRef.current += 1;
    };
  }, []);

  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <div className="min-h-screen bg-[#e5ebf1] dark:bg-[#08111d]">
            <aside className="relative z-30 flex w-full flex-col border-b border-slate-300 bg-[#f3f6f9] lg:fixed lg:inset-y-0 lg:left-0 lg:w-56 lg:border-b-0 lg:border-r dark:border-[#223248] dark:bg-[#091522]">
              <div className="h-20 border-b border-slate-200 px-3 dark:border-[#223248]">
                <Link
                  to="/"
                  aria-label="MarketHelm home"
                  className="flex h-full items-center gap-3 rounded-lg px-2 text-slate-950 outline-none transition hover:bg-slate-200/60 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-teal-500 dark:text-slate-50 dark:hover:bg-[#101f30]"
                >
                  <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-400/10 text-emerald-500">
                    <ChartBarSquareIcon className="h-6 w-6" aria-hidden="true" />
                  </span>
                  <span className="text-lg font-extrabold tracking-[-0.03em]">MarketHelm</span>
                </Link>
              </div>
              <nav
                className="flex gap-1 overflow-x-auto px-3 py-2 lg:flex-1 lg:flex-col lg:gap-0 lg:space-y-1 lg:py-6"
                aria-label="Primary navigation"
              >
                {[
                  { to: '/', end: true, label: 'Dashboard', icon: ChartPieIcon },
                  { to: '/historical', label: 'Historical Trends', icon: ClockIcon },
                  { to: '/alerts', label: 'Helmtower', icon: BellAlertIcon },
                ].map(({ to, end, label, icon: Icon }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={end}
                    className={({ isActive }) =>
                      `group flex shrink-0 items-center gap-3 rounded-lg border-b-2 px-3 py-3 text-sm font-semibold transition lg:border-b-0 lg:border-l-2 ${
                        isActive
                          ? label === 'Helmtower'
                            ? 'border-teal-500 bg-teal-500/10 text-teal-700 dark:text-teal-300'
                            : 'border-blue-500 bg-slate-100 text-slate-950 dark:bg-[#15263a] dark:text-white'
                          : 'border-transparent text-slate-600 hover:bg-slate-100 hover:text-slate-950 dark:text-slate-400 dark:hover:bg-[#101f30] dark:hover:text-slate-100'
                      }`
                    }
                  >
                    <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
                    <span>{label}</span>
                  </NavLink>
                ))}
              </nav>
              <div className="hidden border-t border-slate-300 px-5 py-5 text-xs leading-5 text-slate-600 lg:block dark:border-[#223248] dark:text-slate-400">
                Evidence before action.
                <br />
                Risk stays visible.
              </div>
            </aside>

            <div className="lg:pl-56">
              <Header
                onRefreshComplete={handleRefreshComplete}
                onQuickRefresh={handleQuickRefresh}
                backgroundFetching={backgroundFetching}
              />
              <Routes>
                <Route path="/" element={<Dashboard refreshKey={refreshKey} />} />
                <Route path="/historical" element={<HistoricalTrends refreshKey={refreshKey} />} />
                <Route path="/summary" element={<Navigate to="/#market-brief" replace />} />
                <Route path="/sign-in" element={<SignIn />} />
                <Route path="/forgot-password" element={<AccountRecovery mode="forgot" />} />
                <Route path="/reset-password" element={<AccountRecovery mode="reset" />} />
                <Route path="/verify-email" element={<AccountRecovery mode="verify" />} />
                <Route
                  path="/account"
                  element={
                    <RequireAuth>
                      <AccountSettings />
                    </RequireAuth>
                  }
                />
                <Route
                  path="/alerts"
                  element={
                    <RequireAuth>
                      <AlertsSettings />
                    </RequireAuth>
                  }
                />
              </Routes>
            </div>
          </div>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
