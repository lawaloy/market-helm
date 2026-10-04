import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Combobox,
  ComboboxButton,
  ComboboxInput,
  ComboboxOption,
  ComboboxOptions,
} from '@headlessui/react';
import { ChevronUpDownIcon } from '@heroicons/react/20/solid';
import { formatQuotePrice, quoteContext, type SymbolOption } from './alertsUtils';
import type { QuoteMeta } from '../../types';

const EMPTY_SET = new Set<string>();
const OPTION_PAGE_SIZE = 60;
const PRICE_WINDOW_SIZE = 8;
const OPTION_ROW_HEIGHT = 36;
const SELECTED_LABEL_MAX_LENGTH = 17;

export function compactCompanyLabel(
  label: string,
  symbol: string,
  maxLength = SELECTED_LABEL_MAX_LENGTH,
): string {
  if (label.length <= maxLength) return label;

  const ticker = symbol.toUpperCase();
  const suffix = ` (${ticker})`;
  const name = label.endsWith(suffix)
    ? label.slice(0, -suffix.length).trimEnd()
    : label.endsWith(` · ${ticker}`)
      ? label.slice(0, -` · ${ticker}`.length).trimEnd()
      : label;
  const availableNameLength = Math.max(1, maxLength - suffix.length - 1);

  return `${name.slice(0, availableNameLength).trimEnd()}…${suffix}`;
}

function priceLabel(
  symbol: string,
  prices: Record<string, number>,
  pending: Set<string>,
  attempted: Set<string>,
  quotesUnavailable: boolean,
  apiReady: boolean,
): string {
  const key = symbol.toUpperCase();
  const quote = formatQuotePrice(prices[key]);
  if (quote) return quote;
  if (pending.has(key) || !apiReady) return 'Loading…';
  if (quotesUnavailable || attempted.has(key)) return 'No price';
  return 'Load on scroll';
}

export function CompanySymbolPicker({
  value,
  onChange,
  options,
  loading,
  prices,
  quoteMeta,
  pendingPrices,
  attemptedPrices,
  onFetchPrices,
  quotesUnavailable = false,
  apiReady = true,
}: {
  value: string;
  onChange: (symbol: string) => void;
  options: SymbolOption[];
  loading: boolean;
  prices: Record<string, number>;
  quoteMeta?: Record<string, QuoteMeta>;
  pendingPrices?: Set<string>;
  attemptedPrices?: Set<string>;
  onFetchPrices?: (symbols: string[]) => void;
  quotesUnavailable?: boolean;
  apiReady?: boolean;
}) {
  const [search, setSearch] = useState('');
  const fetchRef = useRef(onFetchPrices);
  fetchRef.current = onFetchPrices;
  const pending = pendingPrices ?? EMPTY_SET;
  const attempted = attemptedPrices ?? EMPTY_SET;
  const selected = options.find((option) => option.value === value);
  const selectedPrice = value ? prices[value.toUpperCase()] : undefined;

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return options;
    return options.filter((option) => option.searchText.includes(query));
  }, [options, search]);

  const requestPrices = useCallback((symbols: string[]) => {
    fetchRef.current?.(symbols);
  }, []);

  const selectedQuote = formatQuotePrice(selectedPrice);
  const inputLabel = loading
    ? 'Loading…'
    : selected
      ? compactCompanyLabel(selected.label, selected.value)
      : 'Pick a company…';
  const buttonLabel = [
    selected?.label ?? inputLabel,
    selectedQuote,
    selectedQuote ? quoteContext(quoteMeta?.[value.toUpperCase()]) : null,
  ]
    .filter(Boolean)
    .join(' · ');

  return (
    <Combobox
      value={value}
      onChange={(symbol) => {
        if (!symbol) return;
        onChange(symbol);
        setSearch('');
        requestPrices([symbol]);
      }}
      onClose={() => setSearch('')}
    >
      {({ open }) => (
        <PickerPanel
          open={open}
          search={search}
          setSearch={setSearch}
          filtered={filtered}
          prices={prices}
          quoteMeta={quoteMeta}
          pending={pending}
          attempted={attempted}
          inputLabel={inputLabel}
          buttonLabel={buttonLabel}
          selectedQuote={selectedQuote}
          value={value}
          quotesUnavailable={quotesUnavailable}
          apiReady={apiReady}
          requestPrices={requestPrices}
        />
      )}
    </Combobox>
  );
}

function PickerPanel({
  open,
  search,
  setSearch,
  filtered,
  prices,
  quoteMeta,
  pending,
  attempted,
  inputLabel,
  buttonLabel,
  selectedQuote,
  value,
  quotesUnavailable,
  apiReady,
  requestPrices,
}: {
  open: boolean;
  search: string;
  setSearch: (value: string) => void;
  filtered: SymbolOption[];
  prices: Record<string, number>;
  quoteMeta?: Record<string, QuoteMeta>;
  pending: Set<string>;
  attempted: Set<string>;
  inputLabel: string;
  buttonLabel: string;
  selectedQuote: string | null;
  value: string;
  quotesUnavailable: boolean;
  apiReady: boolean;
  requestPrices: (symbols: string[]) => void;
}) {
  const [visibleCount, setVisibleCount] = useState(OPTION_PAGE_SIZE);
  const optionsRef = useRef<HTMLDivElement>(null);
  const positionedForOpenRef = useRef(false);
  const scrollPriceTimerRef = useRef<number | null>(null);
  const selectedIndex = search ? -1 : filtered.findIndex((option) => option.value === value);
  const displayed = filtered.slice(0, visibleCount);

  useEffect(() => {
    positionedForOpenRef.current = false;
    setVisibleCount(
      open && selectedIndex >= 0
        ? Math.max(
            OPTION_PAGE_SIZE,
            Math.ceil((selectedIndex + 1) / OPTION_PAGE_SIZE) * OPTION_PAGE_SIZE,
          )
        : OPTION_PAGE_SIZE,
    );
  }, [open, search, selectedIndex]);

  useEffect(() => {
    if (
      !open ||
      search ||
      selectedIndex < 0 ||
      selectedIndex >= visibleCount ||
      positionedForOpenRef.current
    )
      return;
    const frame = requestAnimationFrame(() => {
      const node = optionsRef.current;
      if (!node) return;
      node.scrollTop = Math.max(0, selectedIndex * OPTION_ROW_HEIGHT - node.clientHeight / 2);
      positionedForOpenRef.current = true;
    });
    return () => cancelAnimationFrame(frame);
  }, [open, search, selectedIndex, visibleCount]);

  const requestPriceWindow = useCallback(
    (start: number, count = PRICE_WINDOW_SIZE) => {
      if (!open || !apiReady || quotesUnavailable) return;
      const missing = filtered
        .slice(start, start + count)
        .map((option) => option.value)
        .filter(
          (symbol) =>
            prices[symbol.toUpperCase()] === undefined &&
            !pending.has(symbol.toUpperCase()) &&
            !attempted.has(symbol.toUpperCase()),
        );
      if (missing.length > 0) requestPrices(missing);
    },
    [apiReady, attempted, filtered, open, pending, prices, quotesUnavailable, requestPrices],
  );

  useEffect(() => {
    requestPriceWindow(selectedIndex >= 0 ? selectedIndex : 0);
  }, [requestPriceWindow, selectedIndex]);

  useEffect(
    () => () => {
      if (scrollPriceTimerRef.current !== null) {
        window.clearTimeout(scrollPriceTimerRef.current);
      }
    },
    [open, search],
  );

  return (
    <div className="relative min-w-[7.5rem] max-w-[11rem] flex-1 sm:max-w-[15rem]">
      <div className="relative">
        <ComboboxInput
          aria-label="Company"
          title={buttonLabel}
          placeholder="Search Apple, AAPL…"
          className={`alerts-inline-select w-full truncate text-left ${
            !open && selectedQuote ? 'pr-28' : 'pr-9'
          }`}
          displayValue={() => inputLabel}
          onChange={(event) => setSearch(event.target.value)}
        />
        {!open && selectedQuote && (
          <span className="font-data pointer-events-none absolute inset-y-0 right-9 flex w-20 items-center justify-end text-xs font-semibold tabular-nums text-teal-700 dark:text-teal-300">
            {selectedQuote}
          </span>
        )}
        <ComboboxButton
          aria-label="Open company list"
          className="absolute inset-y-0 right-0 flex w-9 items-center justify-center rounded-r-lg text-slate-500 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-teal-500 dark:text-slate-400 dark:hover:text-slate-100"
        >
          <ChevronUpDownIcon className="h-4 w-4" aria-hidden />
        </ComboboxButton>
      </div>
      <ComboboxOptions
        ref={optionsRef}
        anchor="bottom start"
        onScroll={(event) => {
          const node = event.currentTarget;
          const remaining = node.scrollHeight - node.scrollTop - node.clientHeight;
          const priceStart = Math.max(0, Math.floor(node.scrollTop / OPTION_ROW_HEIGHT));
          const priceCount = Math.ceil(node.clientHeight / OPTION_ROW_HEIGHT) + 1;
          if (scrollPriceTimerRef.current !== null) {
            window.clearTimeout(scrollPriceTimerRef.current);
          }
          scrollPriceTimerRef.current = window.setTimeout(() => {
            requestPriceWindow(priceStart, priceCount);
            scrollPriceTimerRef.current = null;
          }, 120);
          if (remaining < 80 && visibleCount < filtered.length) {
            setVisibleCount((current) => Math.min(current + OPTION_PAGE_SIZE, filtered.length));
          }
        }}
        className="z-30 mt-1 max-h-72 w-[min(100vw-2rem,26rem)] overflow-y-auto rounded-xl border border-slate-200 bg-white py-1 shadow-xl focus:outline-none dark:border-slate-600 dark:bg-slate-900"
      >
        {filtered.length === 0 ? (
          <ComboboxOption
            disabled
            value=""
            className="px-3 py-2 text-sm text-slate-500 dark:text-slate-400"
          >
            No companies match your search.
          </ComboboxOption>
        ) : (
          displayed.map((option) => {
            const quote = priceLabel(
              option.value,
              prices,
              pending,
              attempted,
              quotesUnavailable,
              apiReady,
            );
            return (
              <ComboboxOption key={option.value} value={option.value}>
                {({ focus, selected: isSelected }) => (
                  <div
                    data-symbol={option.value.toUpperCase()}
                    title={`${option.label} · ${quote}${prices[option.value.toUpperCase()] !== undefined ? ` · ${quoteContext(quoteMeta?.[option.value.toUpperCase()])}` : ''}`}
                    className={`grid cursor-pointer grid-cols-[minmax(0,1fr)_6rem] items-center gap-3 px-3 py-2 text-sm ${
                      focus || isSelected || option.value === value
                        ? 'bg-teal-50 text-teal-900 dark:bg-teal-950/40 dark:text-teal-100'
                        : 'text-slate-700 dark:text-slate-200'
                    }`}
                  >
                    <span className="min-w-0 truncate">{option.label}</span>
                    <span
                      data-testid="company-quote"
                      className={`text-right tabular-nums text-xs font-medium ${
                        quote === 'No price' || quote === 'Load on scroll'
                          ? 'text-slate-600 dark:text-slate-400'
                          : focus || isSelected
                            ? 'text-teal-700 dark:text-teal-300'
                            : 'text-slate-600 dark:text-slate-400'
                      }`}
                    >
                      {quote}
                    </span>
                    {prices[option.value.toUpperCase()] !== undefined && (
                      <span className="sr-only">
                        {quoteContext(quoteMeta?.[option.value.toUpperCase()])}
                      </span>
                    )}
                  </div>
                )}
              </ComboboxOption>
            );
          })
        )}
      </ComboboxOptions>
      <span className="sr-only" aria-live="polite">
        {open && displayed.length < filtered.length
          ? `Showing ${displayed.length} of ${filtered.length} companies. Keep scrolling or search to narrow the list.`
          : ''}
      </span>
    </div>
  );
}
