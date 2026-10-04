import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it } from 'vitest';
import MarketPulseChart from './MarketPulseChart';
import type { StockMover } from '../../types';

const mover = (symbol: string, changePercent: number): StockMover => ({
  symbol,
  name: `${symbol} Company`,
  price: 100,
  change: changePercent,
  changePercent,
  volume: 1000,
});

describe('MarketPulseChart', () => {
  afterEach(cleanup);

  it('shows explicit daily moves and company-history links without a misleading connected line', () => {
    render(
      <MemoryRouter>
        <MarketPulseChart
          gainers={[mover('AAPL', 2), mover('MSFT', 4)]}
          losers={[mover('GOOGL', -3)]}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText('Biggest gainers')).toBeTruthy();
    expect(screen.getByText('Biggest decliners')).toBeTruthy();
    expect(screen.getByText('+4.00%')).toBeTruthy();
    expect(screen.getByText('-3.00%')).toBeTruthy();
    expect(
      screen
        .getByRole('link', { name: 'Explore MSFT Company history: +4.00% on this date' })
        .getAttribute('href'),
    ).toBe('/historical?symbol=MSFT');
    expect(document.querySelector('.recharts-wrapper')).toBeNull();
  });

  it('does not show invalid or wrong-direction rows as movers', () => {
    render(
      <MemoryRouter>
        <MarketPulseChart gainers={[mover('BAD', Number.NaN)]} losers={[mover('UP', 2)]} />
      </MemoryRouter>,
    );

    expect(screen.queryByText('BAD Company')).toBeNull();
    expect(screen.queryByText('UP Company')).toBeNull();
    expect(screen.getAllByText('None for this date.')).toHaveLength(2);
  });
});
