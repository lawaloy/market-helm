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

describe('AlertsSettings webhook draft when Discord/Slack is off', () => {
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

  it('does not persist a hidden webhook draft after Discord/Slack is turned off', async () => {
    await renderReady();

    fireEvent.click(screen.getByRole('switch', { name: 'Discord or Slack' }));
    await waitFor(() => {
      expect(screen.getByLabelText(/Webhook URL/i)).toBeTruthy();
    });

    fireEvent.change(screen.getByLabelText(/Webhook URL/i), {
      target: { value: 'https://discord.com/api/webhooks/hidden-draft' },
    });

    // Hide the input; draft remains in React state until we gate it at save time.
    fireEvent.click(screen.getByRole('switch', { name: 'Discord or Slack' }));
    await waitFor(() => {
      expect(screen.queryByLabelText(/Webhook URL/i)).toBeNull();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Save now' }));

    await waitFor(() => {
      expect(apiMocks.saveConfig).toHaveBeenCalledTimes(1);
    });

    const payload = apiMocks.saveConfig.mock.calls[0][0];
    expect(payload.defaults.notify_webhook).toBe(false);
    expect(payload.defaults).not.toHaveProperty('webhook_url');
    expect(payload.alerts.every((rule: { notifications: string[] }) =>
      !rule.notifications.includes('webhook'),
    )).toBe(true);
  });
});
