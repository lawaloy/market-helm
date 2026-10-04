import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import HistoricalTrends from './HistoricalTrends';

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

vi.stubGlobal('ResizeObserver', ResizeObserverMock);

vi.mock('../contexts/ThemeContext', () => ({
  useTheme: () => ({ theme: 'dark', toggleTheme: vi.fn() }),
}));

const apiMocks = vi.hoisted(() => ({
  getSummary: vi.fn(),
  getAccuracy: vi.fn(),
  getRunProjections: vi.fn(),
  getHistorical: vi.fn(),
}));

vi.mock('../services/api', () => ({
  historyApi: {
    getSummary: apiMocks.getSummary,
    getAccuracy: apiMocks.getAccuracy,
    getRunProjections: apiMocks.getRunProjections,
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

function accuracyPayload(
  summaryOverrides: Record<string, unknown> = {},
  samples: Array<Record<string, unknown>> = [],
  samplesTruncated = false,
) {
  return {
    data: {
      summary: {
        schemaVersion: 1,
        calendar: 'XNYS',
        horizonSessions: 5,
        projectionCount: 0,
        validProjectionCount: 0,
        sampleCount: 0,
        invalidCount: 0,
        pendingCount: 0,
        missingActualCount: 0,
        evaluationCoveragePct: null,
        meanAbsErrorPct: null,
        medianAbsErrorPct: null,
        directionalAccuracyPct: null,
        bandCoveragePct: null,
        meanConfidence: null,
        calibrationGapPct: null,
        byRecommendation: {},
        byConfidenceBand: {},
        ...summaryOverrides,
      },
      samples,
      samplesTruncated,
    },
  };
}

describe('HistoricalTrends fetch races', () => {
  beforeEach(() => {
    apiMocks.getSummary.mockResolvedValue(summaryPayload());
    apiMocks.getAccuracy.mockResolvedValue(accuracyPayload());
    apiMocks.getRunProjections.mockResolvedValue({
      data: { date: '2026-08-04', totalProjections: 0, projections: [] },
    });
    apiMocks.getHistorical.mockResolvedValue({ data: { data: [] } });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    window.history.replaceState({}, '', '/');
  });

  it('opens a company directly from the dashboard forecast preview', async () => {
    window.history.replaceState({}, '', '/historical?symbol=AAPL');
    render(<HistoricalTrends />);

    expect(await screen.findByRole('heading', { name: 'Apple Inc history' })).toBeTruthy();
    expect(apiMocks.getHistorical).toHaveBeenCalledWith('AAPL', 30);
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
    expect(screen.queryByText('Market history')).toBeNull();
    expect(screen.queryByText('Loading market history...')).toBeNull();
  });

  it('shows an accessible run record instead of misleading one-point charts', async () => {
    render(<HistoricalTrends />);

    expect(await screen.findByRole('heading', { name: 'Market history' })).toBeTruthy();
    expect(screen.getByText('Most recent')).toBeTruthy();
    expect(screen.getAllByText('70.0%').length).toBeGreaterThan(0);
    expect(screen.getAllByText('+1.20%').length).toBeGreaterThan(0);
    expect(document.querySelector('.recharts-wrapper')).toBeNull();
  });

  it('shows a timeline record when a company has only one recorded session', async () => {
    apiMocks.getHistorical.mockResolvedValue({
      data: {
        data: [
          {
            date: '2026-08-04',
            close: 100,
            change: 1,
            projection: { targetPrice: 105 },
          },
        ],
      },
    });

    render(<HistoricalTrends />);

    await screen.findByRole('heading', { name: 'Market history' });
    fireEvent.click(screen.getByRole('button', { name: 'Company' }));
    fireEvent.click(await screen.findByText('Apple Inc (AAPL)'));

    expect(await screen.findByText('$100.00')).toBeTruthy();
    expect(screen.getByText('$105.00')).toBeTruthy();
    expect(screen.getByText('Most recent')).toBeTruthy();
  });

  it('opens company figure details and loads the saved target range only when needed', async () => {
    apiMocks.getHistorical.mockResolvedValue({
      data: {
        data: [
          {
            date: '2026-08-04',
            close: 100,
            change: 1,
            volume: 1000,
            projection: { targetPrice: 105, recommendation: 'BUY', confidence: 70 },
          },
        ],
      },
    });
    apiMocks.getRunProjections.mockResolvedValue({
      data: {
        date: '2026-08-04',
        totalProjections: 1,
        projections: [
          {
            symbol: 'AAPL',
            name: 'Apple Inc',
            recommendation: 'BUY',
            confidence: 70,
            expectedChange: 5,
            currentPrice: 100,
            targetPrice: 105,
            targetLow: 102,
            targetHigh: 108,
            risk: 'Low',
            reason: 'Saved evidence for this call.',
          },
        ],
      },
    });

    render(<HistoricalTrends />);
    await screen.findByRole('heading', { name: 'Market history' });
    fireEvent.click(screen.getByRole('button', { name: 'Company' }));
    fireEvent.click(await screen.findByText('Apple Inc (AAPL)'));
    await screen.findByRole('button', { name: 'View closing price details: $100.00' });

    fireEvent.click(screen.getByRole('button', { name: 'View closing price details: $100.00' }));
    expect(screen.getByText(/Volume: 1,000/)).toBeTruthy();
    expect(apiMocks.getRunProjections).not.toHaveBeenCalled();

    fireEvent.click(
      screen.getByRole('button', { name: 'View 5-trading-day target details: $105.00' }),
    );
    const target = await screen.findByRole('region', { name: 'target details for Aug 4, 2026' });
    expect(target.textContent).toContain('Saved target range: $102.00 to $108.00');
    expect(target.textContent).toContain('Saved evidence for this call.');
    expect(apiMocks.getRunProjections).toHaveBeenCalledExactlyOnceWith('2026-08-04');
  });

  it('opens the saved companies behind a count and filters a recommendation bucket', async () => {
    apiMocks.getSummary.mockResolvedValue(
      summaryPayload({
        data: [
          {
            date: '2026-08-04',
            totalProjections: 3,
            averageConfidence: 70,
            expectedMarketMove: 1.2,
            sentiment: 'Bullish',
            strongBuy: 0,
            buy: 1,
            hold: 1,
            sell: 1,
            strongSell: 0,
          },
        ],
        symbols: ['AAPL', 'MSFT', 'GOOGL'],
        names: { AAPL: 'Apple Inc', MSFT: 'Microsoft', GOOGL: 'Alphabet' },
      }),
    );
    apiMocks.getRunProjections.mockResolvedValue({
      data: {
        date: '2026-08-04',
        totalProjections: 3,
        projections: [
          {
            symbol: 'AAPL',
            name: 'Apple Inc',
            recommendation: 'BUY',
            confidence: 75,
            expectedChange: 2,
            currentPrice: 100,
            targetPrice: 102,
            risk: 'Low',
            reason: 'Momentum',
          },
          {
            symbol: 'MSFT',
            name: 'Microsoft',
            recommendation: 'HOLD',
            confidence: 70,
            expectedChange: 0,
            currentPrice: 200,
            targetPrice: 200,
            risk: 'Low',
            reason: '',
          },
          {
            symbol: 'GOOGL',
            name: 'Alphabet',
            recommendation: 'SELL',
            confidence: 65,
            expectedChange: -1,
            currentPrice: 300,
            targetPrice: 297,
            risk: 'Medium',
            reason: '',
          },
        ],
      },
    });

    render(<HistoricalTrends />);
    await screen.findByRole('heading', { name: 'Market history' });
    fireEvent.click(screen.getByRole('button', { name: '3 stocks · View companies' }));
    expect(
      await screen.findByRole('region', { name: 'Companies on this date for Aug 4, 2026' }),
    ).toBeTruthy();
    expect(screen.getByText(/Apple Inc/)).toBeTruthy();
    expect(screen.getByText(/Microsoft/)).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'View 1 buy companies from Aug 4, 2026' }));
    const filtered = await screen.findByRole('region', { name: 'buy calls for Aug 4, 2026' });
    expect(filtered.textContent).toContain('Apple Inc');
    expect(filtered.textContent).not.toContain('Microsoft');
    expect(filtered.textContent).not.toContain('Alphabet');
    expect(apiMocks.getRunProjections).toHaveBeenCalledWith('2026-08-04');
    expect(apiMocks.getRunProjections).toHaveBeenCalledTimes(1);
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
      return Promise.resolve(
        accuracyPayload({
          projectionCount: 2,
          validProjectionCount: 2,
          sampleCount: 2,
          evaluationCoveragePct: 100,
          meanAbsErrorPct: 1.5,
        }),
      );
    });

    render(<HistoricalTrends />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(await screen.findByText('Market history')).toBeTruthy();

    fireEvent.change(screen.getByLabelText('Time range:'), {
      target: { value: '7' },
    });

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(apiMocks.getAccuracy.mock.calls.length).toBeGreaterThanOrEqual(2);

    await act(async () => {
      resolveFirstAccuracy?.(
        accuracyPayload({
          projectionCount: 99,
          validProjectionCount: 99,
          sampleCount: 99,
          evaluationCoveragePct: 100,
          meanAbsErrorPct: 99,
        }),
      );
      await Promise.resolve();
      await Promise.resolve();
    });

    // Latest days=7 response wins; stale sampleCount 99 must not appear.
    expect(screen.queryByText('99')).toBeNull();
    const scoredProjections = await screen.findByText('Scored projections');
    expect(scoredProjections.parentElement?.textContent).toContain('2');
  });

  it('ignores stale stock history when days change mid-flight', async () => {
    let resolveFirstHistory: ((value: unknown) => void) | undefined;
    let historyCalls = 0;
    apiMocks.getHistorical.mockImplementation(() => {
      historyCalls += 1;
      if (historyCalls === 1) {
        return new Promise((resolve) => {
          resolveFirstHistory = resolve;
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

    expect(await screen.findByText('Market history')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Company' }));
    fireEvent.click(await screen.findByText('Apple Inc (AAPL)'));

    expect(apiMocks.getHistorical).toHaveBeenCalledWith('AAPL', 30);

    fireEvent.change(screen.getByLabelText('Time range:'), {
      target: { value: '7' },
    });

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(apiMocks.getHistorical).toHaveBeenCalledWith('AAPL', 7);

    await act(async () => {
      resolveFirstHistory?.({
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

    // Latest days=7 history wins; stale empty/error path must not stick.
    expect(screen.queryByText(/No historical data for/)).toBeNull();
    expect(apiMocks.getHistorical.mock.calls.some((c) => c[0] === 'AAPL' && c[1] === 7)).toBe(true);
  });

  it('renders exact-session validation metrics and sample outcomes', async () => {
    apiMocks.getAccuracy.mockResolvedValue(
      accuracyPayload(
        {
          projectionCount: 5,
          validProjectionCount: 5,
          sampleCount: 2,
          pendingCount: 1,
          missingActualCount: 2,
          evaluationCoveragePct: 50,
          meanAbsErrorPct: 2.5,
          medianAbsErrorPct: 2.5,
          directionalAccuracyPct: 60,
          bandCoveragePct: 80,
          meanConfidence: 65,
          calibrationGapPct: 5,
          byRecommendation: {
            BUY: {
              count: 1,
              meanAbsErrorPct: 2.5,
              medianAbsErrorPct: 2.5,
              directionalAccuracyPct: 100,
              bandCoveragePct: 100,
              meanConfidence: 70,
              calibrationGapPct: -30,
            },
          },
          byConfidenceBand: {
            '70-79': {
              count: 1,
              meanAbsErrorPct: 2.5,
              medianAbsErrorPct: 2.5,
              directionalAccuracyPct: 100,
              bandCoveragePct: 100,
              meanConfidence: 70,
              calibrationGapPct: -30,
            },
          },
        },
        [
          {
            symbol: 'AAPL',
            runDate: '2026-07-02',
            targetDate: '2026-07-10',
            actualDate: '2026-07-10',
            current: 100,
            predicted: 110,
            actual: 108,
            absErrorPct: 1.852,
            signedErrorPct: 1.852,
            directionCorrect: true,
            bandHit: true,
            confidence: 70,
            confidenceBand: '70-79',
            recommendation: 'BUY',
          },
        ],
        true,
      ),
    );

    render(<HistoricalTrends />);

    expect(await screen.findByText('Directional accuracy')).toBeTruthy();
    expect(screen.getByText('60.00%')).toBeTruthy();
    expect(screen.getByText('80.00%')).toBeTruthy();
    expect(screen.getByText('50.00%')).toBeTruthy();
    expect(screen.getByText('5.00%')).toBeTruthy();
    expect(screen.getByText('Confidence calibration by cohort')).toBeTruthy();
    expect(screen.getByText('Recent scores (newest 1 of 2)')).toBeTruthy();
    expect(screen.getByText('Correct')).toBeTruthy();
    expect(screen.getByText('Hit')).toBeTruthy();
    fireEvent.click(
      screen.getByRole('button', { name: 'View directional accuracy details: 60.00%' }),
    );
    expect(
      screen.getByRole('region', { name: 'Directional accuracy details' }).textContent,
    ).toContain('correctly predicted');
  });
});
