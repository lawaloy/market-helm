import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Dashboard from './Dashboard';

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

vi.mock('../components/common/ExportButton', () => ({
  default: () => <button type="button">Export</button>,
}));

vi.mock('../components/charts/GainersLosersChart', () => ({
  default: ({
    gainers,
  }: {
    gainers: Array<{ symbol: string }>;
  }) => (
    <div data-testid="movers-chart">
      {gainers.map((g) => (
        <span key={g.symbol}>{g.symbol}</span>
      ))}
    </div>
  ),
}));

vi.mock('../components/charts/SentimentPieChart', () => ({
  default: () => <div data-testid="sentiment-chart" />,
}));

vi.mock('../components/tables/StockTable', () => ({
  default: ({ stocks }: { stocks: Array<{ symbol: string }> }) => (
    <div data-testid="stock-table">
      {stocks.map((s) => (
        <span key={s.symbol}>{s.symbol}-row</span>
      ))}
    </div>
  ),
}));

vi.mock('../components/cards/OpportunityCard', () => ({
  default: ({ opportunity }: { opportunity: { symbol: string } }) => (
    <div>{opportunity.symbol}-opp</div>
  ),
}));

vi.mock('../components/modals/StockDetailModal', () => ({
  default: () => null,
}));

vi.mock('../components/cards/KPICard', () => ({
  default: ({ title, value }: { title: string; value: string | number }) => (
    <div>
      <span>{title}</span>
      <span>{String(value)}</span>
    </div>
  ),
}));

const overview = {
  date: '2026-08-05',
  totalStocks: 10,
  gainers: 4,
  losers: 3,
  unchanged: 3,
  averageChange: 0.5,
  maxChange: 2,
  minChange: -1,
  indices: {},
};

const projections = {
  date: '2026-08-05',
  targetDate: '2026-08-06',
  totalProjections: 10,
  averageConfidence: 72.5,
  expectedMarketMove: 1.2,
  sentiment: 'Bullish',
  recommendations: { STRONG_BUY: 2, BUY: 3 },
  trends: {},
  riskProfile: {},
};

function opportunity(symbol: string) {
  return {
    symbol,
    name: `${symbol} Inc`,
    currentPrice: 100,
    targetPrice: 110,
    expectedChange: 10,
    confidence: 80,
    risk: 'Medium',
    recommendation: 'STRONG BUY',
    trend: 'Bullish',
    reason: 'momentum',
    volume: 1_000_000,
  };
}

function mockHappySecondary(gainerSymbol = 'AAPL') {
  apiMocks.getMovers.mockImplementation((type: string) =>
    Promise.resolve({
      data: {
        type,
        data:
          type === 'gainers'
            ? [
                {
                  symbol: gainerSymbol,
                  name: `${gainerSymbol} Inc`,
                  price: 1,
                  change: 1,
                  changePercent: 1,
                  volume: 1,
                },
              ]
            : [],
      },
    }),
  );
  apiMocks.getOpportunities.mockImplementation((type: string) =>
    Promise.resolve({
      data: {
        type,
        count: type === 'STRONG_BUY' ? 1 : 0,
        opportunities: type === 'STRONG_BUY' ? [opportunity(gainerSymbol)] : [],
      },
    }),
  );
}

describe('Dashboard phased load and races', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('keeps KPIs and shows secondary failure banner when phase 2 rejects', async () => {
    apiMocks.getOverview.mockResolvedValue({ data: overview });
    apiMocks.getSummary.mockResolvedValue({ data: projections });
    apiMocks.getMovers.mockRejectedValue(new Error('movers down'));
    apiMocks.getOpportunities.mockRejectedValue(new Error('opps down'));

    render(<Dashboard />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.getByText('Stocks Tracked')).toBeTruthy();
    expect(screen.getByText('10')).toBeTruthy();
    expect(screen.getByText('Some sections failed to load. You can retry.')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Retry' })).toBeTruthy();
  });

  it('ignores a late phase-1 response after unmount', async () => {
    let resolveOverview: ((value: unknown) => void) | undefined;
    apiMocks.getOverview.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveOverview = resolve;
        }),
    );
    apiMocks.getSummary.mockImplementation(
      () =>
        new Promise(() => {
          /* hang */
        }),
    );

    render(<Dashboard />);
    await act(async () => {
      await Promise.resolve();
    });

    cleanup();

    await act(async () => {
      resolveOverview?.({ data: overview });
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.queryByText('Stocks Tracked')).toBeNull();
    expect(screen.queryByText('Loading dashboard...')).toBeNull();
  });

  it('ignores superseded silent secondary data when refreshKey changes', async () => {
    let resolveFirstMovers: ((value: unknown) => void) | undefined;
    let call = 0;

    apiMocks.getOverview.mockResolvedValue({ data: overview });
    apiMocks.getSummary.mockResolvedValue({ data: projections });
    apiMocks.getOpportunities.mockResolvedValue({
      data: { type: 'STRONG_BUY', count: 0, opportunities: [] },
    });
    apiMocks.getMovers.mockImplementation((type: string) => {
      if (type !== 'gainers') {
        return Promise.resolve({ data: { type, data: [] } });
      }
      call += 1;
      if (call === 1) {
        return Promise.resolve({
          data: {
            type,
            data: [
              {
                symbol: 'INIT',
                name: 'Init',
                price: 1,
                change: 1,
                changePercent: 1,
                volume: 1,
              },
            ],
          },
        });
      }
      if (call === 2) {
        return new Promise((resolve) => {
          resolveFirstMovers = resolve;
        });
      }
      return Promise.resolve({
        data: {
          type,
          data: [
            {
              symbol: 'NEWEST',
              name: 'Newest',
              price: 1,
              change: 1,
              changePercent: 1,
              volume: 1,
            },
          ],
        },
      });
    });

    const { rerender } = render(<Dashboard refreshKey={0} />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByText('INIT')).toBeTruthy();

    rerender(<Dashboard refreshKey={1} />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    rerender(<Dashboard refreshKey={2} />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByText('NEWEST')).toBeTruthy();

    await act(async () => {
      resolveFirstMovers?.({
        data: {
          type: 'gainers',
          data: [
            {
              symbol: 'STALE',
              name: 'Stale',
              price: 1,
              change: 1,
              changePercent: 1,
              volume: 1,
            },
          ],
        },
      });
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.getByText('NEWEST')).toBeTruthy();
    expect(screen.queryByText('STALE')).toBeNull();
  });

  it('surfaces secondary failure during silent refresh after a prior success', async () => {
    apiMocks.getOverview.mockResolvedValue({ data: overview });
    apiMocks.getSummary.mockResolvedValue({ data: projections });
    mockHappySecondary('OK');

    const { rerender } = render(<Dashboard refreshKey={0} />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByText('OK')).toBeTruthy();
    expect(screen.queryByText('Some sections failed to load. You can retry.')).toBeNull();

    apiMocks.getMovers.mockRejectedValue(new Error('silent secondary fail'));
    apiMocks.getOpportunities.mockRejectedValue(new Error('silent secondary fail'));

    rerender(<Dashboard refreshKey={1} />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.getByText('Some sections failed to load. You can retry.')).toBeTruthy();
  });
});
