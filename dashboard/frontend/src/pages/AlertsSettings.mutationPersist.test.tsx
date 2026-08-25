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

const sampleRule = {
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

const channels = {
  email_smtp: true,
  email_recipients: true,
  webhook_url: false,
};

function configResponse(alerts: typeof sampleRule[]) {
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

async function renderReady() {
  render(<AlertsSettings />);
  await waitFor(() => {
    expect(screen.getByRole('button', { name: 'Check watches now' })).toBeTruthy();
  });
}

async function renderWithWatches() {
  await renderReady();
  await waitFor(() => {
    expect(screen.getByTitle('Send test')).toBeTruthy();
  });
}

describe('AlertsSettings mutation persist', () => {
  beforeEach(() => {
    apiMocks.getConfig.mockResolvedValue({ data: structuredClone(configResponse([sampleRule])) });
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
      data: { alert_id: sampleRule.id, status: 'ok', notifiers: ['email'] },
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

  it('saves a paused watch as enabled: false', async () => {
    await renderWithWatches();

    fireEvent.click(screen.getByRole('switch', { name: 'Enable AAPL price alert' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save now' }));

    await waitFor(() => {
      expect(apiMocks.saveConfig).toHaveBeenCalledTimes(1);
    });
    const payload = apiMocks.saveConfig.mock.calls[0][0];
    expect(payload.alerts).toHaveLength(1);
    expect(payload.alerts[0].id).toBe('aapl_less_than_150');
    expect(payload.alerts[0].enabled).toBe(false);
  });

  it('saves a removed watch as an empty alerts list', async () => {
    await renderWithWatches();

    fireEvent.click(screen.getByTitle('Remove'));
    fireEvent.click(screen.getByRole('button', { name: 'Save now' }));

    await waitFor(() => {
      expect(apiMocks.saveConfig).toHaveBeenCalledTimes(1);
    });
    const payload = apiMocks.saveConfig.mock.calls[0][0];
    expect(payload.alerts).toEqual([]);
  });

  it('saves an inline operator and threshold edit under the rewritten watch id', async () => {
    await renderWithWatches();

    fireEvent.click(screen.getByTitle('Edit'));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Save' })).toBeTruthy();
    });
    const editor = screen.getByRole('button', { name: 'Save' }).closest('div');
    expect(editor).toBeTruthy();
    fireEvent.change(within(editor as HTMLElement).getByDisplayValue('Falls below'), {
      target: { value: 'greater_than' },
    });
    fireEvent.change(within(editor as HTMLElement).getByDisplayValue('150'), {
      target: { value: '50' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save now' }));

    await waitFor(() => {
      expect(apiMocks.saveConfig).toHaveBeenCalledTimes(1);
    });
    const payload = apiMocks.saveConfig.mock.calls[0][0];
    expect(payload.alerts).toHaveLength(1);
    expect(payload.alerts[0]).toEqual(
      expect.objectContaining({
        id: 'aapl_greater_than_50',
        enabled: true,
        condition: expect.objectContaining({
          type: 'price_threshold',
          symbol: 'AAPL',
          operator: 'greater_than',
          value: 50,
        }),
      }),
    );
  });

  it('rewrites existing watch channels when switching from email to Discord', async () => {
    await renderWithWatches();

    fireEvent.click(screen.getByRole('switch', { name: 'Discord or Slack' }));
    await waitFor(() => {
      expect(screen.getByLabelText(/Webhook URL/i)).toBeTruthy();
    });
    fireEvent.change(screen.getByLabelText(/Webhook URL/i), {
      target: { value: 'https://discord.com/api/webhooks/rotated' },
    });
    fireEvent.click(screen.getByRole('switch', { name: 'Email' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save now' }));

    await waitFor(() => {
      expect(apiMocks.saveConfig).toHaveBeenCalledTimes(1);
    });
    const payload = apiMocks.saveConfig.mock.calls[0][0];
    expect(payload.defaults.notify_email).toBe(false);
    expect(payload.defaults.notify_webhook).toBe(true);
    expect(payload.defaults.webhook_url).toBe('https://discord.com/api/webhooks/rotated');
    expect(payload.alerts).toEqual([
      expect.objectContaining({
        id: 'aapl_less_than_150',
        notifications: ['log', 'webhook'],
      }),
    ]);
  });

  it('auto-saves a new watch with the default 60-minute cooldown', async () => {
    apiMocks.getConfig.mockResolvedValue({ data: structuredClone(configResponse([])) });
    await renderReady();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Set watch' })).toBeTruthy();
    });

    fireEvent.change(screen.getByLabelText('Target price'), { target: { value: '200' } });
    fireEvent.click(screen.getByRole('button', { name: 'Set watch' }));

    await waitFor(() => {
      expect(apiMocks.saveConfig).toHaveBeenCalledTimes(1);
    });
    const payload = apiMocks.saveConfig.mock.calls[0][0];
    expect(payload.alerts).toHaveLength(1);
    expect(payload.alerts[0]).toEqual(
      expect.objectContaining({
        id: 'aapl_less_than_200',
        enabled: true,
        cooldown_minutes: 60,
        condition: expect.objectContaining({
          type: 'price_threshold',
          symbol: 'AAPL',
          operator: 'less_than',
          value: 200,
        }),
      }),
    );
  });
});
