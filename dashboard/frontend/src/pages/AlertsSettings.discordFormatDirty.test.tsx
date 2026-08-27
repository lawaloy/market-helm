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
        webhook_format: 'slack' as const,
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

describe('AlertsSettings dual-channel Discord format dirty guards from Slack', () => {
  beforeEach(() => {
    apiMocks.getConfig.mockResolvedValue({ data: structuredClone(configResponse()) });
    apiMocks.saveConfig.mockImplementation(async ({ defaults, alerts }) => ({
      data: {
        exists: true,
        config: {
          defaults: {
            email_to: defaults?.email_to ?? '',
            webhook_format: defaults?.webhook_format ?? 'discord',
            notify_email: defaults?.notify_email ?? false,
            notify_webhook: defaults?.notify_webhook ?? false,
          },
          alerts: alerts ?? [],
        },
        channels,
      },
    }));
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

  it('refuses Send test while the Discord format chip is dirty', async () => {
    await renderWithWatches();

    expect(screen.getByRole('button', { name: 'Slack' }).getAttribute('class')).toContain(
      'bg-[#4A154B]',
    );

    fireEvent.click(screen.getByRole('button', { name: 'Discord' }));
    expect(screen.getByRole('button', { name: 'Discord' }).getAttribute('class')).toContain(
      'bg-[#5865F2]',
    );
    fireEvent.click(screen.getByTitle('Send test'));

    await waitFor(() => {
      expect(screen.getByRole('status').textContent).toContain(
        'Save your changes before sending a test.',
      );
    });
    expect(apiMocks.testAlert).not.toHaveBeenCalled();
    expect(apiMocks.saveConfig).not.toHaveBeenCalled();
  });

  it('auto-saves a dirty Discord format then runs Check watches now without rewriting the webhook URL', async () => {
    await renderWithWatches();
    const runCheckCallsAtMount = apiMocks.runCheck.mock.calls.length;

    fireEvent.click(screen.getByRole('button', { name: 'Discord' }));
    fireEvent.click(screen.getByRole('button', { name: 'Check watches now' }));

    await waitFor(() => {
      expect(apiMocks.saveConfig).toHaveBeenCalledTimes(1);
    });
    const payload = apiMocks.saveConfig.mock.calls[0][0];
    expect(payload.defaults.webhook_format).toBe('discord');
    expect(payload.defaults.notify_email).toBe(true);
    expect(payload.defaults.notify_webhook).toBe(true);
    expect(payload.defaults.email_to).toBe('user@example.com');
    expect(payload.defaults).not.toHaveProperty('webhook_url');
    expect(payload.alerts).toEqual([
      expect.objectContaining({
        id: 'aapl_less_than_150',
        notifications: ['log', 'email', 'webhook'],
      }),
    ]);
    expect(apiMocks.testAlert).not.toHaveBeenCalled();
    await waitFor(() => {
      // persistConfig runs a post-save check, then handleRunCheck runs again
      expect(apiMocks.runCheck.mock.calls.length).toBeGreaterThanOrEqual(runCheckCallsAtMount + 2);
    });
  });
});
