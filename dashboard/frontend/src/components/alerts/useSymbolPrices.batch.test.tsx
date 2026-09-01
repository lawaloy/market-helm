import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useSymbolPrices } from './useSymbolPrices';

vi.mock('../../services/api', () => ({
  default: {
    get: vi.fn(),
  },
  alertsApi: {
    getQuotes: vi.fn(),
  },
}));

import api, { alertsApi } from '../../services/api';

const SYMBOLS = Array.from({ length: 16 }, (_, index) => `S${String(index).padStart(2, '0')}`);

function ProbeHarness({ symbols }: { symbols: string[] }) {
  const { apiReady, symbolPrices, fetchPricesFor } = useSymbolPrices();

  return (
    <div>
      <span data-testid="ready">{apiReady ? 'ready' : 'loading'}</span>
      <span data-testid="prices">{JSON.stringify(symbolPrices)}</span>
      <button
        type="button"
        data-testid="fetch"
        onClick={() => {
          void fetchPricesFor(symbols);
        }}
      >
        fetch
      </button>
    </div>
  );
}

describe('useSymbolPrices quote batching', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(api.get).mockReset();
    vi.mocked(alertsApi.getQuotes).mockReset();
    vi.mocked(api.get).mockResolvedValue({ data: { ok: true } });
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('splits 16 watch symbols across two getQuotes calls of 15 then 1', async () => {
    // Partial AxiosResponse is enough for this hook; cast like other API mocks.
    vi.mocked(alertsApi.getQuotes).mockImplementation(async (batch: string[]) => ({
      data: {
        prices: Object.fromEntries(batch.map((symbol, index) => [symbol, 100 + index])),
      },
    }) as never);

    render(<ProbeHarness symbols={SYMBOLS} />);

    await waitFor(() => {
      expect(screen.getByTestId('ready').textContent).toBe('ready');
    });

    await act(async () => {
      screen.getByTestId('fetch').click();
    });

    await waitFor(() => {
      expect(alertsApi.getQuotes).toHaveBeenCalledTimes(1);
    });
    expect(vi.mocked(alertsApi.getQuotes).mock.calls[0][0]).toEqual(SYMBOLS.slice(0, 15));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(400);
    });

    await waitFor(() => {
      expect(alertsApi.getQuotes).toHaveBeenCalledTimes(2);
    });
    expect(vi.mocked(alertsApi.getQuotes).mock.calls[1][0]).toEqual(SYMBOLS.slice(15));

    await waitFor(() => {
      const prices = JSON.parse(screen.getByTestId('prices').textContent || '{}') as Record<
        string,
        number
      >;
      expect(Object.keys(prices).sort()).toEqual([...SYMBOLS].sort());
    });
  });
});
