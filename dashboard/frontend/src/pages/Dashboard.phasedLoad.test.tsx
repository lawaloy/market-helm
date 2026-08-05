import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Dashboard from './Dashboard';
import type { MarketOverview, Opportunity, ProjectionsSummary } from '../types';

const apiMocks = vi.hoisted(() => ({
  getOverview: vi.fn(),
  getMovers: vi.fn(),
  getSummary: vi.fn(),
  getOpportunities: vi.fn(),
}));

vi.mock('../services/api', () => ({
  marketApi: {
    getOverview: apiMocks.getOverview,
    getMovers: apiMocks.getMovers,
  },
  projectionsApi: {
    getSummary: apiMocks.getSummary,
    getOpportunities: apiMocks.getOpportunities,
  },
}));

vi.mock('../components/cards/KPICard', () => ({
  default: ({ title, value }: { title: string; value: string | number }) => (
    <div data-testid={`kpi-${title}`}>{value}</div>
  ),
}));

vi.mock('../components/cards/OpportunityCard', () => ({
  default: ({ opportunity }: { opportunity: Opportunity }) => (
    <div data-testid={`opp-${opportunity.symbol}`}>{opportunity.symbol}</div>
  ),
}));

vi.mock('../components/charts/GainersLosersChart', () => ({
  default: () => <div data-testid="gainers-losers-chart" />,
}));

vi.mock('../components/charts/SentimentPieChart', () => ({
  default: () => <div data-testid="sentiment-pie-chart" />,
}));

vi.mock('../components/tables/StockTable', () => ({
  default: ({ stocks }: { stocks: Opportunity[] }) => (
    <div data-testid="stock-table">{stocks.map((s) => s.symbol).join(',')}</div>
  ),
}));

vi.mock('../components/modals/StockDetailModal', () => ({
  default: () => null,
}));

vi.mock('../components/common/ExportButton', () => ({
  default: () => <button type="button">Export</button>,
}));

function overview(date: string, totalStocks: number): MarketOverview {
  return {
    date,
    totalStocks,
    gainers: 1,
    losers: 1,
    unchanged: 0,
    averageChange: 0.5,
    maxChange: 2,
    minChange: -1,
    indices: {},
  };
}

function projectionsSummary(strongBuy = 2): ProjectionsSummary {
  return {
    date: '2026-08-05',
    targetDate: '2026-08-06',
    totalProjections: 10,
    averageConfidence: 72.5,
    expectedMarketMove: 1.2,
    sentiment: 'Bullish',
    recommendations: {
      STRONG_BUY: strongBuy,
      BUY: 3,
      HOLD: 4,
      SELL: 1,
      STRONG_SELL: 0,
    },
    trends: {},
    riskProfile: {},
  };
}

function opportunity(symbol: string): Opportunity {
  return {
    symbol,
    name: `${symbol} Inc`,
    currentPrice: 100,
    targetPrice: 110,
    expectedChange: 10,
    confidence: 80,
    risk: 'Low',
    recommendation: 'STRONG BUY',
    trend: 'Bullish',
    reason: 'momentum',
    volume: 1_000_000,
  };
}

function mockPhase1(date: string, totalStocks: number) {
  apiMocks.getOverview.mockResolvedValue({ data: overview(date, totalStocks) });
  apiMocks.getSummary.mockResolvedValue({ data: projectionsSummary() });
}

function mockPhase2Success(strongBuySymbol = 'AAPL') {
  apiMocks.getMovers.mockImplementation(async (type: string) => ({
    data: {
      type,
      data: [
        {
          symbol: type === 'gainers' ? 'GAIN' : 'LOSS',
          name: 'Mover',
          price: 10,
          change: type === 'gainers' ? 1 : -1,
          changePercent: type === 'gainers' ? 5 : -5,
          volume: 1000,
        },
      ],
    },
  }));
  apiMocks.getOpportunities.mockImplementation(async (type: string) => ({
    data: {
      type,
      count: type === 'STRONG_BUY' ? 1 : 0,
      opportunities: type === 'STRONG_BUY' ? [opportunity(strongBuySymbol)] : [],
    },
  }));
}

describe('Dashboard phased load and fetch races', () => {
  beforeEach(() => {
    mockPhase1('2026-08-05', 100);
    mockPhase2Success();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('shows a secondary error banner when phase 2 fails after phase 1 succeeds', async () => {
    apiMocks.getMovers.mockRejectedValue(new Error('movers down'));

    render(<Dashboard />);

    expect(
      await screen.findByText('Some sections failed to load. You can retry.'),
    ).toBeTruthy();
    expect(screen.getByTestId('kpi-Stocks Tracked').textContent).toBe('100');
    // Phase-1 KPIs stay up; phase-2 sections stay empty until Retry.
    expect(screen.getByTestId('stock-table').textContent).toBe('');
    expect(screen.queryByTestId('opp-AAPL')).toBeNull();

    mockPhase2Success('MSFT');
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));

    expect(await screen.findByTestId('opp-MSFT')).toBeTruthy();
    expect(screen.queryByText('Some sections failed to load. You can retry.')).toBeNull();
    expect(screen.getByTestId('stock-table').textContent).toContain('MSFT');
  });

  it('ignores a late phase-1 response after unmount', async () => {
    let resolveOverview: ((value: unknown) => void) | undefined;
    const onDataLoaded = vi.fn();
    apiMocks.getOverview.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveOverview = resolve;
        }),
    );

    render(<Dashboard onDataLoaded={onDataLoaded} />);
    await act(async () => {
      await Promise.resolve();
    });

    expect(apiMocks.getOverview).toHaveBeenCalled();
    cleanup();

    await act(async () => {
      resolveOverview?.({ data: overview('2026-08-05', 999) });
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(onDataLoaded).not.toHaveBeenCalled();
    expect(screen.queryByText('999')).toBeNull();
    expect(screen.queryByText('Loading dashboard...')).toBeNull();
  });

  it('ignores a slower refreshKey load when a newer refresh completes first', async () => {
    const onDataLoaded = vi.fn();
    mockPhase1('2026-08-05', 100);
    mockPhase2Success('AAPL');

    const view = render(
      <Dashboard refreshKey={0} onDataLoaded={onDataLoaded} />,
    );
    expect(await screen.findByTestId('kpi-Stocks Tracked')).toBeTruthy();
    expect(screen.getByTestId('kpi-Stocks Tracked').textContent).toBe('100');
    expect(await screen.findByTestId('opp-AAPL')).toBeTruthy();
    onDataLoaded.mockClear();

    let resolveStaleOverview: ((value: unknown) => void) | undefined;
    let resolveStaleSummary: ((value: unknown) => void) | undefined;
    let silentCalls = 0;

    apiMocks.getOverview.mockImplementation(() => {
      silentCalls += 1;
      if (silentCalls === 1) {
        return new Promise((resolve) => {
          resolveStaleOverview = resolve;
        });
      }
      return Promise.resolve({ data: overview('2026-08-07', 250) });
    });
    apiMocks.getSummary.mockImplementation(() => {
      if (silentCalls === 1) {
        return new Promise((resolve) => {
          resolveStaleSummary = resolve;
        });
      }
      return Promise.resolve({ data: projectionsSummary(7) });
    });
    mockPhase2Success('TSLA');

    // First silent refresh hangs in phase 1.
    view.rerender(<Dashboard refreshKey={1} onDataLoaded={onDataLoaded} />);
    await act(async () => {
      await Promise.resolve();
    });
    expect(silentCalls).toBe(1);

    // Second silent refresh completes while the first is still pending.
    view.rerender(<Dashboard refreshKey={2} onDataLoaded={onDataLoaded} />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(await screen.findByTestId('kpi-Stocks Tracked')).toBeTruthy();
    expect(screen.getByTestId('kpi-Stocks Tracked').textContent).toBe('250');
    expect(await screen.findByTestId('opp-TSLA')).toBeTruthy();

    await act(async () => {
      resolveStaleOverview?.({ data: overview('2026-08-01', 1) });
      resolveStaleSummary?.({ data: projectionsSummary(99) });
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.getByTestId('kpi-Stocks Tracked').textContent).toBe('250');
    expect(screen.queryByTestId('opp-AAPL')).toBeNull();
    expect(screen.getByTestId('opp-TSLA')).toBeTruthy();
    // Stale generation must not call onDataLoaded with the older overview date.
    expect(onDataLoaded).not.toHaveBeenCalledWith(
      expect.stringMatching(/August 1|2026-08-01|Aug 1/i),
    );
  });
});
