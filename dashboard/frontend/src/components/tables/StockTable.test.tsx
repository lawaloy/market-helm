import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import StockTable from './StockTable';
import type { Opportunity } from '../../types';

vi.mock('../common/CompanyLogo', () => ({
  default: ({ symbol }: { symbol: string }) => <span data-testid={`logo-${symbol}`} />,
}));

vi.mock('../common/ExportButton', () => ({
  default: () => <button type="button">Export</button>,
}));

function opportunity(overrides: Partial<Opportunity>): Opportunity {
  return {
    symbol: 'AAPL',
    name: 'Apple',
    currentPrice: 150,
    targetPrice: 160,
    expectedChange: 6.5,
    confidence: 80,
    risk: 'Low',
    recommendation: 'BUY',
    trend: 'Bullish',
    reason: 'demo',
    volume: 1_000_000,
    ...overrides,
  };
}

describe('StockTable recommendation filter', () => {
  afterEach(() => {
    cleanup();
  });

  const stocks: Opportunity[] = [
    opportunity({
      symbol: 'AAPL',
      recommendation: 'STRONG BUY',
      trend: 'Bullish',
    }),
    opportunity({
      symbol: 'MSFT',
      recommendation: 'HOLD',
      trend: 'Neutral',
    }),
    opportunity({
      symbol: 'TSLA',
      recommendation: 'SELL',
      trend: 'Bearish',
    }),
  ];

  it('filters by recommendation rating, not Bullish/Bearish trend', () => {
    render(<StockTable stocks={stocks} />);

    expect(screen.getByText('AAPL')).toBeTruthy();
    expect(screen.getByText('MSFT')).toBeTruthy();
    expect(screen.getByText('TSLA')).toBeTruthy();

    // Badge column shows recommendation (BUY/HOLD/SELL), not trend.
    expect(screen.getByText('STRONG BUY')).toBeTruthy();
    expect(screen.getByText('HOLD')).toBeTruthy();
    expect(screen.getByText('SELL')).toBeTruthy();
    expect(screen.queryByText('Bullish')).toBeNull();

    const filter = screen.getByDisplayValue('All');
    fireEvent.change(filter, { target: { value: 'BUY' } });

    expect(screen.getByText('AAPL')).toBeTruthy();
    expect(screen.queryByText('MSFT')).toBeNull();
    expect(screen.queryByText('TSLA')).toBeNull();

    fireEvent.change(filter, { target: { value: 'HOLD' } });
    expect(screen.getByText('MSFT')).toBeTruthy();
    expect(screen.queryByText('AAPL')).toBeNull();

    fireEvent.change(filter, { target: { value: 'SELL' } });
    expect(screen.getByText('TSLA')).toBeTruthy();
    expect(screen.queryByText('MSFT')).toBeNull();
  });

  it('treats STRONG SELL as part of the Sell filter bucket', () => {
    render(
      <StockTable
        stocks={[
          opportunity({
            symbol: 'WEAK',
            recommendation: 'STRONG SELL',
            trend: 'Bearish',
          }),
          opportunity({
            symbol: 'KEEP',
            recommendation: 'BUY',
            trend: 'Bullish',
          }),
        ]}
      />,
    );

    fireEvent.change(screen.getByDisplayValue('All'), {
      target: { value: 'SELL' },
    });

    const table = screen.getByRole('table');
    expect(within(table).getByText('WEAK')).toBeTruthy();
    expect(within(table).queryByText('KEEP')).toBeNull();
  });

  it('does not match Buy filter against Bullish trend alone', () => {
    render(
      <StockTable
        stocks={[
          opportunity({
            symbol: 'FAKE',
            recommendation: 'HOLD',
            trend: 'Bullish',
          }),
        ]}
      />,
    );

    fireEvent.change(screen.getByDisplayValue('All'), {
      target: { value: 'BUY' },
    });

    expect(screen.queryByText('FAKE')).toBeNull();
  });
});
