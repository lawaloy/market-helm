import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Dashboard from './Dashboard';
import type { MarketOverview, StockMover } from '../types';

const apiMocks = vi.hoisted(() => ({
  getOverview: vi.fn(),
  getMovers: vi.fn(),
}));

vi.mock('../services/api', () => ({
  marketApi: {
    getOverview: apiMocks.getOverview,
    getMovers: apiMocks.getMovers,
  },
}));

vi.mock('../components/cards/KPICard', () => ({
  default: ({ title, value }: { title: string; value: string | number }) => (
    <div data-testid={`kpi-${title}`}>{value}</div>
  ),
}));

vi.mock('../components/charts/MarketPulseChart', () => ({
  default: ({ gainers, losers }: { gainers: StockMover[]; losers: StockMover[] }) => (
    <div data-testid="market-pulse">
      {[...gainers, ...losers].map((stock) => stock.symbol).join(',')}
    </div>
  ),
}));

vi.mock('../components/cards/ForecastPreview', () => ({
  default: ({ date }: { date: string }) => (
    <section data-testid="forecast-preview">Forecast preview for {date}</section>
  ),
}));

vi.mock('../components/common/ExportButton', () => ({
  default: () => <button type="button">Export</button>,
}));

vi.mock('./Summary', () => ({
  default: () => <section data-testid="market-brief">Market brief</section>,
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

function mockPhase1(date: string, totalStocks: number) {
  apiMocks.getOverview.mockResolvedValue({ data: overview(date, totalStocks) });
}

function mockPhase2Success(gainerSymbol = 'GAIN') {
  apiMocks.getMovers.mockImplementation(async (type: string) => ({
    data: {
      type,
      data: [
        {
          symbol: type === 'gainers' ? gainerSymbol : 'LOSS',
          name: 'Mover',
          price: 10,
          change: type === 'gainers' ? 1 : -1,
          changePercent: type === 'gainers' ? 5 : -5,
          volume: 1000,
        },
      ],
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

    expect(await screen.findByText('Some sections failed to load. You can retry.')).toBeTruthy();
    expect(screen.getByTestId('kpi-Stocks covered').textContent).toBe('100');
    // Phase-1 observed metrics stay up; phase-2 chart stays empty until Retry.
    expect(screen.getByTestId('market-pulse').textContent).toBe('');

    mockPhase2Success('MSFT');
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));

    expect(await screen.findByText('MSFT,LOSS')).toBeTruthy();
    expect(screen.queryByText('Some sections failed to load. You can retry.')).toBeNull();
  });

  it('shows a dated forecast preview without restoring unsupported rankings', async () => {
    render(<Dashboard />);

    expect(await screen.findByTestId('market-pulse')).toBeTruthy();
    expect(screen.getByTestId('kpi-Stocks covered').textContent).toBe('100');
    expect(screen.getByTestId('forecast-preview').textContent).toContain('2026-08-05');
    expect(screen.queryByRole('heading', { name: 'Top opportunity' })).toBeNull();
  });
  it('ignores a late phase-1 response after unmount', async () => {
    let resolveOverview: ((value: unknown) => void) | undefined;
    apiMocks.getOverview.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveOverview = resolve;
        }),
    );

    render(<Dashboard />);
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
    expect(screen.queryByText('999')).toBeNull();
    expect(screen.queryByText('Loading dashboard...')).toBeNull();
  });

  it('ignores a slower refreshKey load when a newer refresh completes first', async () => {
    mockPhase1('2026-08-05', 100);
    mockPhase2Success('AAPL');

    const view = render(<Dashboard refreshKey={0} />);
    expect(await screen.findByTestId('kpi-Stocks covered')).toBeTruthy();
    expect(screen.getByTestId('kpi-Stocks covered').textContent).toBe('100');
    expect(await screen.findByText('AAPL,LOSS')).toBeTruthy();

    let resolveStaleOverview: ((value: unknown) => void) | undefined;
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
    mockPhase2Success('TSLA');

    // First silent refresh hangs in phase 1.
    view.rerender(<Dashboard refreshKey={1} />);
    await act(async () => {
      await Promise.resolve();
    });
    expect(silentCalls).toBe(1);

    // Second silent refresh completes while the first is still pending.
    view.rerender(<Dashboard refreshKey={2} />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(await screen.findByTestId('kpi-Stocks covered')).toBeTruthy();
    expect(screen.getByTestId('kpi-Stocks covered').textContent).toBe('250');
    expect(await screen.findByText('TSLA,LOSS')).toBeTruthy();

    await act(async () => {
      resolveStaleOverview?.({ data: overview('2026-08-01', 1) });
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.getByTestId('kpi-Stocks covered').textContent).toBe('250');
    expect(screen.queryByText('AAPL,LOSS')).toBeNull();
    expect(screen.getByTestId('market-pulse').textContent).toBe('TSLA,LOSS');
  });
});
