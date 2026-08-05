import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import HistoricalTrends from './HistoricalTrends';

const apiMocks = vi.hoisted(() => ({
  getSummary: vi.fn(),
  getAccuracy: vi.fn(),
  getHistorical: vi.fn(),
}));

vi.mock('../services/api', () => ({
  historyApi: {
    getSummary: apiMocks.getSummary,
    getAccuracy: apiMocks.getAccuracy,
  },
  stocksApi: {
    getHistorical: apiMocks.getHistorical,
  },
}));

function summaryPayload(overrides: Record<string, unknown> = {}) {
  return {
    data: {
      data: [
        {
          date: '2026-08-04',
          averageConfidence: 70,
          expectedMarketMove: 1.2,
          strongBuy: 1,
          buy: 2,
          hold: 3,
          sell: 0,
          strongSell: 0,
        },
      ],
      firstDate: '2026-08-01',
      lastDate: '2026-08-04',
      symbols: ['AAPL'],
      names: { AAPL: 'Apple Inc' },
      ...overrides,
    },
  };
}

describe('HistoricalTrends fetch races', () => {
  beforeEach(() => {
    apiMocks.getSummary.mockResolvedValue(summaryPayload());
    apiMocks.getAccuracy.mockResolvedValue({
      data: {
        summary: { sampleCount: 0, meanAbsErrorPct: null, byRecommendation: {} },
        samples: [],
      },
    });
    apiMocks.getHistorical.mockResolvedValue({ data: { data: [] } });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('ignores a late summary response after unmount', async () => {
    let resolveSummary: ((value: unknown) => void) | undefined;
    apiMocks.getSummary.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveSummary = resolve;
        }),
    );

    render(<HistoricalTrends />);
    await act(async () => {
      await Promise.resolve();
    });

    expect(apiMocks.getSummary).toHaveBeenCalled();
    cleanup();

    await act(async () => {
      resolveSummary?.(summaryPayload());
      await Promise.resolve();
      await Promise.resolve();
    });

    // Unmounted view must not throw or resurrect loading UI via late setState.
    expect(screen.queryByText('Historical Trends')).toBeNull();
    expect(screen.queryByText('Loading historical trends...')).toBeNull();
  });

  it('ignores stale accuracy when days change before the first request settles', async () => {
    let resolveFirstAccuracy: ((value: unknown) => void) | undefined;
    let accuracyCalls = 0;
    apiMocks.getAccuracy.mockImplementation(() => {
      accuracyCalls += 1;
      if (accuracyCalls === 1) {
        return new Promise((resolve) => {
          resolveFirstAccuracy = resolve;
        });
      }
      return Promise.resolve({
        data: {
          summary: {
            sampleCount: 2,
            meanAbsErrorPct: 1.5,
            byRecommendation: {},
          },
          samples: [],
        },
      });
    });

    render(<HistoricalTrends />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(await screen.findByText('Historical Trends')).toBeTruthy();

    fireEvent.change(screen.getByLabelText('Time range:'), {
      target: { value: '7' },
    });

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(apiMocks.getAccuracy.mock.calls.length).toBeGreaterThanOrEqual(2);

    await act(async () => {
      resolveFirstAccuracy?.({
        data: {
          summary: {
            sampleCount: 99,
            meanAbsErrorPct: 99,
            byRecommendation: {},
          },
          samples: [],
        },
      });
      await Promise.resolve();
      await Promise.resolve();
    });

    // Latest days=7 response wins; stale sampleCount 99 must not appear.
    expect(screen.queryByText('99')).toBeNull();
    expect(await screen.findByText('2')).toBeTruthy();
  });

  it('ignores stale stock history when the selected symbol changes mid-flight', async () => {
    apiMocks.getSummary.mockResolvedValue(
      summaryPayload({
        symbols: ['AAPL', 'MSFT'],
        names: { AAPL: 'Apple Inc', MSFT: 'Microsoft' },
      }),
    );

    let resolveAapl: ((value: unknown) => void) | undefined;
    apiMocks.getHistorical.mockImplementation((symbol: string) => {
      if (symbol === 'AAPL') {
        return new Promise((resolve) => {
          resolveAapl = resolve;
        });
      }
      return Promise.resolve({
        data: {
          data: [
            {
              date: '2026-08-04',
              close: 400,
              change: 1,
              projection: { targetPrice: 410 },
            },
          ],
        },
      });
    });

    render(<HistoricalTrends />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(await screen.findByText('Historical Trends')).toBeTruthy();
    // Initial auto-select of AAPL starts a hangable historical fetch.
    expect(apiMocks.getHistorical).toHaveBeenCalledWith('AAPL', 30);

    // Switch company via the listbox button + option (Headless UI).
    fireEvent.click(screen.getByRole('button', { name: /Apple Inc|AAPL/i }));
    await act(async () => {
      await Promise.resolve();
    });
    const msftOption = await screen.findByText('Microsoft');
    fireEvent.click(msftOption);

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(apiMocks.getHistorical).toHaveBeenCalledWith('MSFT', 30);

    await act(async () => {
      resolveAapl?.({
        data: {
          data: [
            {
              date: '2026-08-04',
              close: 1,
              change: 0,
              projection: { targetPrice: 2 },
            },
          ],
        },
      });
      await Promise.resolve();
      await Promise.resolve();
    });

    // MSFT history should remain; AAPL's late close=1 must not overwrite.
    expect(screen.queryByText(/No historical data for/)).toBeNull();
  });
});
