import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import GainersLosersChart from './GainersLosersChart';
import type { StockMover } from '../../types';

vi.mock('../common/CompanyLogo', () => ({
  default: ({ symbol }: { symbol: string }) => <span>{symbol}-logo</span>,
}));

vi.mock('recharts', () => {
  const Passthrough = ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="recharts-stub">{children}</div>
  );
  return {
    ResponsiveContainer: Passthrough,
    BarChart: Passthrough,
    Bar: Passthrough,
    XAxis: () => null,
    YAxis: () => null,
    CartesianGrid: () => null,
    Tooltip: () => null,
    Cell: () => null,
  };
});

function mover(symbol: string, changePercent: number | undefined): StockMover {
  return {
    symbol,
    name: `${symbol} Inc`,
    price: 10,
    change: 1,
    changePercent: changePercent as number,
    volume: 1_000_000,
  };
}

describe('GainersLosersChart dirty changePercent', () => {
  beforeEach(() => {
    if (typeof globalThis.ResizeObserver === 'undefined') {
      globalThis.ResizeObserver = class {
        observe() {}
        unobserve() {}
        disconnect() {}
      } as unknown as typeof ResizeObserver;
    }
  });

  afterEach(() => {
    cleanup();
  });

  it('renders finite mover percents in the legend list', () => {
    render(
      <GainersLosersChart
        gainers={[mover('AAPL', 1.5)]}
        losers={[mover('MSFT', -2)]}
      />,
    );

    expect(screen.getByText('+1.50%')).toBeTruthy();
    expect(screen.getByText('-2.00%')).toBeTruthy();
    expect(screen.getByText('AAPL')).toBeTruthy();
    expect(screen.getByText('MSFT')).toBeTruthy();
  });

  it('omits rows with missing or non-finite changePercent without throwing', () => {
    expect(() =>
      render(
        <GainersLosersChart
          gainers={[
            mover('GOOD', 3.25),
            mover('BAD', undefined),
            { ...mover('NAN', 0), changePercent: Number.NaN },
          ]}
          losers={[
            { ...mover('INF', 0), changePercent: Number.POSITIVE_INFINITY },
            mover('DROP', -1.1),
          ]}
        />,
      ),
    ).not.toThrow();

    expect(screen.getByText('+3.25%')).toBeTruthy();
    expect(screen.getByText('-1.10%')).toBeTruthy();
    expect(screen.queryByText('BAD')).toBeNull();
    expect(screen.queryByText('NAN')).toBeNull();
    expect(screen.queryByText('INF')).toBeNull();
  });

  it('backfills top-5 after dropping non-finite early movers', () => {
    const gainers = [
      { ...mover('POISON', 0), changePercent: Number.NaN },
      mover('G1', 5),
      mover('G2', 4),
      mover('G3', 3),
      mover('G4', 2),
      mover('G5', 1),
      mover('G6', 0.5),
    ];
    const losers = [
      { ...mover('INF', 0), changePercent: Number.POSITIVE_INFINITY },
      mover('L1', -5),
      mover('L2', -4),
      mover('L3', -3),
      mover('L4', -2),
      mover('L5', -1),
      mover('L6', -0.5),
    ];

    render(<GainersLosersChart gainers={gainers} losers={losers} />);

    expect(screen.getByText('G5')).toBeTruthy();
    expect(screen.getByText('+1.00%')).toBeTruthy();
    expect(screen.queryByText('G6')).toBeNull();
    expect(screen.getByText('L5')).toBeTruthy();
    expect(screen.getByText('-1.00%')).toBeTruthy();
    expect(screen.queryByText('L6')).toBeNull();
    expect(screen.queryByText('POISON')).toBeNull();
    expect(screen.queryByText('INF')).toBeNull();
  });
});

