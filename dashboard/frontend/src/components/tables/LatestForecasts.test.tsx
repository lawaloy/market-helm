import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Opportunity } from '../../types';
import LatestForecasts from './LatestForecasts';

const apiMocks = vi.hoisted(() => ({
  getSummary: vi.fn(),
  getOpportunities: vi.fn(),
}));

vi.mock('../../services/api', () => ({
  projectionsApi: apiMocks,
}));

vi.mock('./StockTable', () => ({
  default: ({
    stocks,
    asOfDate,
    onStockClick,
  }: {
    stocks: Opportunity[];
    asOfDate?: string;
    onStockClick: (symbol: string) => void;
  }) => (
    <div data-testid="forecast-table">
      {asOfDate}: {stocks.map((stock) => stock.symbol).join(',')}
      {stocks.map((stock) => (
        <button key={stock.symbol} type="button" onClick={() => onStockClick(stock.symbol)}>
          View {stock.symbol}
        </button>
      ))}
    </div>
  ),
}));

vi.mock('../modals/StockDetailModal', () => ({
  default: ({ symbol, onClose }: { symbol: string; onClose: () => void }) => (
    <div role="dialog" aria-label={`${symbol} details`}>
      <button type="button" onClick={onClose}>
        Close
      </button>
    </div>
  ),
}));

describe('LatestForecasts', () => {
  beforeEach(() => {
    apiMocks.getSummary.mockResolvedValue({ data: { date: '2026-10-02' } });
    apiMocks.getOpportunities.mockImplementation(async (type: string) => ({
      data: {
        opportunities:
          type === 'BUY' ? [{ symbol: 'AAPL', name: 'Apple', recommendation: 'BUY' }] : [],
      },
    }));
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('loads only after expansion and keeps stock details available in history', async () => {
    render(<LatestForecasts refreshKey={0} />);

    expect(apiMocks.getSummary).not.toHaveBeenCalled();
    expect(apiMocks.getOpportunities).not.toHaveBeenCalled();
    const toggle = screen.getByRole('button', { name: /Explore latest experimental forecasts/ });
    expect(toggle.getAttribute('aria-expanded')).toBe('false');

    fireEvent.click(toggle);
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    expect((await screen.findByTestId('forecast-table')).textContent).toContain('2026-10-02: AAPL');
    expect(apiMocks.getOpportunities).toHaveBeenCalledTimes(5);
    expect(apiMocks.getOpportunities).toHaveBeenCalledWith('BUY', 50);

    fireEvent.click(screen.getByRole('button', { name: 'View AAPL' }));
    expect(screen.getByRole('dialog', { name: 'AAPL details' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('shows an error and lets the user retry without leaving the page', async () => {
    apiMocks.getSummary.mockRejectedValueOnce(new Error('offline'));
    render(<LatestForecasts refreshKey={0} />);

    fireEvent.click(screen.getByRole('button', { name: /Explore latest experimental forecasts/ }));
    expect(await screen.findByRole('alert')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByTestId('forecast-table')).toBeTruthy();
    expect(apiMocks.getSummary).toHaveBeenCalledTimes(2);
  });
});
