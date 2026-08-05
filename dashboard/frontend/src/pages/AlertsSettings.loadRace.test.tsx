import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
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

const quietStatus = {
  checks_on_fetch: false,
  last_data_date: null,
  tracked_symbols: ['AAPL'],
  last_triggered_at: null as string | null,
  latest_deliveries: [] as unknown[],
};

describe('AlertsSettings load races', () => {
  beforeEach(() => {
    apiMocks.getConfig.mockResolvedValue({ data: structuredClone(baseConfigResponse) });
    apiMocks.saveConfig.mockResolvedValue({ data: structuredClone(baseConfigResponse) });
    apiMocks.initConfig.mockResolvedValue({ data: { message: 'ok' } });
    apiMocks.testAlert.mockResolvedValue({
      data: { alert_id: sampleRule.id, status: 'ok', notifiers: ['email'] },
    });
    apiMocks.getSymbols.mockResolvedValue({
      data: { symbols: ['AAPL'], names: { AAPL: 'Apple' }, count: 1, prices: {} },
    });
    apiMocks.historyGetSymbols.mockRejectedValue(new Error('unused'));
    apiMocks.getQuotes.mockResolvedValue({ data: { prices: {} } });
    apiMocks.getStatus.mockResolvedValue({ data: structuredClone(quietStatus) });
    apiMocks.runCheck.mockResolvedValue({
      data: { triggered: 0, last_data_date: null, events: [], message: 'No watches triggered.' },
    });
    apiMocks.apiGet.mockResolvedValue({ data: { ok: true } });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('ignores a late getConfig response after unmount', async () => {
    let resolveConfig: ((value: unknown) => void) | undefined;
    apiMocks.getConfig.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveConfig = resolve;
        }),
    );
    apiMocks.getStatus.mockImplementation(() => new Promise(() => {}));
    apiMocks.runCheck.mockImplementation(() => new Promise(() => {}));

    render(<AlertsSettings />);
    await act(async () => {
      await Promise.resolve();
    });
    expect(apiMocks.getConfig).toHaveBeenCalled();

    cleanup();

    await act(async () => {
      resolveConfig?.({ data: structuredClone(baseConfigResponse) });
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.queryByText('Price alerts')).toBeNull();
    expect(screen.queryByText(/Sign in required/)).toBeNull();
  });

  it('ignores a late getStatus response after unmount', async () => {
    let resolveStatus: ((value: unknown) => void) | undefined;
    apiMocks.getStatus.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveStatus = resolve;
        }),
    );
    apiMocks.getConfig.mockImplementation(() => new Promise(() => {}));
    apiMocks.runCheck.mockImplementation(() => new Promise(() => {}));

    render(<AlertsSettings />);
    await act(async () => {
      await Promise.resolve();
    });
    expect(apiMocks.getStatus).toHaveBeenCalled();

    cleanup();

    await act(async () => {
      resolveStatus?.({
        data: { ...structuredClone(quietStatus), last_triggered_at: '2026-08-05T12:00:00.000Z' },
      });
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.queryByText(/Last alert:/)).toBeNull();
  });

  it('does not refresh status from a late mount runCheck after unmount', async () => {
    let resolveCheck: ((value: unknown) => void) | undefined;
    let resolveFollowUpStatus: ((value: unknown) => void) | undefined;
    let statusCalls = 0;

    apiMocks.runCheck.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveCheck = resolve;
        }),
    );
    apiMocks.getStatus.mockImplementation(() => {
      statusCalls += 1;
      if (statusCalls === 1) {
        return Promise.resolve({ data: structuredClone(quietStatus) });
      }
      return new Promise((resolve) => {
        resolveFollowUpStatus = resolve;
      });
    });

    render(<AlertsSettings />);
    await waitFor(() => {
      expect(screen.getByText('Price alerts')).toBeTruthy();
    });
    expect(apiMocks.runCheck).toHaveBeenCalled();
    const statusCallsAtUnmount = statusCalls;

    cleanup();

    await act(async () => {
      resolveCheck?.({
        data: { triggered: 0, last_data_date: null, events: [], message: 'No watches triggered.' },
      });
      await Promise.resolve();
      await Promise.resolve();
    });

    // cancelled mount effect must not schedule a follow-up getStatus
    expect(statusCalls).toBe(statusCallsAtUnmount);
    expect(resolveFollowUpStatus).toBeUndefined();

    await act(async () => {
      resolveFollowUpStatus?.({
        data: { ...structuredClone(quietStatus), last_triggered_at: '2026-08-05T12:00:00.000Z' },
      });
      await Promise.resolve();
    });

    expect(screen.queryByText(/Last alert:/)).toBeNull();
  });
});
