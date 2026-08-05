import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SentimentPieChart, {
  colorForRecommendation,
  formatSliceLabel,
} from './SentimentPieChart';

vi.mock('recharts', () => {
  const Passthrough = ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="recharts-stub">{children}</div>
  );
  return {
    ResponsiveContainer: Passthrough,
    PieChart: Passthrough,
    Pie: ({
      data,
      label,
      children,
    }: {
      data?: Array<{ name: string; value: number }>;
      label?: (props: { name: string; percent: number }) => string;
      children?: React.ReactNode;
    }) => (
      <div>
        <ul data-testid="pie-slices">
          {(data ?? []).map((entry) => (
            <li key={entry.name}>
              {entry.name}:{entry.value}
            </li>
          ))}
        </ul>
        <ul data-testid="pie-labels">
          {(data ?? []).map((entry, _index, all) => {
            const total = all.reduce((sum, row) => sum + row.value, 0);
            const percent = total > 0 ? entry.value / total : Number.NaN;
            return (
              <li key={`label-${entry.name}`}>
                {label ? label({ name: entry.name, percent }) : ''}
              </li>
            );
          })}
        </ul>
        {children}
      </div>
    ),
    Cell: ({ fill }: { fill?: string }) => (
      <span data-testid="pie-cell" data-fill={fill ?? ''} />
    ),
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

  it('formats finite slice percents and soft-fails NaN percent', () => {
    expect(formatSliceLabel('BUY', 0.25)).toBe('BUY: 25.0%');
    expect(formatSliceLabel('HOLD', Number.NaN)).toBe('HOLD: 0.0%');
    expect(formatSliceLabel('SELL', undefined)).toBe('SELL: 0.0%');
  });

  it('maps known recommendation colors and falls back for unknown keys', () => {
    expect(colorForRecommendation('STRONG BUY')).toBe('#10B981');
    expect(colorForRecommendation('WEIRD')).toBe('#94A3B8');
  });

  it('renders labels and cell fills for known and unknown keys', () => {
    render(
      <SentimentPieChart
        recommendations={{
          BUY: 1,
          CUSTOM_REC: 1,
        }}
      />,
    );

    const labels = screen.getByTestId('pie-labels').textContent ?? '';
    expect(labels).toContain('BUY: 50.0%');
    expect(labels).toContain('CUSTOM REC: 50.0%');

    const fills = screen.getAllByTestId('pie-cell').map((el) => el.getAttribute('data-fill'));
    expect(fills).toContain('#34D399');
    expect(fills).toContain('#94A3B8');
  });
});
