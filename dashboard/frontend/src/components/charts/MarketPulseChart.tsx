import { Link } from 'react-router';
import type { StockMover } from '../../types';
import { formatPercentage, formatPrice, getCompanyName } from '../../utils/formatters';

interface MarketPulseChartProps {
  gainers: StockMover[];
  losers: StockMover[];
}

function MoverList({
  title,
  rows,
  maxMove,
  direction,
}: {
  title: string;
  rows: StockMover[];
  maxMove: number;
  direction: 'up' | 'down';
}) {
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
        <ul className="divide-y divide-slate-200 overflow-hidden rounded-lg border border-slate-200 bg-white dark:divide-[#26384d] dark:border-[#31435b] dark:bg-[#101f30]">
          {rows.map((row) => (
            <li key={row.symbol}>
              <Link
                to={`/historical?symbol=${encodeURIComponent(row.symbol)}`}
                aria-label={`Explore ${getCompanyName(row.symbol, row.name)} history: ${formatPercentage(row.changePercent)} on this date`}
                className="block min-h-16 px-4 py-3 transition-colors hover:bg-emerald-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-emerald-500 dark:hover:bg-[#172d40]"
              >
                <span className="flex items-center justify-between gap-3">
                  <span className="min-w-0 truncate text-sm font-bold text-slate-950 dark:text-white">
                    {getCompanyName(row.symbol, row.name)}{' '}
                    <span className="font-data text-xs font-normal text-slate-600 dark:text-slate-300">
                      {row.symbol}
                    </span>
                  </span>
                  <span
                    className={`font-data shrink-0 text-sm font-bold ${
                      direction === 'up'
                        ? 'text-emerald-800 dark:text-emerald-300'
                        : 'text-rose-800 dark:text-rose-300'
                    }`}
                  >
                    {formatPercentage(row.changePercent)}
                  </span>
                </span>
                <span className="mt-1 flex items-center gap-3">
                  <span className="font-data shrink-0 text-xs text-slate-600 dark:text-slate-300">
                    {formatPrice(row.price)}
                  </span>
                  <span
                    className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200 dark:bg-[#31435b]"
                    aria-hidden="true"
                  >
                    <span
                      className={`block h-full rounded-full ${direction === 'up' ? 'bg-emerald-500' : 'bg-rose-500'}`}
                      style={{
                        width: `${Math.min((Math.abs(row.changePercent) / maxMove) * 100, 100)}%`,
                      }}
                    />
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function MarketPulseChart({ gainers, losers }: MarketPulseChartProps) {
  const rises = gainers
    .filter((row) => row.symbol && Number.isFinite(row.changePercent) && row.changePercent > 0)
    .sort((a, b) => b.changePercent - a.changePercent)
    .slice(0, 4);
  const falls = losers
    .filter((row) => row.symbol && Number.isFinite(row.changePercent) && row.changePercent < 0)
    .sort((a, b) => a.changePercent - b.changePercent)
    .slice(0, 4);
  const maxMove = Math.max(1, ...[...rises, ...falls].map((row) => Math.abs(row.changePercent)));

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <MoverList title="Biggest gainers" rows={rises} maxMove={maxMove} direction="up" />
      <MoverList title="Biggest decliners" rows={falls} maxMove={maxMove} direction="down" />
    </div>
  );
}
