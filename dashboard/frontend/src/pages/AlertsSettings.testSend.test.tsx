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

const dualChannelRule = {
  id: 'aapl_less_than_150',
  name: 'AAPL price alert',
  enabled: true,
  condition: {
    type: 'price_threshold' as const,
    symbol: 'AAPL',
    operator: 'less_than' as const,
    value: 150,
  },
  notifications: ['log', 'email', 'webhook'] as Array<'log' | 'email' | 'webhook'>,
};

const channels = {
  email_smtp: true,
  email_recipients: true,
  webhook_url: true,
};

function configResponse() {
  return {
    exists: true,
    config: {
      defaults: {
        email_to: 'user@example.com',
        webhook_format: 'discord' as const,
        notify_email: true,
        notify_webhook: true,
      },
      alerts: [dualChannelRule],
    },
    channels,
  };
}

async function renderWithWatches() {
  render(<AlertsSettings />);
  await waitFor(() => {
    expect(screen.getByRole('button', { name: 'Check watches now' })).toBeTruthy();
  });
  await waitFor(() => {
    expect(screen.getByTitle('Send test')).toBeTruthy();
  });
}

describe('AlertsSettings dual-channel Send test', () => {
  beforeEach(() => {
    apiMocks.getConfig.mockResolvedValue({ data: structuredClone(configResponse()) });
    apiMocks.saveConfig.mockResolvedValue({ data: structuredClone(configResponse()) });
    apiMocks.initConfig.mockResolvedValue({ data: { message: 'ok' } });
    apiMocks.testAlert.mockResolvedValue({
      data: {
        alert_id: dualChannelRule.id,
        status: 'sent',
        notifiers: ['email', 'webhook'],
      },
    });
    apiMocks.getSymbols.mockResolvedValue({
      data: { symbols: ['AAPL', 'MSFT'], names: { AAPL: 'Apple', MSFT: 'Microsoft' }, count: 2, prices: {} },
    });
    apiMocks.historyGetSymbols.mockRejectedValue(new Error('unused'));
    apiMocks.getQuotes.mockResolvedValue({ data: { prices: {} } });
    apiMocks.getStatus.mockResolvedValue({
      data: {
        checks_on_fetch: false,
        last_data_date: null,
        tracked_symbols: ['AAPL'],
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

  it('sends a live test for the dual-channel watch without saving', async () => {
    await renderWithWatches();
    const statusCallsBefore = apiMocks.getStatus.mock.calls.length;

    fireEvent.click(screen.getByTitle('Send test'));

    await waitFor(() => {
      expect(apiMocks.testAlert).toHaveBeenCalledTimes(1);
    });
    expect(apiMocks.testAlert).toHaveBeenCalledWith('aapl_less_than_150', false);
    expect(apiMocks.saveConfig).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(screen.getByRole('status').textContent).toContain('Test sent via email and webhook.');
    });
    await waitFor(() => {
      expect(apiMocks.getStatus.mock.calls.length).toBeGreaterThan(statusCallsBefore);
    });
  });
});
