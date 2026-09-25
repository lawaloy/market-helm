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

const priceRule = {
  id: 'aapl_less_than_150',
  name: 'AAPL price alert',
  enabled: true,
  condition: {
    type: 'price_threshold' as const,
    symbol: 'AAPL',
    operator: 'less_than' as const,
    value: 150,
  },
  notifications: ['log', 'email'] as Array<'log' | 'email' | 'webhook'>,
};

const rsiRule = {
  id: 'aapl_rsi_less_than_30',
  name: 'AAPL RSI alert',
  enabled: true,
  condition: {
    type: 'rsi_threshold' as const,
    symbol: 'AAPL',
    period: 14,
    operator: 'less_than' as const,
    value: 30,
  },
  notifications: ['log', 'email'] as Array<'log' | 'email' | 'webhook'>,
};

const channels = {
  email_smtp: true,
  email_recipients: true,
  webhook_url: false,
};

function configResponse(alerts: Array<typeof priceRule | typeof rsiRule> = [priceRule]) {
  return {
    exists: true,
    config: {
      defaults: {
        email_to: 'user@example.com',
        webhook_format: 'discord' as const,
        notify_email: true,
        notify_webhook: false,
      },
      alerts,
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

function stubApis(alerts: Array<typeof priceRule | typeof rsiRule> = [priceRule]) {
  apiMocks.getConfig.mockResolvedValue({ data: structuredClone(configResponse(alerts)) });
  apiMocks.saveConfig.mockImplementation(async ({ defaults, alerts: nextAlerts }) => ({
    data: {
      exists: true,
      config: {
        defaults: {
          email_to: defaults?.email_to ?? '',
          webhook_format: defaults?.webhook_format ?? 'discord',
          notify_email: defaults?.notify_email ?? false,
          notify_webhook: defaults?.notify_webhook ?? false,
        },
        alerts: nextAlerts ?? [],
      },
      channels,
    },
  }));
  apiMocks.initConfig.mockResolvedValue({ data: { message: 'ok' } });
  apiMocks.testAlert.mockResolvedValue({
    data: { alert_id: alerts[0].id, status: 'ok', notifiers: ['email'] },
  });
  apiMocks.getSymbols.mockResolvedValue({
    data: {
      symbols: ['AAPL', 'MSFT'],
      names: { AAPL: 'Apple', MSFT: 'Microsoft' },
      count: 2,
      prices: {},
    },
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
}

describe('AlertsSettings RSI and compound composer persist', () => {
  beforeEach(() => {
    stubApis();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('auto-saves an RSI watch without replacing existing price watches', async () => {
    await renderWithWatches();

    fireEvent.click(screen.getByRole('button', { name: /^RSI$/ }));
    fireEvent.change(screen.getByLabelText('RSI threshold'), { target: { value: '25' } });
    fireEvent.click(screen.getByRole('button', { name: 'Set watch' }));

    await waitFor(() => {
      expect(apiMocks.saveConfig).toHaveBeenCalledTimes(1);
    });
    const payload = apiMocks.saveConfig.mock.calls[0][0];
    expect(payload.alerts).toHaveLength(2);
    expect(payload.alerts.map((alert: { id: string }) => alert.id)).toEqual([
      'aapl_less_than_150',
      'aapl_rsi_less_than_25',
    ]);
    expect(payload.alerts[1]).toEqual(
      expect.objectContaining({
        id: 'aapl_rsi_less_than_25',
        name: 'AAPL RSI alert',
        enabled: true,
        cooldown_minutes: 60,
        notifications: ['log', 'email'],
        condition: {
          type: 'rsi_threshold',
          symbol: 'AAPL',
          period: 14,
          operator: 'less_than',
          value: 25,
        },
      }),
    );
    expect(payload.alerts[0]).toEqual(
      expect.objectContaining({
        id: 'aapl_less_than_150',
        condition: expect.objectContaining({ type: 'price_threshold', value: 150 }),
      }),
    );
    expect(screen.getByRole('switch', { name: 'Enable AAPL RSI alert' })).toBeTruthy();
  });

  it('auto-saves a Price + RSI compound watch with both leaves', async () => {
    await renderWithWatches();

    fireEvent.click(screen.getByRole('button', { name: /^Price \+ RSI$/ }));
    fireEvent.change(screen.getByLabelText('Target price'), { target: { value: '200' } });
    fireEvent.change(screen.getByLabelText('RSI threshold'), { target: { value: '30' } });
    fireEvent.click(screen.getByRole('button', { name: 'Set watch' }));

    await waitFor(() => {
      expect(apiMocks.saveConfig).toHaveBeenCalledTimes(1);
    });
    const payload = apiMocks.saveConfig.mock.calls[0][0];
    expect(payload.alerts).toHaveLength(2);
    expect(payload.alerts[0].id).toBe('aapl_less_than_150');
    expect(payload.alerts[1]).toEqual(
      expect.objectContaining({
        id: 'aapl_less_than_200_rsi_less_than_30',
        name: 'AAPL price + RSI alert',
        enabled: true,
        cooldown_minutes: 60,
        notifications: ['log', 'email'],
        condition: {
          type: 'compound',
          op: 'and',
          conditions: [
            {
              type: 'price_threshold',
              symbol: 'AAPL',
              operator: 'less_than',
              value: 200,
            },
            {
              type: 'rsi_threshold',
              symbol: 'AAPL',
              period: 14,
              operator: 'less_than',
              value: 30,
            },
          ],
        },
      }),
    );
  });

  it('refuses a duplicate RSI composer watch without saving', async () => {
    stubApis([rsiRule]);
    await renderWithWatches();

    fireEvent.click(screen.getByRole('button', { name: /^RSI$/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Set watch' }));

    await waitFor(() => {
      expect(screen.getByRole('status').textContent).toContain(
        'You already have a watch when aapl rsi(14) falls below 30.00.',
      );
    });
    expect(apiMocks.saveConfig).not.toHaveBeenCalled();
  });
});
