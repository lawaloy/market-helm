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

const missingConfig = {
  exists: false,
  config: { defaults: {}, alerts: [] },
  channels: {
    email_smtp: false,
    email_recipients: false,
    webhook_url: false,
  },
};

const readyConfig = {
  exists: true,
  config: {
    defaults: {
      email_to: '',
      webhook_format: 'discord' as const,
      notify_email: false,
      notify_webhook: false,
    },
    alerts: [],
  },
  channels: {
    email_smtp: false,
    email_recipients: false,
    webhook_url: false,
  },
};

function axiosError(status: number, detail: string) {
  return {
    isAxiosError: true,
    message: 'Request failed',
    response: { status, data: { detail } },
  };
}

describe('AlertsSettings onboarding init', () => {
  beforeEach(() => {
    apiMocks.getConfig.mockResolvedValue({ data: structuredClone(missingConfig) });
    apiMocks.saveConfig.mockResolvedValue({ data: structuredClone(readyConfig) });
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

  it('shows Start watching when config does not exist and skips the watches toolbar', async () => {
    render(<AlertsSettings />);

    expect(await screen.findByRole('button', { name: 'Start watching' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Check watches now' })).toBeNull();
    expect(apiMocks.initConfig).not.toHaveBeenCalled();
  });

  it('Start watching inits without force, reloads config, and leaves onboarding', async () => {
    apiMocks.getConfig
      .mockResolvedValueOnce({ data: structuredClone(missingConfig) })
      .mockResolvedValue({ data: structuredClone(readyConfig) });

    render(<AlertsSettings />);
    fireEvent.click(await screen.findByRole('button', { name: 'Start watching' }));

    await waitFor(() => {
      expect(apiMocks.initConfig).toHaveBeenCalledTimes(1);
    });
    expect(apiMocks.initConfig.mock.calls[0]).toEqual([]);

    await waitFor(() => {
      expect(apiMocks.getConfig.mock.calls.length).toBeGreaterThanOrEqual(2);
    });
    expect(
      await screen.findByRole('status'),
    ).toBeTruthy();
    expect(screen.getByRole('status').textContent).toContain(
      'Helmtower is ready — pick how you want to be notified.',
    );
    expect(await screen.findByRole('button', { name: 'Check watches now' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Start watching' })).toBeNull();
  });

  it('surfaces init 409 detail and stays on onboarding', async () => {
    const detail =
      "alerts.json already exists. Pass ?force=true to overwrite.";
    apiMocks.initConfig.mockRejectedValueOnce(axiosError(409, detail));

    render(<AlertsSettings />);
    fireEvent.click(await screen.findByRole('button', { name: 'Start watching' }));

    expect(await screen.findByRole('status')).toBeTruthy();
    expect(screen.getByRole('status').textContent).toContain(detail);
    expect(apiMocks.initConfig).toHaveBeenCalledTimes(1);
    expect(apiMocks.initConfig.mock.calls[0]).toEqual([]);
    expect(screen.getByRole('button', { name: 'Start watching' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Check watches now' })).toBeNull();
  });
});
