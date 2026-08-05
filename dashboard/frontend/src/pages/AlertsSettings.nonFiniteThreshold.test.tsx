import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
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

const baseConfigResponse = {
  exists: true,
  config: {
    defaults: {
      email_to: 'user@example.com',
      webhook_format: 'discord' as const,
      notify_email: true,
      notify_webhook: false,
    },
    alerts: [] as Array<Record<string, unknown>>,
  },
  channels: {
    email_smtp: true,
    email_recipients: true,
    webhook_url: false,
  },
};

async function renderReady() {
  render(<AlertsSettings />);
  await waitFor(() => {
    expect(screen.getByRole('button', { name: /Set watch|Add to list/ })).toBeTruthy();
  });
}

describe('AlertsSettings non-finite thresholds', () => {
  beforeEach(() => {
    apiMocks.getConfig.mockResolvedValue({ data: structuredClone(baseConfigResponse) });
    apiMocks.saveConfig.mockResolvedValue({ data: structuredClone(baseConfigResponse) });
    apiMocks.initConfig.mockResolvedValue({ data: { message: 'ok' } });
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

  it('rejects blank target prices without adding a watch or saving', async () => {
    // type=number sanitizes Infinity/1e999 to "" — blank must not become a $0 watch.
    await renderReady();

    fireEvent.change(screen.getByLabelText('Target price'), {
      target: { value: '' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Set watch|Add to list/ }));

    await waitFor(() => {
      expect(screen.getByRole('status').textContent).toContain(
        'Enter a valid symbol and price.',
      );
    });
    expect(apiMocks.saveConfig).not.toHaveBeenCalled();
    expect(screen.queryByText('Active watches')).toBeNull();
  });
});
