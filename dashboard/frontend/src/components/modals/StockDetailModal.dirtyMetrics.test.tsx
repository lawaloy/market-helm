import { cleanup, render, screen } from '@testing-library/react';
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

function detail(overrides: Partial<StockDetail> = {}): StockDetail {
  return {
    symbol: 'AAPL',
    name: 'AAPL Corp',
    currentData: {
      price: 150,
      change: 1,
      changePercent: 0.5,
      volume: 1_000_000,
    },
    projection: {
      targetDate: '2026-08-10',
      targetPrice: 160,
      expectedChange: 6.6,
      confidence: 72,
      recommendation: 'BUY',
      risk: 'Medium',
      trend: 'Bullish',
    },
    technical: {
      momentum: 12.3,
      volatility: 4.5,
    },
    ...overrides,
  };
}

describe('StockDetailModal dirty technical metrics', () => {
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
    vi.clearAllMocks();
  });

  it('renders finite momentum and volatility', async () => {
    apiMocks.getDetail.mockResolvedValue({ data: detail() });

    render(<StockDetailModal symbol="AAPL" isOpen onClose={() => {}} />);

    expect(await screen.findByText('12.3')).toBeTruthy();
    expect(screen.getByText('4.5%')).toBeTruthy();
    expect(screen.getByText('Confidence: 72%')).toBeTruthy();
  });

  it('omits null technical metrics without throwing', async () => {
    apiMocks.getDetail.mockResolvedValue({
      data: detail({
        technical: {
          // Backend _finite_float may serialize dirty scores as null.
          momentum: null as unknown as number,
          volatility: null as unknown as number,
        },
      }),
    });

    render(<StockDetailModal symbol="AAPL" isOpen onClose={() => {}} />);

    expect(await screen.findByText(/AAPL/)).toBeTruthy();
    expect(screen.getByText('$150.00')).toBeTruthy();
    expect(screen.queryByText('Momentum')).toBeNull();
    expect(screen.queryByText('Volatility')).toBeNull();
  });

  it('omits non-finite technical metrics and confidence', async () => {
    apiMocks.getDetail.mockResolvedValue({
      data: detail({
        projection: {
          targetDate: '2026-08-10',
          targetPrice: 160,
          expectedChange: 6.6,
          confidence: Number.NaN,
          recommendation: 'BUY',
          risk: 'Medium',
          trend: 'Bullish',
        },
        technical: {
          momentum: Number.POSITIVE_INFINITY,
          volatility: Number.NaN,
        },
      }),
    });

    render(<StockDetailModal symbol="AAPL" isOpen onClose={() => {}} />);

    expect(await screen.findByText(/AAPL/)).toBeTruthy();
    expect(screen.getByText('$150.00')).toBeTruthy();
    expect(screen.queryByText('Momentum')).toBeNull();
    expect(screen.queryByText('Volatility')).toBeNull();
    expect(screen.queryByText(/Confidence:/)).toBeNull();
  });
});
