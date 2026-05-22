import { BellAlertIcon, SparklesIcon } from '@heroicons/react/24/outline';
import { CompanySymbolPicker } from './CompanySymbolPicker';
import { formatPrice, formatQuotePrice, type SymbolOption } from './alertsUtils';

export function AlertComposer({
  newSymbol,
  newOperator,
  newValue,
  symbolOptions,
  symbolsLoading,
  prices,
  pendingPrices,
  onFetchPrices,
  quotesUnavailable = false,
  apiReady = true,
  onSymbolChange,
  onOperatorChange,
  onValueChange,
  onSubmit,
  headline,
  submitting = false,
  canActivate = true,
}: {
  newSymbol: string;
  newOperator: 'less_than' | 'greater_than';
  newValue: string;
  symbolOptions: SymbolOption[];
  symbolsLoading: boolean;
  onSymbolChange: (value: string) => void;
  onOperatorChange: (value: 'less_than' | 'greater_than') => void;
  onValueChange: (value: string) => void;
  onSubmit: () => void;
  headline?: string;
  submitting?: boolean;
  canActivate?: boolean;
  prices: Record<string, number>;
  pendingPrices?: Set<string>;
  onFetchPrices?: (symbols: string[]) => void;
  quotesUnavailable?: boolean;
  apiReady?: boolean;
}) {
  const selectedCompany = symbolOptions.find((option) => option.value === newSymbol);
  const previewName = selectedCompany?.label ?? (newSymbol.trim().toUpperCase() || '—');
  const previewPrice = newValue.trim() ? formatPrice(newValue) : '—';
  const previewVerb = newOperator === 'greater_than' ? 'rises above' : 'falls below';
  const currentPrice = formatQuotePrice(prices[newSymbol.trim().toUpperCase()]);

  return (
    <div className="alerts-composer">
      {headline && (
        <div className="mb-4 flex items-center gap-2">
          <SparklesIcon className="h-4 w-4 text-teal-500" />
          <p className="text-xs font-semibold uppercase tracking-[0.15em] text-teal-600 dark:text-teal-400">
            {headline}
          </p>
        </div>
      )}
      <div className="flex flex-nowrap items-center gap-x-2 overflow-x-auto text-base leading-relaxed text-slate-600 dark:text-slate-300">
        <span className="shrink-0 whitespace-nowrap font-medium text-slate-500 dark:text-slate-400">
          Notify me when
        </span>
        <CompanySymbolPicker
          value={newSymbol}
          onChange={onSymbolChange}
          options={symbolOptions}
          loading={symbolsLoading}
          prices={prices}
          pendingPrices={pendingPrices}
          onFetchPrices={onFetchPrices}
          quotesUnavailable={quotesUnavailable}
          apiReady={apiReady}
        />
        <select
          value={newOperator}
          onChange={(e) => onOperatorChange(e.target.value as 'less_than' | 'greater_than')}
          aria-label="Price direction"
          className="alerts-inline-select shrink-0"
        >
          <option value="less_than">falls below</option>
          <option value="greater_than">rises above</option>
        </select>
        <span className="inline-flex shrink-0 items-center gap-0.5 font-medium text-slate-500 dark:text-slate-400">
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
      </div>
      <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">
        You&apos;ll be informed when{' '}
        <span className="font-semibold text-slate-700 dark:text-slate-200">{previewName}</span>{' '}
        {previewVerb}{' '}
        <span className="font-semibold tabular-nums text-slate-700 dark:text-slate-200">${previewPrice}</span>
        {currentPrice ? (
          <>
            {' '}
            <span className="text-slate-400">· now {currentPrice}</span>
          </>
        ) : null}
      </p>
      <button
        type="button"
        onClick={onSubmit}
        disabled={symbolsLoading || !newSymbol || submitting}
        className="alerts-cta mt-5 disabled:cursor-not-allowed"
      >
        <BellAlertIcon className="h-4 w-4" />
        {submitting ? 'Starting watch…' : canActivate ? 'Set watch' : 'Add to list'}
      </button>
    </div>
  );
}
