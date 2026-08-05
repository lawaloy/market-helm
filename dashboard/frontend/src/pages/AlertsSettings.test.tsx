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

const baseConfigResponse = {
  exists: true,
  config: {
    defaults: {
      email_to: 'user@example.com',
      webhook_format: 'discord' as const,
      notify_email: true,
      notify_webhook: false,
    },
    alerts: [sampleRule],
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
    expect(screen.getByRole('button', { name: 'Check watches now' })).toBeTruthy();
  });
  await waitFor(() => {
    expect(screen.getByTitle('Send test')).toBeTruthy();
  });
}

describe('AlertsSettings dirty guards', () => {
  beforeEach(() => {
    apiMocks.getConfig.mockResolvedValue({ data: structuredClone(baseConfigResponse) });
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
        channels: {
          email_smtp: true,
          email_recipients: true,
          webhook_url: false,
        },
      },
    }));
    apiMocks.initConfig.mockResolvedValue({ data: { message: 'ok' } });
    apiMocks.testAlert.mockResolvedValue({
      data: { alert_id: sampleRule.id, status: 'ok', notifiers: ['email'] },
    });
    apiMocks.getSymbols.mockResolvedValue({
      data: { symbols: ['AAPL'], names: { AAPL: 'Apple' }, count: 1, prices: {} },
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

  it('refuses Send test while dirty and does not call testAlert', async () => {
    await renderReady();

    fireEvent.change(screen.getByPlaceholderText('you@email.com'), {
      target: { value: 'other@example.com' },
    });
    fireEvent.click(screen.getByTitle('Send test'));

    await waitFor(() => {
      expect(screen.getByRole('status').textContent).toContain(
        'Save your changes before sending a test.',
      );
    });
    expect(apiMocks.testAlert).not.toHaveBeenCalled();
  });

  it('auto-saves then runs check when dirty but canSave', async () => {
    await renderReady();
    const runCheckCallsAtMount = apiMocks.runCheck.mock.calls.length;

    fireEvent.change(screen.getByPlaceholderText('you@email.com'), {
      target: { value: 'other@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Check watches now' }));

    await waitFor(() => {
      expect(apiMocks.saveConfig).toHaveBeenCalledTimes(1);
    });
    expect(apiMocks.saveConfig.mock.calls[0][0].defaults.email_to).toBe('other@example.com');

    await waitFor(() => {
      // persistConfig runs a post-save check, then handleRunCheck runs again
      expect(apiMocks.runCheck.mock.calls.length).toBeGreaterThanOrEqual(runCheckCallsAtMount + 2);
    });
    await waitFor(() => {
      expect(screen.getByRole('status').textContent).toMatch(/No watches triggered|watch\(es\) triggered/);
    });
  });

  it('refuses Run check when dirty and invalid without saving', async () => {
    await renderReady();
    const runCheckCallsAtMount = apiMocks.runCheck.mock.calls.length;

    fireEvent.change(screen.getByPlaceholderText('you@email.com'), {
      target: { value: '' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Check watches now' }));

    await waitFor(() => {
      expect(screen.getByRole('status').textContent).toContain(
        'Save your changes before running a check.',
      );
    });
    expect(apiMocks.saveConfig).not.toHaveBeenCalled();
    expect(apiMocks.runCheck.mock.calls.length).toBe(runCheckCallsAtMount);
  });
});
