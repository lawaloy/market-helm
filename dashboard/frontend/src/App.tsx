import { useEffect, useRef, useState } from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext';
import Header from './components/layout/Header';
import Dashboard from './pages/Dashboard';
import HistoricalTrends from './pages/HistoricalTrends';
import Summary from './pages/Summary';
import api from './services/api';

function App() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [dataDate, setDataDate] = useState<string>('');
  const [backgroundFetching, setBackgroundFetching] = useState(false);
  const hasAutoFetched = useRef(false);

  const handleRefreshComplete = () => {
    setRefreshKey((prev) => prev + 1);
  };

  const handleQuickRefresh = () => {
    setRefreshKey((prev) => prev + 1);
  };

  const refreshCompleteRef = useRef(handleRefreshComplete);
  refreshCompleteRef.current = handleRefreshComplete;

  // On first load: fetch latest trading day data if missing (runs behind the scenes, no button click)
  useEffect(() => {
    if (hasAutoFetched.current) return;
    hasAutoFetched.current = true;

    const fetchIfNeeded = async () => {
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
            refreshCompleteRef.current();
          }
        };
        await poll();
      } catch {
        setBackgroundFetching(false);
      }
    };
    fetchIfNeeded();
  }, []);

  return (
    <ThemeProvider>
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
            </nav>
          </div>
        </div>
        <Routes>
          <Route path="/" element={<Dashboard refreshKey={refreshKey} onDataLoaded={setDataDate} />} />
          <Route path="/historical" element={<HistoricalTrends refreshKey={refreshKey} />} />
          <Route path="/summary" element={<Summary refreshKey={refreshKey} />} />
        </Routes>
      </div>
    </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
