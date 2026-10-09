import { useEffect, useState } from 'react';
import { ChevronDownIcon, ChevronUpIcon } from '@heroicons/react/20/solid';
import { projectionsApi } from '../../services/api';
import type { Opportunity } from '../../types';
import StockDetailModal from '../modals/StockDetailModal';
import StockTable from './StockTable';

const RECOMMENDATIONS = ['STRONG_BUY', 'BUY', 'HOLD', 'SELL', 'STRONG_SELL'];

export default function LatestForecasts({ refreshKey }: { refreshKey: number }) {
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [retryKey, setRetryKey] = useState(0);
  const [stocks, setStocks] = useState<Opportunity[]>([]);
  const [asOfDate, setAsOfDate] = useState<string>();
  const [selectedStock, setSelectedStock] = useState<string | null>(null);

  useEffect(() => {
    if (!expanded) return;
    let cancelled = false;
    setLoading(true);
    setError(false);

    void Promise.all([
      projectionsApi.getSummary(),
      ...RECOMMENDATIONS.map((recommendation) =>
        projectionsApi.getOpportunities(recommendation, 50),
      ),
    ])
      .then(([summary, ...groups]) => {
        if (cancelled) return;
        setAsOfDate(summary.data.date);
        setStocks(groups.flatMap((group) => group.data.opportunities));
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [expanded, refreshKey, retryKey]);

  return (
    <section aria-label="Experimental forecasts" className="mb-7">
      <button
        type="button"
        aria-expanded={expanded}
        aria-controls="latest-forecasts-content"
        onClick={() => {
          setExpanded((value) => !value);
          if (!expanded) setLoading(true);
          else setSelectedStock(null);
        }}
        className="flex min-h-16 w-full items-center justify-between gap-4 rounded-xl border border-slate-300 bg-white px-5 py-4 text-left shadow-sm hover:border-emerald-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 dark:border-[#31435b] dark:bg-[#101f30] dark:hover:border-emerald-400"
      >
        <span>
          <span className="block text-sm font-extrabold text-slate-950 dark:text-white">
            Explore latest experimental forecasts
          </span>
          <span className="mt-1 block text-xs text-slate-600 dark:text-slate-300">
            Optional comparison of the latest saved targets; accuracy is still being evaluated.
          </span>
        </span>
        {expanded ? (
          <ChevronUpIcon
            className="h-5 w-5 shrink-0 text-slate-600 dark:text-slate-300"
            aria-hidden
          />
        ) : (
          <ChevronDownIcon
            className="h-5 w-5 shrink-0 text-slate-600 dark:text-slate-300"
            aria-hidden
          />
        )}
      </button>

      {expanded && (
        <div id="latest-forecasts-content" className="mt-4">
          {loading ? (
            <p role="status" className="card px-5 py-8 text-sm text-slate-700 dark:text-slate-300">
              Loading latest saved forecasts…
            </p>
          ) : error ? (
            <div role="alert" className="card px-5 py-6 text-sm text-amber-900 dark:text-amber-200">
              Forecasts could not be loaded.{' '}
              <button
                type="button"
                onClick={() => {
                  setLoading(true);
                  setRetryKey((value) => value + 1);
                }}
                className="min-h-11 rounded px-2 font-bold hover:bg-amber-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
              >
                Try again
              </button>
            </div>
          ) : (
            <StockTable
              stocks={stocks}
              asOfDate={asOfDate}
              onStockClick={(symbol) => setSelectedStock(symbol)}
            />
          )}
        </div>
      )}

      {expanded && selectedStock && (
        <StockDetailModal symbol={selectedStock} isOpen onClose={() => setSelectedStock(null)} />
      )}
    </section>
  );
}
