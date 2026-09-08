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
    expect(await screen.findByText('2')).toBeTruthy();
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

    expect(await screen.findByText('Historical Trends')).toBeTruthy();
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
  });
});
