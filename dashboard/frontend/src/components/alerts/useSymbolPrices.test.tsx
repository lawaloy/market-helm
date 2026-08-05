import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import axios from 'axios';
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

function ProbeHarness({ symbols }: { symbols?: string[] }) {
  const {
    apiReady,
    quotesUnavailable,
    symbolPrices,
    fetchPricesFor,
    pricingPending,
  } = useSymbolPrices();

  return (
    <div>
      <span data-testid="ready">{apiReady ? 'ready' : 'loading'}</span>
      <span data-testid="unavailable">{quotesUnavailable ? 'yes' : 'no'}</span>
      <span data-testid="prices">{JSON.stringify(symbolPrices)}</span>
      <span data-testid="pending">{pricingPending.size}</span>
      <button
        type="button"
        data-testid="fetch"
        onClick={() => {
          void fetchPricesFor(symbols ?? ['AAPL']);
        }}
      >
        fetch
      </button>
    </div>
  );
}

describe('useSymbolPrices', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(api.get).mockReset();
    vi.mocked(alertsApi.getQuotes).mockReset();
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('marks apiReady after a healthy probe and clears fail state', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: { ok: true } });

    render(<ProbeHarness />);

    await waitFor(() => {
      expect(screen.getByTestId('ready').textContent).toBe('ready');
    });
    expect(screen.getByTestId('unavailable').textContent).toBe('no');
    expect(api.get).toHaveBeenCalledWith('/api/alerts/health');
  });

  it('sets quotesUnavailable when health probe is not ok', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: { ok: false } });

    render(<ProbeHarness />);

    await waitFor(() => {
      expect(screen.getByTestId('ready').textContent).toBe('ready');
    });
    expect(screen.getByTestId('unavailable').textContent).toBe('yes');
  });

  it('sets quotesUnavailable when health probe throws', async () => {
    vi.mocked(api.get).mockRejectedValueOnce(new Error('network'));

    render(<ProbeHarness />);

    await waitFor(() => {
      expect(screen.getByTestId('ready').textContent).toBe('ready');
    });
    expect(screen.getByTestId('unavailable').textContent).toBe('yes');
  });

  it('does not fetch quotes while unavailable', async () => {
    vi.mocked(api.get).mockRejectedValueOnce(new Error('down'));

    render(<ProbeHarness />);

    await waitFor(() => {
      expect(screen.getByTestId('unavailable').textContent).toBe('yes');
    });

    await act(async () => {
      screen.getByTestId('fetch').click();
    });

    expect(alertsApi.getQuotes).not.toHaveBeenCalled();
  });

  it('cools down a missing quote symbol for FAILED_RETRY_MS', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: { ok: true } });
    vi.mocked(alertsApi.getQuotes).mockResolvedValue({ data: { prices: {} } });

    render(<ProbeHarness symbols={['MSFT']} />);

    await waitFor(() => {
      expect(screen.getByTestId('ready').textContent).toBe('ready');
    });

    await act(async () => {
      screen.getByTestId('fetch').click();
    });

    await waitFor(() => {
      expect(alertsApi.getQuotes).toHaveBeenCalledTimes(1);
    });

    await act(async () => {
      screen.getByTestId('fetch').click();
    });
    // Still inside the 45s fail cooldown — no second request.
    expect(alertsApi.getQuotes).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(45_000);
    });

    await act(async () => {
      screen.getByTestId('fetch').click();
    });

    await waitFor(() => {
      expect(alertsApi.getQuotes).toHaveBeenCalledTimes(2);
    });
  });

  it('stops further batches when quotes endpoint returns 405', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: { ok: true } });
    const err = new Error('Method Not Allowed') as Error & {
      isAxiosError?: boolean;
      response?: { status: number };
    };
    err.isAxiosError = true;
    err.response = { status: 405 };
    vi.spyOn(axios, 'isAxiosError').mockReturnValue(true);
    vi.mocked(alertsApi.getQuotes).mockRejectedValueOnce(err);

    render(<ProbeHarness symbols={['AAPL', 'MSFT']} />);

    await waitFor(() => {
      expect(screen.getByTestId('ready').textContent).toBe('ready');
    });

    await act(async () => {
      screen.getByTestId('fetch').click();
    });

    await waitFor(() => {
      expect(screen.getByTestId('unavailable').textContent).toBe('yes');
    });
    expect(JSON.parse(screen.getByTestId('prices').textContent || '{}')).toEqual({});
  });
});
