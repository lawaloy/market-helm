import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import AlertsSettings from './AlertsSettings';

const apiMocks = vi.hoisted(() => ({
  getConfig: vi.fn(),
  saveConfig: vi.fn(),
  initConfig: vi.fn(),
  testAlert: vi.fn(),
  getSymbols: vi.fn(),
  getQuotes: vi.fn(),
  getStatus: vi.fn(),
  runCheck: vi.fn(),
  apiGet: vi.fn(),
  historyGetSymbols: vi.fn(),
}));

vi.mock('../services/api', () => ({
  default: {
    get: apiMocks.apiGet,
  },
  alertsApi: {
    getConfig: apiMocks.getConfig,
    saveConfig: apiMocks.saveConfig,
    initConfig: apiMocks.initConfig,
    testAlert: apiMocks.testAlert,
    getSymbols: apiMocks.getSymbols,
    getQuotes: apiMocks.getQuotes,
    getStatus: apiMocks.getStatus,
    runCheck: apiMocks.runCheck,
  },
  historyApi: {
    getSymbols: apiMocks.historyGetSymbols,
  },
}));

vi.mock('../components/alerts/useSymbolPrices', () => ({
  useSymbolPrices: () => ({
    symbolPrices: {},
    mergePrices: vi.fn(),
    pricingPending: new Set<string>(),
    quotesUnavailable: false,
    apiReady: true,
    fetchPricesFor: vi.fn(),
  }),
}));

function axiosStatus(status: number, message = 'Request failed') {
  return {
    isAxiosError: true,
    message,
    response: { status },
  };
}

describe('AlertsSettings verification load errors', () => {
  beforeEach(() => {
    apiMocks.saveConfig.mockResolvedValue({ data: { exists: false } });
    apiMocks.initConfig.mockResolvedValue({ data: { message: 'ok' } });
    apiMocks.testAlert.mockResolvedValue({ data: { status: 'ok' } });
    apiMocks.getSymbols.mockResolvedValue({
      data: { symbols: ['AAPL'], names: { AAPL: 'Apple' }, count: 1, prices: {} },
    });
    apiMocks.historyGetSymbols.mockRejectedValue(new Error('unused'));
    apiMocks.getQuotes.mockResolvedValue({ data: { prices: {} } });
    apiMocks.getStatus.mockResolvedValue({
      data: {
        checks_on_fetch: false,
        last_data_date: null,
        tracked_symbols: [],
        last_triggered_at: null,
        latest_deliveries: [],
      },
    });
    apiMocks.runCheck.mockResolvedValue({
      data: { triggered: 0, last_data_date: null, events: [], message: 'No watches triggered.' },
    });
    apiMocks.apiGet.mockResolvedValue({ data: { ok: true } });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('does not treat a 403 config failure as a missing sign-in', async () => {
    apiMocks.getConfig.mockRejectedValueOnce(axiosStatus(403, 'Request failed with status code 403'));

    render(<AlertsSettings />);

    expect(await screen.findByText('Request failed with status code 403')).toBeTruthy();
    expect(screen.queryByText(/Sign in required/)).toBeNull();
  });
});
