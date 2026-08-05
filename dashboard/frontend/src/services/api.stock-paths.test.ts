import { afterEach, describe, expect, it, vi } from 'vitest';
import api, { stocksApi } from './api';

describe('stocksApi path encoding', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('percent-encodes ticker path segments for detail and historical', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValue({ data: {} } as never);

    await stocksApi.getDetail('BRK/B');
    await stocksApi.getHistorical('BRK/B', 7);

    expect(get).toHaveBeenNthCalledWith(1, '/api/stocks/BRK%2FB');
    expect(get).toHaveBeenNthCalledWith(2, '/api/stocks/BRK%2FB/historical', {
      params: { days: 7 },
    });
  });

  it('leaves ordinary tickers readable in the path', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValue({ data: {} } as never);

    await stocksApi.getDetail('AAPL');

    expect(get).toHaveBeenCalledWith('/api/stocks/AAPL');
  });
});
