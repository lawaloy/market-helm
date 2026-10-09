import React, { useState } from 'react';
import {
  formatDate,
  formatPrice,
  formatPercentage,
  getCompanyName,
  getRecommendationColor,
  getRiskColor,
} from '../../utils/formatters';
import CompanyLogo from '../common/CompanyLogo';
import ExportButton from '../common/ExportButton';
import type { Opportunity } from '../../types';

interface StockTableProps {
  stocks: Opportunity[];
  onStockClick?: (symbol: string) => void;
  asOfDate?: string;
}

type ForecastSort = 'recommended' | 'change' | 'confidence' | 'company';

const sortableNumber = (value: number): number =>
  Number.isFinite(value) ? value : Number.NEGATIVE_INFINITY;

const changeTone = (value: number): string =>
  !Number.isFinite(value)
    ? 'text-slate-600 dark:text-slate-300'
    : value >= 0
      ? 'text-green-700 dark:text-green-300'
      : 'text-red-700 dark:text-red-300';

function MobileForecastCard({
  stock,
  onStockClick,
}: {
  stock: Opportunity;
  onStockClick?: (symbol: string) => void;
}) {
  const name = getCompanyName(stock.symbol, stock.name);
  return (
    <article className="px-5 py-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <CompanyLogo symbol={stock.symbol} name={name} size={24} />
          <div className="min-w-0">
            <h3 className="truncate text-sm font-bold text-slate-950 dark:text-white">{name}</h3>
            <p className="font-data text-xs text-slate-600 dark:text-slate-300">{stock.symbol}</p>
          </div>
        </div>
        <span className={`badge shrink-0 ${getRecommendationColor(stock.recommendation)}`}>
          {stock.recommendation}
        </span>
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-xs text-slate-600 dark:text-slate-300">Last price</dt>
          <dd className="font-data font-semibold text-slate-950 dark:text-white">
            {formatPrice(stock.currentPrice)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-slate-600 dark:text-slate-300">5-day target</dt>
          <dd className="font-data font-semibold text-slate-950 dark:text-white">
            {formatPrice(stock.targetPrice)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-slate-600 dark:text-slate-300">Forecast change</dt>
          <dd className={`font-data font-semibold ${changeTone(stock.expectedChange)}`}>
            {formatPercentage(stock.expectedChange)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-slate-600 dark:text-slate-300">Confidence</dt>
          <dd className="font-data font-semibold text-slate-950 dark:text-white">
            {Number.isFinite(stock.confidence) ? `${stock.confidence}%` : '—'}
          </dd>
        </div>
      </dl>
      <div className="mt-4 flex items-center justify-between gap-3">
        <span className={`badge ${getRiskColor(stock.risk)}`}>{stock.risk} risk</span>
        {onStockClick && (
          <button
            type="button"
            onClick={() => onStockClick(stock.symbol)}
            className="min-h-11 rounded-md px-2 text-xs font-bold text-emerald-800 hover:bg-emerald-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 dark:text-emerald-300"
            aria-label={`View details for ${name} (${stock.symbol})`}
          >
            View details →
          </button>
        )}
      </div>
    </article>
  );
}

const StockTable: React.FC<StockTableProps> = ({ stocks, onStockClick, asOfDate }) => {
  const [currentPage, setCurrentPage] = useState(1);
  const [filterRec, setFilterRec] = useState('All');
  const [sortBy, setSortBy] = useState<ForecastSort>('recommended');
  const itemsPerPage = 20;

  // Keep corrupt rows from breaking rendering or reaching the detail view.
  const filteredStocks = stocks.filter((stock) => {
    if (typeof stock.symbol !== 'string' || !stock.symbol.trim()) {
      return false;
    }
    const rating = stock.recommendation || '';
    const matchesFilter =
      filterRec === 'All' ||
      (filterRec === 'BUY' && (rating === 'STRONG BUY' || rating === 'BUY')) ||
      (filterRec === 'HOLD' && rating === 'HOLD') ||
      (filterRec === 'SELL' && (rating === 'STRONG SELL' || rating === 'SELL'));

    return matchesFilter;
  });

  const sortedStocks = [...filteredStocks].sort((a, b) => {
    if (sortBy === 'change') {
      return sortableNumber(b.expectedChange) - sortableNumber(a.expectedChange) || 0;
    }
    if (sortBy === 'confidence') {
      return sortableNumber(b.confidence) - sortableNumber(a.confidence) || 0;
    }
    if (sortBy === 'company') {
      return getCompanyName(a.symbol, a.name).localeCompare(getCompanyName(b.symbol, b.name));
    }
    return 0;
  });

  // Paginate — clamp so search/filter cannot leave an empty page with no pager.
  const totalPages = Math.max(1, Math.ceil(filteredStocks.length / itemsPerPage));
  const page = Math.min(Math.max(1, currentPage), totalPages);
  const startIndex = (page - 1) * itemsPerPage;
  const paginatedStocks = sortedStocks.slice(startIndex, startIndex + itemsPerPage);

  return (
    <div className="card overflow-hidden">
      <div className="border-b border-slate-200 px-5 py-5 dark:border-[#26384d]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-2xl">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-extrabold text-slate-950 dark:text-white">
                Stock forecasts
              </h2>
              <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] font-bold text-amber-900 dark:text-amber-200">
                Experimental
              </span>
            </div>
            <p className="mt-1 text-sm leading-6 text-slate-700 dark:text-slate-300">
              Compare each stock's last recorded price with its forecast for five trading days
              later. Select a company for more details.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-bold text-slate-700 dark:bg-[#1a2b3f] dark:text-slate-200">
              {stocks.length} {stocks.length === 1 ? 'stock' : 'stocks'}
              {asOfDate ? ` · ${formatDate(asOfDate)}` : ''}
            </span>
            <ExportButton stocks={sortedStocks} formats={['csv']} label="Stock forecasts" />
          </div>
        </div>
        <p className="mt-4 max-w-3xl rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm leading-6 text-amber-950 dark:text-amber-100">
          Experimental estimates from the latest analysis. Accuracy has not been established; the
          confidence scores are rules-based, not measured probabilities.
        </p>
        <div className="mt-5 flex flex-wrap items-end gap-3">
          <label>
            <span className="mb-1 block text-xs font-bold text-slate-700 dark:text-slate-300">
              Recommendation
            </span>
            <select
              className="min-h-11 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 dark:border-[#31435b] dark:bg-[#101f30] dark:text-slate-100"
              value={filterRec}
              onChange={(e) => setFilterRec(e.target.value)}
            >
              <option value="All">All</option>
              <option value="BUY">Buy</option>
              <option value="HOLD">Hold</option>
              <option value="SELL">Sell</option>
            </select>
          </label>
          <label>
            <span className="mb-1 block text-xs font-bold text-slate-700 dark:text-slate-300">
              Sort by
            </span>
            <select
              className="min-h-11 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 dark:border-[#31435b] dark:bg-[#101f30] dark:text-slate-100"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as ForecastSort)}
            >
              <option value="recommended">Recommendation</option>
              <option value="change">Highest forecast change</option>
              <option value="confidence">Highest confidence</option>
              <option value="company">Company name</option>
            </select>
          </label>
        </div>
        <p className="mt-3 text-xs text-slate-600 dark:text-slate-300" role="status">
          Showing {filteredStocks.length} of {stocks.length} forecasts.
        </p>
      </div>

      {paginatedStocks.length === 0 ? (
        <p className="px-5 py-10 text-center text-sm text-slate-700 dark:text-slate-300">
          {stocks.length === 0
            ? 'No stock forecasts are available yet. Fetch new market data to create them.'
            : 'No forecasts match that recommendation.'}
        </p>
      ) : (
        <>
          <div className="divide-y divide-slate-200 md:hidden dark:divide-[#223248]">
            {paginatedStocks.map((stock) => (
              <MobileForecastCard key={stock.symbol} stock={stock} onStockClick={onStockClick} />
            ))}
          </div>
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full min-w-[840px]">
              <thead className="border-b border-slate-200 bg-slate-50 dark:border-[#26384d] dark:bg-[#122235]">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 dark:text-slate-400 uppercase">
                    Company
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-slate-600 dark:text-slate-400 uppercase">
                    Last price
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-slate-600 dark:text-slate-400 uppercase">
                    5-day target
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-slate-600 dark:text-slate-400 uppercase">
                    Forecast change
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-slate-600 dark:text-slate-400 uppercase">
                    Confidence
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-slate-600 dark:text-slate-400 uppercase">
                    Risk
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-slate-600 dark:text-slate-400 uppercase">
                    Recommendation
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-[#223248]">
                {paginatedStocks.map((stock) => (
                  <tr
                    key={stock.symbol}
                    className="transition hover:bg-slate-100 dark:hover:bg-[#122235]"
                  >
                    <th
                      scope="row"
                      className="px-4 py-3 text-left text-sm font-medium text-slate-900 dark:text-slate-100"
                    >
                      {onStockClick ? (
                        <button
                          type="button"
                          onClick={() => onStockClick(stock.symbol)}
                          className="-m-1 flex min-h-11 max-w-56 items-center gap-2 rounded-md p-1 text-left transition hover:text-emerald-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:ring-offset-[#f3f6f9] dark:hover:text-emerald-300 dark:focus-visible:ring-offset-[#0e1b2a]"
                          aria-label={`View details for ${getCompanyName(stock.symbol, stock.name)} (${stock.symbol})`}
                        >
                          <CompanyLogo
                            symbol={stock.symbol}
                            name={getCompanyName(stock.symbol, stock.name)}
                            size={20}
                          />
                          <span className="min-w-0">
                            <span className="block truncate font-bold">
                              {getCompanyName(stock.symbol, stock.name)}
                            </span>
                            <span className="font-data block text-xs text-slate-600 dark:text-slate-300">
                              {stock.symbol}
                            </span>
                          </span>
                        </button>
                      ) : (
                        <div className="flex items-center gap-2">
                          <CompanyLogo
                            symbol={stock.symbol}
                            name={getCompanyName(stock.symbol, stock.name)}
                            size={20}
                          />
                          <span>
                            <span className="block font-bold">
                              {getCompanyName(stock.symbol, stock.name)}
                            </span>
                            <span className="font-data block text-xs text-slate-600 dark:text-slate-300">
                              {stock.symbol}
                            </span>
                          </span>
                        </div>
                      )}
                    </th>
                    <td className="font-data px-4 py-3 text-right text-sm text-slate-900 dark:text-slate-100">
                      {formatPrice(stock.currentPrice)}
                    </td>
                    <td className="font-data px-4 py-3 text-right text-sm text-slate-900 dark:text-slate-100">
                      {formatPrice(stock.targetPrice)}
                    </td>
                    <td
                      className={`font-data px-4 py-3 text-sm text-right font-medium ${changeTone(stock.expectedChange)}`}
                    >
                      {formatPercentage(stock.expectedChange)}
                    </td>
                    <td className="px-4 py-3 text-center text-sm text-slate-900 dark:text-slate-100">
                      {Number.isFinite(stock.confidence) ? `${stock.confidence}%` : '—'}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`badge ${getRiskColor(stock.risk)}`}>{stock.risk}</span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`badge ${getRecommendationColor(stock.recommendation)}`}>
                        {stock.recommendation}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 border-t border-slate-200 px-5 py-4 dark:border-[#26384d]">
          <button
            className="px-3 py-1 border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200 rounded disabled:opacity-50"
            disabled={page === 1}
            onClick={() => setCurrentPage(page - 1)}
          >
            Previous
          </button>
          <span className="text-sm text-slate-600 dark:text-slate-400">
            Page {page} of {totalPages}
          </span>
          <button
            className="px-3 py-1 border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200 rounded disabled:opacity-50"
            disabled={page === totalPages}
            onClick={() => setCurrentPage(page + 1)}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
};

export default StockTable;
