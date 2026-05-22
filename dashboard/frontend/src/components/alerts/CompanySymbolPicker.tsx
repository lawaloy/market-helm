import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Listbox, ListboxButton, ListboxOption, ListboxOptions } from '@headlessui/react';
import { ChevronUpDownIcon } from '@heroicons/react/20/solid';
import { formatQuotePrice, type SymbolOption } from './alertsUtils';

const EMPTY_SET = new Set<string>();

function priceLabel(
  symbol: string,
  prices: Record<string, number>,
  pending: Set<string>,
  quotesUnavailable: boolean,
  apiReady: boolean,
): string {
  if (quotesUnavailable) return '—';
  const key = symbol.toUpperCase();
  const quote = formatQuotePrice(prices[key]);
  if (quote) return quote;
  if (pending.has(key) || !apiReady) return '…';
  return '—';
}

export function CompanySymbolPicker({
  value,
  onChange,
  options,
  loading,
  prices,
  pendingPrices,
  onFetchPrices,
  quotesUnavailable = false,
  apiReady = true,
}: {
  value: string;
  onChange: (symbol: string) => void;
  options: SymbolOption[];
  loading: boolean;
  prices: Record<string, number>;
  pendingPrices?: Set<string>;
  onFetchPrices?: (symbols: string[]) => void;
  quotesUnavailable?: boolean;
  apiReady?: boolean;
}) {
  const [search, setSearch] = useState('');
  const listRef = useRef<HTMLDivElement>(null);
  const fetchRef = useRef(onFetchPrices);
  fetchRef.current = onFetchPrices;
  const pending = pendingPrices ?? EMPTY_SET;
  const selected = options.find((option) => option.value === value);
  const selectedPrice = value ? prices[value.toUpperCase()] : undefined;

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return options;
    return options.filter((option) => option.searchText.includes(query));
  }, [options, search]);

  const collectVisibleSymbols = useCallback(() => {
    const container = listRef.current;
    if (!container) return [] as string[];
    const rows = container.querySelectorAll<HTMLElement>('[data-symbol]');
    const symbols: string[] = [];
    const containerRect = container.getBoundingClientRect();
    rows.forEach((row) => {
      const rect = row.getBoundingClientRect();
      if (rect.bottom >= containerRect.top && rect.top <= containerRect.bottom) {
        const symbol = row.dataset.symbol;
        if (symbol) symbols.push(symbol);
      }
    });
    return symbols;
  }, []);

  const requestPrices = useCallback((symbols: string[]) => {
    fetchRef.current?.(symbols);
  }, []);

  const buttonLabel = loading
    ? 'Loading…'
    : selected
      ? [selected.label, formatQuotePrice(selectedPrice)].filter(Boolean).join(' · ')
      : 'Pick a company…';

  return (
    <Listbox
      value={value}
      onChange={(symbol) => {
        onChange(symbol);
        setSearch('');
        requestPrices([symbol]);
      }}
    >
      {({ open }) => (
        <PickerPanel
          open={open}
          search={search}
          setSearch={setSearch}
          filtered={filtered}
          options={options}
          prices={prices}
          pending={pending}
          listRef={listRef}
          collectVisibleSymbols={collectVisibleSymbols}
          requestPrices={requestPrices}
          buttonLabel={buttonLabel}
          value={value}
          quotesUnavailable={quotesUnavailable}
          apiReady={apiReady}
        />
      )}
    </Listbox>
  );
}

function PickerPanel({
  open,
  search,
  setSearch,
  filtered,
  options,
  prices,
  pending,
  listRef,
  collectVisibleSymbols,
  requestPrices,
  buttonLabel,
  value,
  quotesUnavailable,
  apiReady,
}: {
  open: boolean;
  search: string;
  setSearch: (value: string) => void;
  filtered: SymbolOption[];
  options: SymbolOption[];
  prices: Record<string, number>;
  pending: Set<string>;
  listRef: React.RefObject<HTMLDivElement | null>;
  collectVisibleSymbols: () => string[];
  requestPrices: (symbols: string[]) => void;
  buttonLabel: string;
  value: string;
  quotesUnavailable: boolean;
  apiReady: boolean;
}) {
  const openedRef = useRef(false);

  useEffect(() => {
    if (!open) {
      openedRef.current = false;
      return;
    }
    if (!apiReady || quotesUnavailable) return;
    const handle = window.setTimeout(() => {
      const visible = collectVisibleSymbols();
      if (visible.length > 0) requestPrices(visible);
    }, 50);
    openedRef.current = true;
    return () => window.clearTimeout(handle);
  }, [apiReady, collectVisibleSymbols, open, quotesUnavailable, requestPrices]);

  useEffect(() => {
    if (quotesUnavailable || !apiReady || !open || !search.trim()) return;
    const handle = window.setTimeout(() => {
      requestPrices(filtered.slice(0, 15).map((option) => option.value));
    }, 300);
    return () => window.clearTimeout(handle);
  }, [apiReady, filtered, open, quotesUnavailable, requestPrices, search]);

  useEffect(() => {
    if (quotesUnavailable || !apiReady || !open) return;
    const node = listRef.current;
    if (!node) return;
    let frame = 0;
    let lastScrollFetch = 0;
    const onScroll = () => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(() => {
        const now = Date.now();
        if (now - lastScrollFetch < 600) return;
        lastScrollFetch = now;
        const visible = collectVisibleSymbols();
        if (visible.length > 0) requestPrices(visible);
      });
    };
    node.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      node.removeEventListener('scroll', onScroll);
      window.cancelAnimationFrame(frame);
    };
  }, [apiReady, collectVisibleSymbols, listRef, open, quotesUnavailable, requestPrices]);

  return (
    <div className="relative min-w-[7.5rem] max-w-[11rem] flex-1 sm:max-w-[13rem]">
      <ListboxButton
        aria-label="Company"
        title={buttonLabel}
        className="alerts-inline-select relative w-full cursor-pointer truncate pr-9 text-left"
      >
        <span className="block truncate">{buttonLabel}</span>
        <ChevronUpDownIcon
          className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
          aria-hidden
        />
      </ListboxButton>
      <ListboxOptions
        anchor="bottom start"
        className="z-30 mt-1 max-h-72 w-[min(100vw-2rem,26rem)] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl focus:outline-none dark:border-slate-600 dark:bg-slate-900"
      >
        <div className="sticky top-0 border-b border-slate-100 bg-white p-2 dark:border-slate-700 dark:bg-slate-900">
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.stopPropagation()}
            placeholder="Search Apple, AAPL…"
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
          />
        </div>
        <div ref={listRef} className="max-h-56 overflow-y-auto py-1">
          {!search.trim() && options.length > 0 && (
            <p className="px-3 py-1.5 text-xs text-slate-400">
              {options.length >= 100
                ? 'Scroll or search — prices load for companies in view'
                : `${options.length} companies`}
            </p>
          )}
          {filtered.length === 0 ? (
            <p className="px-3 py-2 text-sm text-slate-500">No companies match your search.</p>
          ) : (
            filtered.map((option) => {
              const quote = priceLabel(option.value, prices, pending, quotesUnavailable, apiReady);
              return (
                <ListboxOption key={option.value} value={option.value}>
                  {({ focus, selected: isSelected }) => (
                    <div
                      data-symbol={option.value.toUpperCase()}
                      title={
                        quote !== '—' && quote !== '…'
                          ? `${option.label} · ${quote}`
                          : option.label
                      }
                      className={`flex cursor-pointer items-center justify-between gap-3 px-3 py-2 text-sm ${
                        focus || isSelected || option.value === value
                          ? 'bg-teal-50 text-teal-900 dark:bg-teal-950/40 dark:text-teal-100'
                          : 'text-slate-700 dark:text-slate-200'
                      }`}
                    >
                      <span className="min-w-0 truncate">{option.label}</span>
                      <span
                        className={`shrink-0 tabular-nums text-xs font-medium ${
                          quote === '—'
                            ? 'text-slate-300 dark:text-slate-600'
                            : focus || isSelected
                              ? 'text-teal-700 dark:text-teal-300'
                              : 'text-slate-500 dark:text-slate-400'
                        }`}
                      >
                        {quote}
                      </span>
                    </div>
                  )}
                </ListboxOption>
              );
            })
          )}
        </div>
      </ListboxOptions>
    </div>
  );
}
