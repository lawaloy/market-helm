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
    const table = screen.getByRole('table');

    expect(within(table).getByText('AAPL')).toBeTruthy();
    expect(within(table).getByText('MSFT')).toBeTruthy();
    expect(within(table).getByText('TSLA')).toBeTruthy();

    // Badge column shows recommendation (BUY/HOLD/SELL), not trend.
    expect(within(table).getByText('STRONG BUY')).toBeTruthy();
    expect(within(table).getByText('HOLD')).toBeTruthy();
    expect(within(table).getByText('SELL')).toBeTruthy();
    expect(screen.queryByText('Bullish')).toBeNull();

    const filter = screen.getByDisplayValue('All');
    fireEvent.change(filter, { target: { value: 'BUY' } });

    expect(within(table).getByText('AAPL')).toBeTruthy();
    expect(within(table).queryByText('MSFT')).toBeNull();
    expect(within(table).queryByText('TSLA')).toBeNull();

    fireEvent.change(filter, { target: { value: 'HOLD' } });
    expect(within(table).getByText('MSFT')).toBeTruthy();
    expect(within(table).queryByText('AAPL')).toBeNull();

    fireEvent.change(filter, { target: { value: 'SELL' } });
    expect(within(table).getByText('TSLA')).toBeTruthy();
    expect(within(table).queryByText('MSFT')).toBeNull();
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

describe('StockTable non-finite display and pagination clamp', () => {
  afterEach(() => {
    cleanup();
  });

  it('soft-fails Infinity / NaN confidence and expectedChange cells', () => {
    render(
      <StockTable
        stocks={[
          opportunity({
            symbol: 'BAD',
            confidence: Number.POSITIVE_INFINITY,
            expectedChange: Number.NaN,
          }),
        ]}
      />,
    );

    const table = screen.getByRole('table');
    expect(within(table).getAllByText('—').length).toBeGreaterThanOrEqual(2);
    expect(table.textContent).not.toMatch(/Infinity|NaN/);
  });

  it('soft-fails Infinity / NaN prices and skips non-string symbols', () => {
    render(
      <StockTable
        stocks={[
          opportunity({
            symbol: 'OK',
            currentPrice: Number.POSITIVE_INFINITY,
            targetPrice: Number.NaN,
          }),
          // Dirty API rows previously threw on symbol.toLowerCase() during search.
          opportunity({
            symbol: null as unknown as string,
            name: 'Poison',
          }),
        ]}
      />,
    );

    const table = screen.getByRole('table');
    expect(within(table).getByText('OK')).toBeTruthy();
    expect(within(table).queryByText('Poison')).toBeNull();
    expect(table.textContent).not.toMatch(/\$∞|\$NaN|Infinity|NaN/);
    expect(screen.queryByRole('searchbox')).toBeNull();
  });

  it('clamps to page 1 when a filter shrinks results below the current page', () => {
    const stocks = Array.from({ length: 21 }, (_, i) =>
      opportunity({
        symbol: `S${String(i).padStart(2, '0')}`,
        name: `Stock ${i}`,
        recommendation: i === 0 ? 'BUY' : 'HOLD',
      }),
    );

    render(<StockTable stocks={stocks} />);

    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getByText('Page 2 of 2')).toBeTruthy();
    expect(within(screen.getByRole('table')).getByText('S20')).toBeTruthy();

    fireEvent.change(screen.getByDisplayValue('All'), {
      target: { value: 'BUY' },
    });

    expect(within(screen.getByRole('table')).getByText('S00')).toBeTruthy();
    expect(screen.queryByText('Page 2 of')).toBeNull();
  });
});

describe('Stock forecasts experience', () => {
  afterEach(cleanup);

  it('explains the forecast purpose, date, and unvalidated score without a list search', () => {
    render(<StockTable stocks={[opportunity({})]} asOfDate="2026-10-02" />);

    expect(screen.getByRole('heading', { name: 'Stock forecasts' })).toBeTruthy();
    expect(screen.getByText(/1 stock · Oct 2, 2026/)).toBeTruthy();
    expect(screen.getByText(/Accuracy has not been established/)).toBeTruthy();
    expect(screen.getByText(/not measured probabilities/)).toBeTruthy();
    expect(screen.queryByText('Why are these stocks here?')).toBeNull();
    expect(screen.queryByRole('searchbox')).toBeNull();
    expect(
      within(screen.getByRole('table')).getByRole('columnheader', { name: 'Forecast change' }),
    ).toBeTruthy();
  });

  it('sorts by forecast change and opens the chosen company details', () => {
    const onStockClick = vi.fn();
    render(
      <StockTable
        stocks={[
          opportunity({ symbol: 'LOW', name: 'Low Co', expectedChange: -3 }),
          opportunity({ symbol: 'HIGH', name: 'High Co', expectedChange: 8 }),
        ]}
        onStockClick={onStockClick}
      />,
    );

    fireEvent.change(screen.getByRole('combobox', { name: 'Sort by' }), {
      target: { value: 'change' },
    });
    const rows = within(screen.getByRole('table')).getAllByRole('row');
    expect(rows[1].textContent).toContain('HIGH');
    expect(rows[2].textContent).toContain('LOW');

    fireEvent.click(
      within(screen.getByRole('table')).getByRole('button', { name: /View details for High Co/ }),
    );
    expect(onStockClick).toHaveBeenCalledWith('HIGH');
    fireEvent.click(screen.getAllByRole('button', { name: /View details for Low Co/ })[0]);
    expect(onStockClick).toHaveBeenCalledWith('LOW');
  });

  it('gives a useful empty state for missing data and unmatched recommendations', () => {
    const { rerender } = render(<StockTable stocks={[]} />);
    expect(screen.getByText(/No stock forecasts are available yet/)).toBeTruthy();

    rerender(<StockTable stocks={[opportunity({})]} />);
    fireEvent.change(screen.getByRole('combobox', { name: 'Recommendation' }), {
      target: { value: 'SELL' },
    });
    expect(screen.getByText(/No forecasts match that recommendation/)).toBeTruthy();
  });
});
