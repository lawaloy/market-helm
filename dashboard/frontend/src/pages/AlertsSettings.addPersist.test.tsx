import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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

const aaplRule = {
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

const msftRule = {
  id: 'msft_less_than_150',
  name: 'MSFT price alert',
  enabled: true,
  condition: {
    type: 'price_threshold' as const,
    symbol: 'MSFT',
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
      alerts: [aaplRule, msftRule],
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
    expect(screen.getAllByTitle('Send test')).toHaveLength(2);
  });
}

describe('AlertsSettings dual-channel composer add persist', () => {
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
        alert_id: msftRule.id,
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
        tracked_symbols: ['AAPL', 'MSFT'],
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

  it('auto-saves a composer add without replacing existing dual-channel watches', async () => {
    await renderWithWatches();

    fireEvent.change(screen.getByLabelText('Target price'), { target: { value: '200' } });
    fireEvent.click(screen.getByRole('button', { name: 'Set watch' }));

    await waitFor(() => {
      expect(apiMocks.saveConfig).toHaveBeenCalledTimes(1);
    });
    const payload = apiMocks.saveConfig.mock.calls[0][0];
    expect(payload.defaults.notify_email).toBe(true);
    expect(payload.defaults.notify_webhook).toBe(true);
    expect(payload.defaults.email_to).toBe('user@example.com');
    expect(payload.defaults.webhook_format).toBe('discord');
    expect(payload.defaults).not.toHaveProperty('webhook_url');
    expect(payload.alerts).toHaveLength(3);
    expect(payload.alerts.map((alert: { id: string }) => alert.id)).toEqual([
      'aapl_less_than_150',
      'msft_less_than_150',
      'aapl_less_than_200',
    ]);
    expect(payload.alerts[2]).toEqual(
      expect.objectContaining({
        id: 'aapl_less_than_200',
        enabled: true,
        cooldown_minutes: 60,
        notifications: ['log', 'email', 'webhook'],
        condition: expect.objectContaining({
          type: 'price_threshold',
          symbol: 'AAPL',
          operator: 'less_than',
          value: 200,
        }),
      }),
    );
    expect(payload.alerts.slice(0, 2)).toEqual([
      expect.objectContaining({
        id: 'aapl_less_than_150',
        enabled: true,
        notifications: ['log', 'email', 'webhook'],
        condition: expect.objectContaining({
          type: 'price_threshold',
          symbol: 'AAPL',
          operator: 'less_than',
          value: 150,
        }),
      }),
      expect.objectContaining({
        id: 'msft_less_than_150',
        enabled: true,
        notifications: ['log', 'email', 'webhook'],
        condition: expect.objectContaining({
          type: 'price_threshold',
          symbol: 'MSFT',
          operator: 'less_than',
          value: 150,
        }),
      }),
    ]);
    expect(screen.getAllByTitle('Send test')).toHaveLength(3);
    expect(screen.getAllByRole('switch', { name: 'Enable AAPL price alert' })).toHaveLength(2);
    expect(screen.getByRole('switch', { name: 'Enable MSFT price alert' })).toBeTruthy();
  });

  it('allows Send test and Check watches now after a composer add persist', async () => {
    await renderWithWatches();
    const runCheckCallsAtMount = apiMocks.runCheck.mock.calls.length;

    fireEvent.change(screen.getByLabelText('Target price'), { target: { value: '200' } });
    fireEvent.click(screen.getByRole('button', { name: 'Set watch' }));
    await waitFor(() => {
      expect(apiMocks.saveConfig).toHaveBeenCalledTimes(1);
    });

    const msftCard = screen.getByRole('switch', { name: 'Enable MSFT price alert' }).closest('li');
    expect(msftCard).toBeTruthy();
    fireEvent.click(within(msftCard as HTMLElement).getByTitle('Send test'));
    await waitFor(() => {
      expect(apiMocks.testAlert).toHaveBeenCalledTimes(1);
    });
    expect(apiMocks.testAlert.mock.calls[0][0]).toBe(msftRule.id);
    expect(apiMocks.testAlert.mock.calls[0][0]).not.toBe('aapl_less_than_200');
    expect(apiMocks.testAlert.mock.calls[0][1]).toBe(false);

    fireEvent.click(screen.getByRole('button', { name: 'Check watches now' }));
    await waitFor(() => {
      expect(apiMocks.runCheck.mock.calls.length).toBeGreaterThanOrEqual(runCheckCallsAtMount + 2);
    });
    expect(apiMocks.saveConfig).toHaveBeenCalledTimes(1);
  });
});
