import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import api, { alertsApi } from '../../services/api';

const MAX_BATCH = 15;
const BATCH_GAP_MS = 400;
const FAILED_RETRY_MS = 45_000;

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

/**
 * Stable symbol price fetching for the alerts picker.
 * Uses refs so callbacks don't change identity and retrigger fetch loops.
 */
export function useSymbolPrices() {
  const [symbolPrices, setSymbolPrices] = useState<Record<string, number>>({});
  const [pricingPending, setPricingPending] = useState<Set<string>>(new Set());
  const [quotesUnavailable, setQuotesUnavailable] = useState(false);
  const [apiReady, setApiReady] = useState(false);
  const pricesRef = useRef(symbolPrices);
  const inflightRef = useRef<Set<string>>(new Set());
  const failedAtRef = useRef<Map<string, number>>(new Map());
  const lastBatchAtRef = useRef(0);

  pricesRef.current = symbolPrices;

  useEffect(() => {
    let cancelled = false;
    const probe = async () => {
      try {
        const { data } = await api.get<{ ok?: boolean }>('/api/alerts/health');
        if (!cancelled && data?.ok !== true) {
          setQuotesUnavailable(true);
        } else if (!cancelled) {
          failedAtRef.current.clear();
        }
      } catch {
        if (!cancelled) setQuotesUnavailable(true);
      } finally {
        if (!cancelled) setApiReady(true);
      }
    };
    void probe();
    return () => {
      cancelled = true;
    };
  }, []);

  const mergePrices = useCallback((prices: Record<string, number>) => {
    if (Object.keys(prices).length === 0) return;
    setSymbolPrices((prev) => ({ ...prev, ...prices }));
  }, []);

  const isFetchBlocked = useCallback((symbol: string) => {
    if (inflightRef.current.has(symbol)) return true;
    const failedAt = failedAtRef.current.get(symbol);
    if (failedAt === undefined) return false;
    if (Date.now() - failedAt >= FAILED_RETRY_MS) {
      failedAtRef.current.delete(symbol);
      return false;
    }
    return true;
  }, []);

  const fetchPricesFor = useCallback(
    async (symbols: string[]) => {
      if (!apiReady || quotesUnavailable) return;

      const unique = [...new Set(symbols.map((symbol) => symbol.toUpperCase().trim()).filter(Boolean))];
      let pending = unique.filter(
        (symbol) => pricesRef.current[symbol] === undefined && !isFetchBlocked(symbol),
      );
      if (pending.length === 0) return;

      while (pending.length > 0) {
        const now = Date.now();
        const waitMs = BATCH_GAP_MS - (now - lastBatchAtRef.current);
        if (waitMs > 0) await sleep(waitMs);

        pending = pending.filter(
          (symbol) => pricesRef.current[symbol] === undefined && !isFetchBlocked(symbol),
        );
        if (pending.length === 0) return;

        const batch = pending.slice(0, MAX_BATCH);
        pending = pending.slice(MAX_BATCH);
        lastBatchAtRef.current = Date.now();

        batch.forEach((symbol) => inflightRef.current.add(symbol));
        setPricingPending((prev) => new Set([...prev, ...batch]));

        try {
          const { data } = await alertsApi.getQuotes(batch);
          const returned = data.prices ?? {};
          if (Object.keys(returned).length > 0) {
            setSymbolPrices((prev) => ({ ...prev, ...returned }));
            setQuotesUnavailable(false);
          }
          batch.forEach((symbol) => {
            if (returned[symbol] === undefined) {
              failedAtRef.current.set(symbol, Date.now());
            } else {
              failedAtRef.current.delete(symbol);
            }
          });
        } catch (err) {
          if (axios.isAxiosError(err) && err.response?.status === 405) {
            setQuotesUnavailable(true);
            pending = [];
          }
        } finally {
          batch.forEach((symbol) => inflightRef.current.delete(symbol));
          setPricingPending((prev) => {
            const next = new Set(prev);
            batch.forEach((symbol) => next.delete(symbol));
            return next;
          });
        }
      }
    },
    [apiReady, isFetchBlocked, quotesUnavailable],
  );

  return {
    symbolPrices,
    mergePrices,
    pricingPending,
    quotesUnavailable,
    apiReady,
    fetchPricesFor,
  };
}
