import { BellAlertIcon, SparklesIcon } from '@heroicons/react/24/outline';
import { CompanySymbolPicker } from './CompanySymbolPicker';
import { formatPrice, formatQuotePrice, quoteContext, type SymbolOption } from './alertsUtils';
import type { QuoteMeta } from '../../types';

export type ComposerMode = 'price' | 'rsi' | 'price_and_rsi';

export function AlertComposer({
  mode,
  onModeChange,
  newSymbol,
  newOperator,
  newValue,
  newRsiOperator,
  newRsiValue,
  symbolOptions,
  symbolsLoading,
  prices,
  quoteMeta,
  pendingPrices,
  attemptedPrices,
  onFetchPrices,
  onRetryPrice,
  quotesUnavailable = false,
  apiReady = true,
  onSymbolChange,
  onOperatorChange,
  onValueChange,
  onRsiOperatorChange,
  onRsiValueChange,
  onSubmit,
  headline,
  submitting = false,
  canActivate = true,
}: {
  mode: ComposerMode;
  onModeChange: (mode: ComposerMode) => void;
  newSymbol: string;
  newOperator: 'less_than' | 'greater_than';
  newValue: string;
  newRsiOperator: 'less_than' | 'greater_than';
  newRsiValue: string;
  symbolOptions: SymbolOption[];
  symbolsLoading: boolean;
  onSymbolChange: (value: string) => void;
  onOperatorChange: (value: 'less_than' | 'greater_than') => void;
  onValueChange: (value: string) => void;
  onRsiOperatorChange: (value: 'less_than' | 'greater_than') => void;
  onRsiValueChange: (value: string) => void;
  onSubmit: () => void;
  headline?: string;
  submitting?: boolean;
  canActivate?: boolean;
  prices: Record<string, number>;
  quoteMeta?: Record<string, QuoteMeta>;
  pendingPrices?: Set<string>;
  attemptedPrices?: Set<string>;
  onFetchPrices?: (symbols: string[]) => void;
  onRetryPrice?: (symbol: string) => void;
  quotesUnavailable?: boolean;
  apiReady?: boolean;
}) {
  const selectedCompany = symbolOptions.find((option) => option.value === newSymbol);
  const previewName = selectedCompany?.label ?? (newSymbol.trim().toUpperCase() || '—');
  const trimmedValue = newValue.trim();
  const parsedValue = trimmedValue === '' ? Number.NaN : Number(trimmedValue);
  const hasFinitePrice = Number.isFinite(parsedValue);
  const trimmedRsi = newRsiValue.trim();
  const parsedRsi = trimmedRsi === '' ? Number.NaN : Number(trimmedRsi);
  const hasFiniteRsi = Number.isFinite(parsedRsi);
  const previewPrice = hasFinitePrice ? formatPrice(parsedValue) : '—';
  const previewRsi = hasFiniteRsi ? formatPrice(parsedRsi) : '—';
  const previewVerb = newOperator === 'greater_than' ? 'rises above' : 'falls below';
  const previewRsiVerb = newRsiOperator === 'greater_than' ? 'rises above' : 'falls below';
  const currentPrice = formatQuotePrice(prices[newSymbol.trim().toUpperCase()]);
  const currentQuoteMeta = quoteMeta?.[newSymbol.trim().toUpperCase()];
  const needsPrice = mode === 'price' || mode === 'price_and_rsi';
  const needsRsi = mode === 'rsi' || mode === 'price_and_rsi';
  const canSubmit =
    !symbolsLoading &&
    Boolean(newSymbol) &&
    !submitting &&
    (!needsPrice || hasFinitePrice) &&
    (!needsRsi || hasFiniteRsi);

  return (
    <div className="alerts-composer">
      {headline && (
        <div className="mb-4 flex items-center gap-2">
          <SparklesIcon className="h-4 w-4 text-teal-500" />
          <p className="text-xs font-semibold uppercase tracking-[0.15em] text-teal-800 dark:text-teal-400">
            {headline}
          </p>
        </div>
      )}
      <div className="mb-4 flex flex-wrap gap-2">
        {(
          [
            ['price', 'Price'],
            ['rsi', 'RSI'],
            ['price_and_rsi', 'Price + RSI'],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => onModeChange(value)}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
              mode === value
                ? 'bg-teal-700 text-white shadow-sm'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="flex flex-nowrap items-center gap-x-2 overflow-x-auto text-base leading-relaxed text-slate-600 dark:text-slate-300">
        <span className="shrink-0 whitespace-nowrap font-medium text-slate-600 dark:text-slate-400">
          Notify me when
        </span>
        <CompanySymbolPicker
          value={newSymbol}
          onChange={onSymbolChange}
          options={symbolOptions}
          loading={symbolsLoading}
          prices={prices}
          quoteMeta={quoteMeta}
          pendingPrices={pendingPrices}
          attemptedPrices={attemptedPrices}
          onFetchPrices={onFetchPrices}
          quotesUnavailable={quotesUnavailable}
          apiReady={apiReady}
        />
        {needsPrice ? (
          <>
            <select
              value={newOperator}
              onChange={(e) => onOperatorChange(e.target.value as 'less_than' | 'greater_than')}
              aria-label="Price direction"
              className="alerts-inline-select shrink-0"
            >
              <option value="less_than">falls below</option>
              <option value="greater_than">rises above</option>
            </select>
            <span className="inline-flex shrink-0 items-center gap-0.5 font-medium text-slate-600 dark:text-slate-400">
              $
              <input
                type="number"
                value={newValue}
                onChange={(e) => onValueChange(e.target.value)}
                aria-label="Target price"
                className="alerts-inline-input w-[5.5rem]"
                placeholder="150.00"
              />
            </span>
          </>
        ) : null}
        {needsRsi ? (
          <>
            {needsPrice ? (
              <span className="shrink-0 font-medium text-slate-600 dark:text-slate-400">
                and RSI(14)
              </span>
            ) : (
              <span className="shrink-0 font-medium text-slate-600 dark:text-slate-400">
                RSI(14)
              </span>
            )}
            <select
              value={newRsiOperator}
              onChange={(e) => onRsiOperatorChange(e.target.value as 'less_than' | 'greater_than')}
              aria-label="RSI direction"
              className="alerts-inline-select shrink-0"
            >
              <option value="less_than">falls below</option>
              <option value="greater_than">rises above</option>
            </select>
            <input
              type="number"
              value={newRsiValue}
              onChange={(e) => onRsiValueChange(e.target.value)}
              aria-label="RSI threshold"
              className="alerts-inline-input w-[4.5rem] shrink-0"
              placeholder="30"
            />
          </>
        ) : null}
      </div>
      <p className="mt-3 text-sm text-slate-600 dark:text-slate-400">
        You&apos;ll be informed when{' '}
        <span className="font-semibold text-slate-700 dark:text-slate-200">{previewName}</span>{' '}
        {needsPrice ? (
          <>
            {previewVerb}{' '}
            <span className="font-semibold tabular-nums text-slate-700 dark:text-slate-200">
              ${previewPrice}
            </span>
          </>
        ) : null}
        {needsPrice && needsRsi ? ' and ' : null}
        {needsRsi ? (
          <>
            RSI(14) {previewRsiVerb}{' '}
            <span className="font-semibold tabular-nums text-slate-700 dark:text-slate-200">
              {previewRsi}
            </span>
          </>
        ) : null}
      </p>
      {currentPrice && (
        <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
          Reference price {currentPrice} · {quoteContext(currentQuoteMeta)}.
        </p>
      )}
      {!currentPrice &&
        !symbolsLoading &&
        (attemptedPrices?.has(newSymbol.toUpperCase()) || quotesUnavailable) && (
          <p role="status" className="mt-1 text-xs text-amber-800 dark:text-amber-300">
            No saved or live price is available for {newSymbol}. The watch can be set, but price
            checks need a future quote.
            {!quotesUnavailable && onRetryPrice && (
              <button
                type="button"
                onClick={() => onRetryPrice(newSymbol)}
                className="ml-2 rounded px-1 font-bold text-teal-700 hover:bg-teal-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 dark:text-teal-300"
              >
                Try price again
              </button>
            )}
          </p>
        )}
      <button
        type="button"
        onClick={onSubmit}
        disabled={!canSubmit}
        className="alerts-cta mt-5 disabled:cursor-not-allowed"
      >
        <BellAlertIcon className="h-4 w-4" />
        {submitting ? 'Starting watch…' : canActivate ? 'Set watch' : 'Add to list'}
      </button>
    </div>
  );
}
