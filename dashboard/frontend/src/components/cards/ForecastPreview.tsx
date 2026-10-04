import { useEffect, useState } from 'react';
import { ArrowRightIcon } from '@heroicons/react/24/outline';
import { Link } from 'react-router';
import { historyApi } from '../../services/api';
import type { RunProjection } from '../../types';
import { formatDate, formatPercentage, formatPrice, getCompanyName } from '../../utils/formatters';

function ForecastList({ title, rows }: { title: string; rows: RunProjection[] }) {
  return (
    <div className="min-w-0">
      <h3 className="mb-2 text-xs font-extrabold uppercase tracking-[0.12em] text-slate-600 dark:text-slate-300">
        {title}
      </h3>
      {rows.length === 0 ? (
        <p className="rounded-lg border border-slate-200 px-4 py-5 text-sm text-slate-600 dark:border-[#31435b] dark:text-slate-300">
          None for this date.
        </p>
      ) : (
        <div className="divide-y divide-slate-200 overflow-hidden rounded-lg border border-slate-200 bg-white dark:divide-[#26384d] dark:border-[#31435b] dark:bg-[#101f30]">
          {rows.map((row) => (
            <Link
              key={row.symbol}
              to={`/historical?symbol=${encodeURIComponent(row.symbol)}`}
              aria-label={`Explore ${getCompanyName(row.symbol, row.name)} forecast history`}
              className="group flex min-h-20 items-center justify-between gap-3 px-4 py-3 transition-colors hover:bg-emerald-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-emerald-500 dark:hover:bg-[#172d40]"
            >
              <span className="min-w-0">
                <span className="block truncate text-sm font-bold text-slate-950 dark:text-white">
                  {getCompanyName(row.symbol, row.name)}
                </span>
                <span className="font-data block text-xs text-slate-600 dark:text-slate-300">
                  {row.symbol} · Last {formatPrice(row.currentPrice ?? Number.NaN)} · Target{' '}
                  {formatPrice(row.targetPrice ?? Number.NaN)}
                </span>
              </span>
              <span
                className={`font-data shrink-0 text-sm font-bold ${
                  (row.expectedChange ?? 0) > 0
                    ? 'text-emerald-800 dark:text-emerald-300'
                    : 'text-rose-800 dark:text-rose-300'
                }`}
              >
                {formatPercentage(row.expectedChange ?? 0)}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ForecastPreview({
  date,
  refreshKey,
}: {
  date: string;
  refreshKey: number;
}) {
  const [rows, setRows] = useState<RunProjection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    void historyApi
      .getRunProjections(date)
      .then(({ data }) => {
        if (!cancelled) setRows(data.projections);
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
  }, [date, refreshKey, retryKey]);

  const usable = rows.filter(
    (row) =>
      row.symbol &&
      Number.isFinite(row.expectedChange) &&
      Number.isFinite(row.currentPrice) &&
      Number.isFinite(row.targetPrice) &&
      (row.currentPrice ?? 0) > 0 &&
      (row.targetPrice ?? 0) > 0,
  );
  const rises = usable
    .filter((row) => (row.expectedChange ?? 0) > 0)
    .sort((a, b) => (b.expectedChange ?? 0) - (a.expectedChange ?? 0))
    .slice(0, 3);
  const falls = usable
    .filter((row) => (row.expectedChange ?? 0) < 0)
    .sort((a, b) => (a.expectedChange ?? 0) - (b.expectedChange ?? 0))
    .slice(0, 3);

  return (
    <section className="card mt-5 p-5 sm:p-6" aria-labelledby="forecast-preview-title">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2
              id="forecast-preview-title"
              className="text-lg font-extrabold text-slate-950 dark:text-white"
            >
              Five-day forecast preview
            </h2>
            <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] font-bold text-amber-900 dark:text-amber-200">
              Experimental
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-700 dark:text-slate-300">
            The model's largest projected rises and falls from {formatDate(date)}.
          </p>
        </div>
        <Link
          to="/historical"
          className="inline-flex min-h-11 items-center gap-2 text-sm font-bold text-emerald-800 hover:text-emerald-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 dark:text-emerald-300 dark:hover:text-emerald-200"
        >
          All forecasts and past accuracy <ArrowRightIcon className="h-4 w-4" aria-hidden />
        </Link>
      </div>

      {loading ? (
        <div role="status" className="mt-5 grid gap-4 md:grid-cols-2">
          <div className="h-56 animate-pulse rounded-lg bg-slate-200 dark:bg-[#172b40]" />
          <div className="h-56 animate-pulse rounded-lg bg-slate-200 dark:bg-[#172b40]" />
          <span className="sr-only">Loading forecast preview</span>
        </div>
      ) : error ? (
        <div role="alert" className="mt-5 text-sm text-slate-700 dark:text-slate-300">
          Forecast preview is unavailable.{' '}
          <button
            type="button"
            onClick={() => setRetryKey((value) => value + 1)}
            className="rounded px-2 py-1 font-bold text-emerald-800 hover:bg-emerald-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 dark:text-emerald-300"
          >
            Try again
          </button>
        </div>
      ) : usable.length === 0 ? (
        <p className="mt-5 text-sm text-slate-700 dark:text-slate-300">
          No complete forecasts are available for this date.
        </p>
      ) : (
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <ForecastList title="Projected rises" rows={rises} />
          <ForecastList title="Projected falls" rows={falls} />
        </div>
      )}
      <p className="mt-4 border-t border-slate-200 pt-3 text-xs leading-5 text-slate-600 dark:border-[#26384d] dark:text-slate-300">
        <strong>Disclaimer:</strong> Forecasts are hypothetical and may differ from actual prices.
        The projections are not investment advice.
      </p>
    </section>
  );
}
