import { useEffect, useRef, useState } from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext';
import { AuthProvider } from './contexts/AuthContext';
import Header from './components/layout/Header';
import RequireAuth from './components/auth/RequireAuth';
import Dashboard from './pages/Dashboard';
import HistoricalTrends from './pages/HistoricalTrends';
import Summary from './pages/Summary';
import AlertsSettings from './pages/AlertsSettings';
import SignIn from './pages/SignIn';
import api, { alertsApi } from './services/api';

function App() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [dataDate, setDataDate] = useState<string>('');
  const [backgroundFetching, setBackgroundFetching] = useState(false);
  const hasAutoFetched = useRef(false);

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
    if (hasAutoFetched.current) return;
    hasAutoFetched.current = true;

    void runBackgroundAlertCheck();

    const fetchIfNeeded = async () => {
      let refreshSucceeded = false;
      try {
        const { data } = await api.get<{ needs_fetch: boolean }>('/api/data-info');
        if (!data.needs_fetch) return;

        setBackgroundFetching(true);
        await api.post('/api/refresh');
        const pollIntervalMs = 2000;
        const maxWaitMs = 15 * 60 * 1000;
        const started = Date.now();

        const poll = async (): Promise<void> => {
          if (Date.now() - started > maxWaitMs) {
            setBackgroundFetching(false);
            return;
          }
          const { data: status } = await api.get<{ is_running: boolean; last_status: string }>(
            '/api/refresh/status',
          );
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
        setBackgroundFetching(false);
      } finally {
        if (!refreshSucceeded) {
          await runBackgroundAlertCheck();
        }
      }
    };
    fetchIfNeeded();
  }, []);

  return (
    <ThemeProvider>
    <AuthProvider>
    <BrowserRouter>
      <div className="min-h-screen bg-slate-50 dark:bg-slate-900">
        <Header
          dataDate={dataDate}
          onRefreshComplete={handleRefreshComplete}
          onQuickRefresh={handleQuickRefresh}
          backgroundFetching={backgroundFetching}
        />
        <div className="border-b border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <nav className="flex gap-6">
              <NavLink
                to="/"
                end
                className={({ isActive }) =>
                  `py-4 px-1 border-b-2 text-sm font-medium transition-colors ${
                    isActive
                      ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                      : 'border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300 dark:text-slate-400 dark:hover:text-slate-200 dark:hover:border-slate-600'
                  }`
                }
              >
                Dashboard
              </NavLink>
              <NavLink
                to="/historical"
                className={({ isActive }) =>
                  `py-4 px-1 border-b-2 text-sm font-medium transition-colors ${
                    isActive
                      ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                      : 'border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300 dark:text-slate-400 dark:hover:text-slate-200 dark:hover:border-slate-600'
                  }`
                }
              >
                Historical Trends
              </NavLink>
              <NavLink
                to="/summary"
                className={({ isActive }) =>
                  `py-4 px-1 border-b-2 text-sm font-medium transition-colors ${
                    isActive
                      ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                      : 'border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300 dark:text-slate-400 dark:hover:text-slate-200 dark:hover:border-slate-600'
                  }`
                }
              >
                Summary
              </NavLink>
              <NavLink
                to="/alerts"
                className={({ isActive }) =>
                  `py-4 px-1 border-b-2 text-sm font-medium transition-colors ${
                    isActive
                      ? 'border-teal-500 text-teal-600 dark:text-teal-400'
                      : 'border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300 dark:text-slate-400 dark:hover:text-slate-200 dark:hover:border-slate-600'
                  }`
                }
              >
                Helmtower
              </NavLink>
            </nav>
          </div>
        </div>
        <Routes>
          <Route path="/" element={<Dashboard refreshKey={refreshKey} onDataLoaded={setDataDate} />} />
          <Route path="/historical" element={<HistoricalTrends refreshKey={refreshKey} />} />
          <Route path="/summary" element={<Summary refreshKey={refreshKey} />} />
          <Route path="/sign-in" element={<SignIn />} />
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
    </BrowserRouter>
    </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
