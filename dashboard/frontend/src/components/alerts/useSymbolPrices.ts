import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import api, { alertsApi } from '../../services/api';
import type { QuoteMeta } from '../../types';

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
  const [quoteMeta, setQuoteMeta] = useState<Record<string, QuoteMeta>>({});
  const [pricingPending, setPricingPending] = useState<Set<string>>(new Set());
  const [attemptedPrices, setAttemptedPrices] = useState<Set<string>>(new Set());
  const [quotesUnavailable, setQuotesUnavailable] = useState(false);
  const [apiReady, setApiReady] = useState(false);
  const [liveQuotesConfigured, setLiveQuotesConfigured] = useState(true);
  const pricesRef = useRef(symbolPrices);
  const inflightRef = useRef<Set<string>>(new Set());
  const failedAtRef = useRef<Map<string, number>>(new Map());
  const lastBatchAtRef = useRef(0);
  const requestChainRef = useRef<Promise<void>>(Promise.resolve());
  const mountedRef = useRef(true);
  const quotesUnavailableRef = useRef(quotesUnavailable);

  pricesRef.current = symbolPrices;
  quotesUnavailableRef.current = quotesUnavailable;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const probe = async () => {
      try {
        const { data } = await api.get<{ ok?: boolean; live_quotes_configured?: boolean }>(
          '/api/alerts/health',
        );
        if (!cancelled && data?.live_quotes_configured === false) {
          setLiveQuotesConfigured(false);
          setQuotesUnavailable(true);
        } else if (!cancelled && data?.ok !== true) {
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

  const mergePrices = useCallback(
    (prices: Record<string, number>, meta?: Record<string, QuoteMeta>) => {
      if (Object.keys(prices).length === 0) return;
      setSymbolPrices((prev) => ({ ...prev, ...prices }));
      if (meta) setQuoteMeta((prev) => ({ ...prev, ...meta }));
    },
    [],
  );

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
    (symbols: string[]) => {
      if (!mountedRef.current || !apiReady || quotesUnavailable) return;

      const unique = [
        ...new Set(symbols.map((symbol) => symbol.toUpperCase().trim()).filter(Boolean)),
      ];
      if (unique.length === 0) return;
      const queued = unique.filter(
        (symbol) => pricesRef.current[symbol] === undefined && !isFetchBlocked(symbol),
      );
      if (queued.length === 0) return;
      setPricingPending((prev) => new Set([...prev, ...queued]));

      const run = async () => {
        if (!mountedRef.current || quotesUnavailableRef.current) return;
        let pending = queued.filter(
          (symbol) => pricesRef.current[symbol] === undefined && !isFetchBlocked(symbol),
        );
        if (pending.length === 0) return;

        while (pending.length > 0) {
          if (!mountedRef.current || quotesUnavailableRef.current) return;

          const now = Date.now();
          const waitMs = BATCH_GAP_MS - (now - lastBatchAtRef.current);
          if (waitMs > 0) await sleep(waitMs);
          if (!mountedRef.current || quotesUnavailableRef.current) return;

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
            if (!mountedRef.current) return;
            const returned = data.prices ?? {};
            const finiteEntries = Object.entries(returned).filter(
              (entry): entry is [string, number] =>
                typeof entry[1] === 'number' && Number.isFinite(entry[1]),
            );
            if (finiteEntries.length > 0) {
              setSymbolPrices((prev) => ({ ...prev, ...Object.fromEntries(finiteEntries) }));
              if (data.quote_meta) {
                setQuoteMeta((prev) => ({ ...prev, ...data.quote_meta }));
              }
              setQuotesUnavailable(false);
            }
            batch.forEach((symbol) => {
              const price = returned[symbol];
              if (typeof price !== 'number' || !Number.isFinite(price)) {
                failedAtRef.current.set(symbol, Date.now());
              } else {
                failedAtRef.current.delete(symbol);
              }
            });
          } catch (err) {
            if (!mountedRef.current) return;
            if (axios.isAxiosError(err) && err.response?.status === 405) {
              quotesUnavailableRef.current = true;
              setQuotesUnavailable(true);
              pending = [];
            }
          } finally {
            batch.forEach((symbol) => inflightRef.current.delete(symbol));
            if (!mountedRef.current) return;
            setAttemptedPrices((prev) => new Set([...prev, ...batch]));
            setPricingPending((prev) => {
              const next = new Set(prev);
              batch.forEach((symbol) => next.delete(symbol));
              return next;
            });
          }
        }
      };

      const request = requestChainRef.current.then(run, run);
      requestChainRef.current = request
        .catch(() => undefined)
        .finally(() => {
          if (!mountedRef.current) return;
          setPricingPending((prev) => {
            const next = new Set(prev);
            queued.forEach((symbol) => next.delete(symbol));
            return next;
          });
        });
      return request;
    },
    [apiReady, isFetchBlocked, quotesUnavailable],
  );

  const retryPriceFor = useCallback(
    (symbol: string) => {
      const key = symbol.toUpperCase().trim();
      if (!key) return;
      failedAtRef.current.delete(key);
      setAttemptedPrices((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
      return fetchPricesFor([key]);
    },
    [fetchPricesFor],
  );

  return {
    symbolPrices,
    quoteMeta,
    mergePrices,
    pricingPending,
    attemptedPrices,
    quotesUnavailable,
    liveQuotesConfigured,
    apiReady,
    fetchPricesFor,
    retryPriceFor,
  };
}
