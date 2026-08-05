import React, { useEffect, useRef, useState } from 'react';
import { ArrowPathIcon } from '@heroicons/react/24/outline';
import axios from 'axios';
import ExportButton from '../components/common/ExportButton';
import api, { summaryApi } from '../services/api';
import { formatDate } from '../utils/formatters';

interface SummaryProps {
  refreshKey?: number;
}

const POLL_MS = 2000;
const MAX_WAIT_MS = 15 * 60 * 1000;

const Summary: React.FC<SummaryProps> = ({ refreshKey = 0 }) => {
  const [summary, setSummary] = useState<string>('');
  const [date, setDate] = useState<string>('');
  const [source, setSource] = useState<'ai' | 'demo'>('demo');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshNote, setRefreshNote] = useState<string | null>(null);
  const summaryRef = useRef<HTMLDivElement>(null);
  const isInitialMount = useRef(true);
  const refreshActiveRef = useRef(false);
  /** Bumped on unmount / superseded refreshKey loads so late responses are ignored. */
  const loadGenerationRef = useRef(0);

  useEffect(() => {
    return () => {
      refreshActiveRef.current = false;
      loadGenerationRef.current += 1;
    };
  }, []);

  useEffect(() => {
    void fetchSummary(false);
  }, []);

  useEffect(() => {
    if (isInitialMount.current) return;
    void fetchSummary(true);
  }, [refreshKey]);

  const fetchSummary = async (silent = false) => {
    const generation = ++loadGenerationRef.current;
    if (!silent) setLoading(true);
    setError(null);
    try {
      const res = await summaryApi.getSummary();
      if (generation !== loadGenerationRef.current) return;
      setSummary(res.data.summary);
      setDate(res.data.date);
      setSource(res.data.source);
    } catch (e) {
      if (generation !== loadGenerationRef.current) return;
      if (!silent) {
        let msg = 'Unable to load summary.';
        if (axios.isAxiosError(e)) {
          const status = e.response?.status;
          if (status === 404) {
            msg = 'show-fetch-button';
          } else if (status && status >= 500) {
            msg = 'Something went wrong. Please try again later.';
          } else if (e.code === 'ECONNREFUSED' || e.message?.includes('Network Error')) {
            msg = 'Unable to connect. Please try again.';
          }
        }
        setError(msg);
      }
    } finally {
      if (generation !== loadGenerationRef.current) return;
      setLoading(false);
      if (!silent) isInitialMount.current = false;
    }
  };

  const stopRefresh = (note: string | null = null) => {
    refreshActiveRef.current = false;
    setIsRefreshing(false);
    setRefreshNote(note);
  };

  const handleFetchNew = async () => {
    setIsRefreshing(true);
    setRefreshNote(null);
    refreshActiveRef.current = true;
    // Capture generation so a late success after cancel cannot clear the note
    // or apply a superseded summary fetch started by this poll loop.
    const pollGeneration = loadGenerationRef.current;
    const pollStarted = Date.now();

    try {
      await api.post('/api/refresh');

      while (refreshActiveRef.current) {
        if (Date.now() - pollStarted > MAX_WAIT_MS) {
          stopRefresh('Refresh is taking too long. Please try again.');
          return;
        }

        const statusRes = await api.get('/api/refresh/status');
        if (
          !refreshActiveRef.current ||
          pollGeneration !== loadGenerationRef.current
        ) {
          return;
        }

        if (statusRes.data.is_running) {
          await new Promise((r) => setTimeout(r, POLL_MS));
          continue;
        }

        if (statusRes.data.last_status === 'success') {
          await fetchSummary();
          if (pollGeneration !== loadGenerationRef.current) {
            return;
          }
          stopRefresh(null);
          return;
        }

        if (statusRes.data.last_status === 'idle') {
          stopRefresh(null);
          return;
        }

        stopRefresh('Refresh failed. Please try again.');
        return;
      }
    } catch {
      if (
        refreshActiveRef.current &&
        pollGeneration === loadGenerationRef.current
      ) {
        stopRefresh('Failed to start refresh. Please try again.');
      }
    }
  };

  const handleCancelRefresh = async () => {
    // Invalidate in-flight status / success paths before awaiting cancel so a
    // late success cannot wipe the cancelled note or reload summary.
    refreshActiveRef.current = false;
    loadGenerationRef.current += 1;
    try {
      await api.post('/api/refresh/cancel');
      stopRefresh('Refresh cancelled.');
    } catch {
      stopRefresh('Failed to cancel refresh.');
    }
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="animate-pulse card p-8">
          <div className="h-4 bg-slate-200 dark:bg-slate-600 rounded w-1/4 mb-4" />
          <div className="space-y-2">
            <div className="h-3 bg-slate-200 dark:bg-slate-600 rounded" />
            <div className="h-3 bg-slate-200 dark:bg-slate-600 rounded" />
            <div className="h-3 bg-slate-200 dark:bg-slate-600 rounded w-3/4" />
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    const showFetchButton = error === 'show-fetch-button';
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-lg p-6">
          <p className="text-slate-700 dark:text-slate-300 mb-4">
            {showFetchButton
              ? 'No summary available yet.'
              : error}
          </p>
          {refreshNote && (
            <p className="text-sm text-slate-600 dark:text-slate-400 mb-4">{refreshNote}</p>
          )}
          {showFetchButton && (
            <div className="flex items-center gap-3 flex-wrap">
              <button
                onClick={handleFetchNew}
                disabled={isRefreshing}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium bg-blue-500 text-white hover:bg-blue-600 disabled:bg-slate-300 disabled:cursor-not-allowed transition-colors"
              >
                <ArrowPathIcon className={`h-5 w-5 ${isRefreshing ? 'animate-spin' : ''}`} />
                {isRefreshing ? 'Fetching...' : 'Fetch New'}
              </button>
              {isRefreshing && (
                <button
                  type="button"
                  onClick={handleCancelRefresh}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium bg-red-500 text-white hover:bg-red-600 transition-colors"
                >
                  Cancel
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div ref={summaryRef} className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="card">
        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-600 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Market Summary</h1>
          <div className="flex items-center gap-3 flex-wrap">
            <ExportButton captureRef={summaryRef} formats={['png', 'pdf']} label="Summary" />
            <span className="text-sm text-slate-500 dark:text-slate-400">
              {date ? formatDate(date) : '—'}
            </span>
            {source === 'ai' && (
              <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400">
                Expert Summary
              </span>
            )}
          </div>
        </div>
        <div className="px-6 py-6">
          <p className="text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-wrap">
            {summary}
          </p>
        </div>
      </div>
    </div>
  );
};

export default Summary;
