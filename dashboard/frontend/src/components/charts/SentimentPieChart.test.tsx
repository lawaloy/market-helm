import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SentimentPieChart from './SentimentPieChart';

vi.mock('recharts', () => {
  const Passthrough = ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="recharts-stub">{children}</div>
  );
  return {
    ResponsiveContainer: Passthrough,
    PieChart: Passthrough,
    Pie: ({ data }: { data?: Array<{ name: string; value: number }> }) => (
      <ul data-testid="pie-slices">
        {(data ?? []).map((entry) => (
          <li key={entry.name}>
            {entry.name}:{entry.value}
          </li>
        ))}
      </ul>
    ),
    Cell: () => null,
    Legend: () => null,
    Tooltip: () => null,
  };
});

describe('SentimentPieChart dirty recommendation counts', () => {
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

  it('renders finite positive recommendation slices', () => {
    render(
      <SentimentPieChart
        recommendations={{
          STRONG_BUY: 3,
          BUY: 2,
          HOLD: 0,
          SELL: 1,
          STRONG_SELL: 0,
        }}
      />,
    );

    const slices = screen.getByTestId('pie-slices').textContent ?? '';
    expect(slices).toContain('STRONG BUY:3');
    expect(slices).toContain('BUY:2');
    expect(slices).toContain('SELL:1');
    expect(slices).not.toContain('HOLD:');
    expect(slices).not.toContain('STRONG SELL:');
  });

  it('omits NaN / ±Infinity / non-positive counts without throwing', () => {
    expect(() =>
      render(
        <SentimentPieChart
          recommendations={{
            STRONG_BUY: 4,
            BUY: Number.POSITIVE_INFINITY,
            HOLD: Number.NaN,
            SELL: Number.NEGATIVE_INFINITY,
            STRONG_SELL: -2,
          }}
        />,
      ),
    ).not.toThrow();

    const slices = screen.getByTestId('pie-slices').textContent ?? '';
    expect(slices).toBe('STRONG BUY:4');
  });
});
