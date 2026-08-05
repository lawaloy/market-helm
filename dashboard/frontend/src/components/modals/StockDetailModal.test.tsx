import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import StockDetailModal from './StockDetailModal';
import type { StockDetail } from '../../types';

const apiMocks = vi.hoisted(() => ({
  getDetail: vi.fn(),
}));

vi.mock('../../services/api', () => ({
  stocksApi: {
    getDetail: apiMocks.getDetail,
  },
}));

function detail(symbol: string, price: number): StockDetail {
  return {
    symbol,
    name: `${symbol} Corp`,
    currentData: {
      price,
      change: 1,
      changePercent: 0.5,
      volume: 1_000_000,
    },
  };
}

describe('StockDetailModal fetch races', () => {
  beforeEach(() => {
    apiMocks.getDetail.mockResolvedValue({ data: detail('AAPL', 150) });
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
    vi.clearAllMocks();
  });

  it('ignores a late response after unmount', async () => {
    let resolveDetail: ((value: unknown) => void) | undefined;
    apiMocks.getDetail.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveDetail = resolve;
        }),
    );

    render(<StockDetailModal symbol="AAPL" isOpen onClose={() => {}} />);
    await act(async () => {
      await Promise.resolve();
    });

    expect(apiMocks.getDetail).toHaveBeenCalledWith('AAPL');
    cleanup();

    await act(async () => {
      resolveDetail?.({ data: detail('AAPL', 150) });
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.queryByText(/AAPL/)).toBeNull();
    expect(screen.queryByText('Failed to load stock details')).toBeNull();
  });

  it('ignores a stale slower response when the symbol changes', async () => {
    let resolveAapl: ((value: unknown) => void) | undefined;
    let calls = 0;
    apiMocks.getDetail.mockImplementation((symbol: string) => {
      calls += 1;
      if (symbol === 'AAPL' && calls === 1) {
        return new Promise((resolve) => {
          resolveAapl = resolve;
        });
      }
      return Promise.resolve({ data: detail(symbol, 200) });
    });

    const { rerender } = render(
      <StockDetailModal symbol="AAPL" isOpen onClose={() => {}} />,
    );
    await act(async () => {
      await Promise.resolve();
    });

    rerender(<StockDetailModal symbol="MSFT" isOpen onClose={() => {}} />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(await screen.findByText(/MSFT/)).toBeTruthy();
    expect(screen.getByText('$200.00')).toBeTruthy();

    await act(async () => {
      resolveAapl?.({ data: detail('AAPL', 999) });
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.queryByText('$999.00')).toBeNull();
    expect(screen.getByText('$200.00')).toBeTruthy();
    expect(screen.getByText(/MSFT/)).toBeTruthy();
  });

  it('shows an error banner when the detail fetch fails', async () => {
    apiMocks.getDetail.mockRejectedValue(new Error('boom'));

    render(<StockDetailModal symbol="AAPL" isOpen onClose={() => {}} />);
    expect(await screen.findByText('Failed to load stock details')).toBeTruthy();
  });
});
