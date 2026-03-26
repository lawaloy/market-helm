import React, { useEffect, useRef, useState } from 'react';
import { Listbox, ListboxButton, ListboxOptions, ListboxOption } from '@headlessui/react';
import { ChevronDownIcon } from '@heroicons/react/20/solid';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  Legend,
} from 'recharts';
import { historyApi, stocksApi } from '../services/api';
import { coerceTooltipNumber, formatPercentage, formatDate, formatPrice, getCompanyName } from '../utils/formatters';
import type { DailySummaryPoint, HistoricalPoint } from '../types';

const DAY_OPTIONS = [7, 14, 30, 90];

interface HistoricalTrendsProps {
  refreshKey?: number;
}

const HistoricalTrends: React.FC<HistoricalTrendsProps> = ({ refreshKey = 0 }) => {
  const [data, setData] = useState<DailySummaryPoint[]>([]);
  const [dateRange, setDateRange] = useState<{ first: string; last: string } | null>(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [symbolList, setSymbolList] = useState<string[]>([]);
  const [apiNames, setApiNames] = useState<Record<string, string>>({});
  const [selectedSymbol, setSelectedSymbol] = useState<string>('');
  const [stockHistory, setStockHistory] = useState<HistoricalPoint[]>([]);
  const [stockLoading, setStockLoading] = useState(false);
  const isInitialMount = useRef(true);

  // Names come from summary API (saved at write time in projections/daily data)
  const symbols = symbolList.map((s) => {
    const name = getCompanyName(s, apiNames[s]);
    return {
      value: s,
      label: name !== s ? name : s,
    };
  });

  useEffect(() => {
    fetchData(false);
  }, [days]);

  useEffect(() => {
    if (isInitialMount.current) return;
    fetchData(true);
  }, [refreshKey]);

  useEffect(() => {
    if (selectedSymbol) {
      fetchStockHistory();
    } else {
      setStockHistory([]);
    }
  }, [selectedSymbol, days]);

  const fetchStockHistory = async () => {
    if (!selectedSymbol) return;
    setStockLoading(true);
    try {
      const res = await stocksApi.getHistorical(selectedSymbol, days);
      setStockHistory(res.data?.data ?? []);
    } catch {
      setStockHistory([]);
    } finally {
      setStockLoading(false);
    }
  };

  const fetchData = async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const response = await historyApi.getSummary(days);
      const summaryData = response.data?.data ?? [];
      const first = response.data?.firstDate ?? '';
      const last = response.data?.lastDate ?? '';
      const syms = response.data?.symbols ?? [];
      setSymbolList(syms);
      setApiNames(response.data?.names ?? {});
      setData([...summaryData].reverse());
      setDateRange(first && last ? { first, last } : null);
      if (syms.length > 0 && !selectedSymbol) {
        setSelectedSymbol(syms[0]);
      }
    } catch (err) {
      console.error('Error fetching historical data:', err);
      if (!silent) setError('Unable to load historical data. Please try again later.');
      setData([]);
      setDateRange(null);
    } finally {
      setLoading(false);
      if (!silent) isInitialMount.current = false;
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-[50vh]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-blue-500 mx-auto"></div>
          <p className="mt-4 text-slate-600 dark:text-slate-400">Loading historical trends...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-400 px-4 py-3 rounded">
          <p>{error}</p>
          <p className="mt-2 text-sm">Use the Fetch New button above to fetch data.</p>
          <button onClick={() => fetchData()} className="mt-4 underline font-medium">
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-lg p-8 text-center">
          <p className="text-slate-600 dark:text-slate-400">No historical data available for the selected period.</p>
          <p className="text-sm text-slate-500 dark:text-slate-500 mt-2">
            Use Fetch New regularly to build up historical data over time.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h2 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-slate-100">Historical Trends</h2>
        <p className="mt-1 text-slate-600 dark:text-slate-400 text-sm">
          How your stock projections have changed over time — market-wide and by company.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-4 mb-8">
        <div className="flex items-center gap-2">
          <label htmlFor="days" className="text-sm font-medium text-slate-700 dark:text-slate-300">
            Time range:
          </label>
          <select
            id="days"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="rounded-md border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100 px-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500"
          >
            {DAY_OPTIONS.map((d) => (
              <option key={d} value={d}>
                Last {d} days
              </option>
            ))}
          </select>
        </div>
        {dateRange && (
          <span className="text-sm text-slate-500 dark:text-slate-400">
            {formatDate(dateRange.first)} to {formatDate(dateRange.last)}
          </span>
        )}
      </div>

      <div className="space-y-8">
        {/* Market overview section */}
        <section>
          <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-100 mb-4">Market overview</h3>
          <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
            Aggregated across all tracked stocks for each day.
          </p>
          <div className="space-y-8">
        <div className="card p-6">
          <h4 className="font-medium text-slate-800 dark:text-slate-100 mb-4">Projection confidence</h4>
          <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">How confident the model was in its price targets (0–100%).</p>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
              <Tooltip
                formatter={(value) => {
                  const n = coerceTooltipNumber(value);
                  return n != null ? [`${n}%`, 'Avg Confidence'] : ['', 'Avg Confidence'];
                }}
                labelFormatter={(label) => `Date: ${label}`}
              />
              <Line
                type="monotone"
                dataKey="averageConfidence"
                stroke="#3B82F6"
                strokeWidth={2}
                dot={{ r: 3 }}
                name="Avg Confidence"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-6">
          <h4 className="font-medium text-slate-800 dark:text-slate-100 mb-4">Expected price change</h4>
          <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">Average expected % move across all stocks.</p>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `${v}%`} />
              <Tooltip
                formatter={(value) => {
                  const n = coerceTooltipNumber(value);
                  return n != null ? [formatPercentage(n), 'Expected Move'] : ['', 'Expected Move'];
                }}
                labelFormatter={(label) => `Date: ${label}`}
              />
              <Line
                type="monotone"
                dataKey="expectedMarketMove"
                stroke="#10B981"
                strokeWidth={2}
                dot={{ r: 3 }}
                name="Expected Move"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-6">
          <h4 className="font-medium text-slate-800 dark:text-slate-100 mb-4">Buy vs sell recommendations</h4>
          <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">How many stocks were rated STRONG BUY, BUY, HOLD, etc.</p>
          <ResponsiveContainer width="100%" height={320}>
            <AreaChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip
                contentStyle={{ maxWidth: 300 }}
                labelFormatter={(label) => `Date: ${label}`}
              />
              <Legend />
              <Area type="monotone" dataKey="strongBuy" stackId="1" stroke="#10B981" fill="#10B981" name="STRONG BUY" />
              <Area type="monotone" dataKey="buy" stackId="1" stroke="#34D399" fill="#34D399" name="BUY" />
              <Area type="monotone" dataKey="hold" stackId="1" stroke="#64748B" fill="#64748B" name="HOLD" />
              <Area type="monotone" dataKey="sell" stackId="1" stroke="#F59E0B" fill="#F59E0B" name="SELL" />
              <Area type="monotone" dataKey="strongSell" stackId="1" stroke="#EF4444" fill="#EF4444" name="STRONG SELL" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
          </div>
        </section>

        {/* Per-company view */}
        <section>
          <h3 className="text-lg font-semibold text-slate-800 mb-4">Single stock view</h3>
          <p className="text-sm text-slate-600 mb-6">
            Pick a company to see its price and 5-day target over time.
          </p>
          <div className="card p-6">
          <div className="flex flex-wrap items-center gap-4 mb-6">
            <label htmlFor="symbol" className="text-sm font-medium text-slate-700">
              Company:
            </label>
            <Listbox value={selectedSymbol} onChange={setSelectedSymbol}>
              <div className="relative w-52">
                <ListboxButton
                  id="symbol"
                  title={selectedSymbol ? (symbols.find((x) => x.value === selectedSymbol)?.label ?? selectedSymbol) : undefined}
                  className="relative w-full cursor-pointer rounded-md border border-slate-300 bg-white py-2 pl-3 pr-10 text-left text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                >
                  <span className="block truncate">
                    {selectedSymbol ? symbols.find((x) => x.value === selectedSymbol)?.label ?? selectedSymbol : 'Select a company...'}
                  </span>
                  <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2">
                    <ChevronDownIcon className="h-5 w-5 text-slate-400" aria-hidden="true" />
                  </span>
                </ListboxButton>
                <ListboxOptions
                  anchor="bottom start"
                  className="mt-1 max-h-60 w-56 overflow-auto rounded-md border border-slate-200 bg-white py-1 shadow-lg focus:outline-none"
                >
                  <ListboxOption value="">
                    {({ focus }) => (
                      <div
                        className={`relative cursor-pointer select-none py-2 pl-3 pr-9 ${focus ? 'bg-blue-50' : ''}`}
                      >
                        Select a company...
                      </div>
                    )}
                  </ListboxOption>
                  {symbols.map((s) => (
                    <ListboxOption key={s.value} value={s.value}>
                      {({ focus }) => (
                        <div
                          title={s.label}
                          className={`relative cursor-pointer select-none py-2 pl-3 pr-9 ${focus ? 'bg-blue-50' : ''}`}
                        >
                          <span className="block truncate">{s.label}</span>
                        </div>
                      )}
                    </ListboxOption>
                  ))}
                </ListboxOptions>
              </div>
            </Listbox>
          </div>

          {stockLoading && (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500" />
            </div>
          )}

          {!stockLoading && selectedSymbol && stockHistory.length > 0 && (
            <>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart
                  data={[...stockHistory]
                    .sort((a, b) => (a.date < b.date ? -1 : 1))
                    .map((p) => ({
                    date: p.date,
                    close: p.close,
                    target: p.projection?.targetPrice,
                    change: p.change,
                  }))}
                >
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `$${v.toFixed(0)}`} />
                  <Tooltip
                    formatter={(value, name) => {
                      const n = coerceTooltipNumber(value);
                      const label = name != null ? String(name) : '';
                      return n != null ? [formatPrice(n), label] : ['', label];
                    }}
                    labelFormatter={(label) => `Date: ${label}`}
                  />
                  <Legend />
                  <Line type="monotone" dataKey="close" stroke="#3B82F6" name="Price" strokeWidth={2} dot={{ r: 3 }} />
                  <Line type="monotone" dataKey="target" stroke="#10B981" name="Target (5d)" strokeWidth={2} dot={{ r: 3 }} strokeDasharray="5 5" />
                </LineChart>
              </ResponsiveContainer>
            </>
          )}

          {!stockLoading && selectedSymbol && stockHistory.length === 0 && (
            <div className="py-8 text-center text-slate-600">
              No historical data for <strong>{selectedSymbol}</strong> in this period
            </div>
          )}

          {!selectedSymbol && (
            <div className="py-8 text-center text-slate-500 text-sm">
              Select a company to see its chart
            </div>
          )}
        </div>
        </section>
      </div>
    </div>
  );
};

export default HistoricalTrends;
