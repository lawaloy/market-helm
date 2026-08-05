import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  buildNotifications,
  buildSymbolOptions,
  canPersistConfig,
  dedupeAlerts,
  emptyConfig,
  findDuplicatePriceRule,
  formatCondition,
  formatDeliveryStatusLine,
  formatTestSuccess,
  isSampleRule,
  loadSymbolCatalog,
  loadTrackedSymbols,
  parseSymbolCatalog,
  priceAlertKey,
  slugify,
} from './alertsUtils';
import type { AlertRule, AlertsConfig, ChannelStatus } from '../../types';

vi.mock('../../services/api', () => ({
  alertsApi: {
    getSymbols: vi.fn(),
  },
  historyApi: {
    getSymbols: vi.fn(),
  },
}));

import { alertsApi, historyApi } from '../../services/api';

function priceRule(
  id: string,
  symbol: string,
  operator: AlertRule['condition']['operator'],
  value: number,
): AlertRule {
  return {
    id,
    name: id,
    enabled: true,
    condition: { type: 'price_threshold', symbol, operator, value },
    notifications: ['log'],
  };
}

describe('buildNotifications', () => {
  it('always includes log and appends enabled channels', () => {
    expect(buildNotifications(false, false)).toEqual(['log']);
    expect(buildNotifications(true, false)).toEqual(['log', 'email']);
    expect(buildNotifications(false, true)).toEqual(['log', 'webhook']);
    expect(buildNotifications(true, true)).toEqual(['log', 'email', 'webhook']);
  });
});

describe('canPersistConfig', () => {
  const channelsOff: ChannelStatus = {
    email_smtp: false,
    email_recipients: false,
    webhook_url: false,
  };
  const channelsWebhookSaved: ChannelStatus = {
    email_smtp: false,
    email_recipients: false,
    webhook_url: true,
  };

  function config(partial: Partial<AlertsConfig['defaults']>): AlertsConfig {
    const base = emptyConfig();
    return {
      ...base,
      defaults: { ...base.defaults, ...partial },
    };
  }

  it('rejects when both delivery channels are off', () => {
    expect(canPersistConfig(config({ notify_email: false, notify_webhook: false }), null, '')).toBe(
      'Turn on email or Discord/Slack.',
    );
  });

  it('rejects email-on without an address', () => {
    expect(
      canPersistConfig(config({ notify_email: true, notify_webhook: false, email_to: '  ' }), null, ''),
    ).toBe('Enter your email address, or turn off email notifications.');
  });

  it('rejects webhook-on without a saved URL or draft', () => {
    expect(
      canPersistConfig(
        config({ notify_email: false, notify_webhook: true }),
        channelsOff,
        '   ',
      ),
    ).toBe('Paste a webhook URL, or turn off Discord/Slack notifications.');
  });

  it('allows webhook-on when a secret is already saved and draft is blank', () => {
    expect(
      canPersistConfig(
        config({ notify_email: false, notify_webhook: true }),
        channelsWebhookSaved,
        '',
      ),
    ).toBeNull();
  });

  it('allows email-on with a trimmed address', () => {
    expect(
      canPersistConfig(
        config({ notify_email: true, notify_webhook: false, email_to: 'user@example.com' }),
        null,
        '',
      ),
    ).toBeNull();
  });
});

describe('priceAlertKey', () => {
  it('builds a stable uppercase key for price thresholds', () => {
    expect(
      priceAlertKey({
        type: 'price_threshold',
        symbol: '  aapl ',
        operator: 'less_than',
        value: 150,
      }),
    ).toBe('AAPL|less_than|150');
  });

  it('returns null for screening rules and incomplete price rules', () => {
    expect(priceAlertKey({ type: 'screening_match', filters: { min_volume: 1 } })).toBeNull();
    expect(
      priceAlertKey({ type: 'price_threshold', symbol: '   ', operator: 'less_than', value: 10 }),
    ).toBeNull();
    expect(
      priceAlertKey({ type: 'price_threshold', symbol: 'AAPL', operator: undefined, value: 10 }),
    ).toBeNull();
    expect(
      priceAlertKey({ type: 'price_threshold', symbol: 'AAPL', operator: 'less_than', value: Number.NaN }),
    ).toBeNull();
  });
});

describe('dedupeAlerts', () => {
  it('keeps the first price rule and drops later duplicates by key', () => {
    const first = priceRule('a1', 'AAPL', 'less_than', 100);
    const duplicate = priceRule('a2', 'aapl', 'less_than', 100);
    const other = priceRule('a3', 'MSFT', 'greater_than', 200);
    expect(dedupeAlerts([first, duplicate, other]).map((r) => r.id)).toEqual(['a1', 'a3']);
  });

  it('dedupes screening rules by id when price key is absent', () => {
    const screening: AlertRule = {
      id: 'screen-1',
      name: 'Screen',
      enabled: true,
      condition: { type: 'screening_match', filters: { min_volume: 1e6 } },
      notifications: ['log'],
    };
    const clone = { ...screening };
    expect(dedupeAlerts([screening, clone]).map((r) => r.id)).toEqual(['screen-1']);
  });
});

describe('findDuplicatePriceRule', () => {
  const alerts = [
    priceRule('keep', 'AAPL', 'less_than', 100),
    priceRule('other', 'MSFT', 'greater_than', 200),
  ];

  it('matches regardless of symbol casing or surrounding whitespace', () => {
    expect(findDuplicatePriceRule(alerts, ' aapl', 'less_than', 100)?.id).toBe('keep');
  });

  it('honors excludeId so editing a rule does not collide with itself', () => {
    expect(findDuplicatePriceRule(alerts, 'AAPL', 'less_than', 100, 'keep')).toBeUndefined();
    expect(findDuplicatePriceRule(alerts, 'AAPL', 'less_than', 100, 'other')?.id).toBe('keep');
  });

  it('returns undefined for invalid lookup inputs', () => {
    expect(findDuplicatePriceRule(alerts, '   ', 'less_than', 100)).toBeUndefined();
    expect(findDuplicatePriceRule(alerts, 'AAPL', 'less_than', Number.NaN)).toBeUndefined();
  });
});

describe('parseSymbolCatalog', () => {
  it('returns null for missing, empty, or non-array symbol payloads', () => {
    expect(parseSymbolCatalog(null)).toBeNull();
    expect(parseSymbolCatalog(undefined)).toBeNull();
    expect(parseSymbolCatalog('AAPL')).toBeNull();
    expect(parseSymbolCatalog({})).toBeNull();
    expect(parseSymbolCatalog({ symbols: [] })).toBeNull();
    expect(parseSymbolCatalog({ symbols: 'AAPL' })).toBeNull();
  });

  it('builds searchable options from symbols and optional names', () => {
    const options = parseSymbolCatalog({
      symbols: ['msft', 'AAPL'],
      names: { AAPL: 'Apple Inc.' },
    });
    expect(options).not.toBeNull();
    expect(options!.map((o) => o.value)).toEqual(['AAPL', 'msft']);
    expect(options!.find((o) => o.value === 'AAPL')).toMatchObject({
      label: 'Apple Inc. (AAPL)',
      searchText: 'aapl apple inc.',
    });
    expect(options!.find((o) => o.value === 'msft')).toMatchObject({
      label: 'msft',
      searchText: 'msft msft',
    });
  });
});

describe('buildSymbolOptions', () => {
  it('sorts by label and falls back to the symbol when name is absent', () => {
    expect(buildSymbolOptions(['ZZZ', 'AAA'], { ZZZ: 'Zebra' }).map((o) => o.label)).toEqual([
      'AAA',
      'Zebra (ZZZ)',
    ]);
  });
});

describe('loadSymbolCatalog', () => {
  beforeEach(() => {
    vi.mocked(alertsApi.getSymbols).mockReset();
    vi.mocked(historyApi.getSymbols).mockReset();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        json: async () => ({}),
      }),
    );
  });

  it('prefers the longest catalog and merges prices across sources', async () => {
    vi.mocked(alertsApi.getSymbols).mockResolvedValue({
      data: { symbols: ['AAPL'], prices: { AAPL: 100 } },
    } as never);
    vi.mocked(historyApi.getSymbols).mockResolvedValue({
      data: {
        symbols: ['AAPL', 'MSFT'],
        names: { MSFT: 'Microsoft' },
        prices: { MSFT: 200 },
      },
    } as never);

    const result = await loadSymbolCatalog();

    expect(result.options.map((o) => o.value).sort()).toEqual(['AAPL', 'MSFT']);
    expect(result.prices).toEqual({ AAPL: 100, MSFT: 200 });
  });

  it('falls through to static JSON when APIs fail', async () => {
    vi.mocked(alertsApi.getSymbols).mockRejectedValue(new Error('down'));
    vi.mocked(historyApi.getSymbols).mockRejectedValue(new Error('down'));
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ symbols: ['GOOG'], names: { GOOG: 'Alphabet' } }),
      }),
    );

    const result = await loadSymbolCatalog();

    expect(result.options).toHaveLength(1);
    expect(result.options[0]).toMatchObject({
      value: 'GOOG',
      label: 'Alphabet (GOOG)',
    });
  });

  it('throws when every catalog source is empty or unavailable', async () => {
    vi.mocked(alertsApi.getSymbols).mockResolvedValue({ data: { symbols: [] } } as never);
    vi.mocked(historyApi.getSymbols).mockRejectedValue(new Error('down'));
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ symbols: 'not-an-array' }),
      }),
    );

    await expect(loadSymbolCatalog()).rejects.toThrow('Company list unavailable');
  });
});

describe('loadTrackedSymbols', () => {
  beforeEach(() => {
    vi.mocked(alertsApi.getSymbols).mockReset();
    vi.mocked(historyApi.getSymbols).mockReset();
  });

  it('prefers tracked_symbols from the alerts catalog', async () => {
    vi.mocked(alertsApi.getSymbols).mockResolvedValue({
      data: { symbols: ['ZZZ'], tracked_symbols: ['aapl', 'Msft'] },
    } as never);

    await expect(loadTrackedSymbols()).resolves.toEqual(new Set(['AAPL', 'MSFT']));
    expect(historyApi.getSymbols).not.toHaveBeenCalled();
  });

  it('falls back to history symbols when tracked_symbols is unavailable', async () => {
    vi.mocked(alertsApi.getSymbols).mockRejectedValue(new Error('down'));
    vi.mocked(historyApi.getSymbols).mockResolvedValue({
      data: { symbols: ['goog'] },
    } as never);

    await expect(loadTrackedSymbols()).resolves.toEqual(new Set(['GOOG']));
  });

  it('returns an empty set when every source fails', async () => {
    vi.mocked(alertsApi.getSymbols).mockRejectedValue(new Error('down'));
    vi.mocked(historyApi.getSymbols).mockRejectedValue(new Error('down'));

    await expect(loadTrackedSymbols()).resolves.toEqual(new Set());
  });
});

describe('isSampleRule', () => {
  it('detects known sample ids and example: name prefixes', () => {
    expect(
      isSampleRule({
        id: 'alert_aapl_drop',
        name: 'Real looking name',
        enabled: true,
        condition: { type: 'screening_match' },
        notifications: ['log'],
      }),
    ).toBe(true);
    expect(
      isSampleRule({
        id: 'custom',
        name: 'example: Discord demo',
        enabled: true,
        condition: { type: 'screening_match' },
        notifications: ['log'],
      }),
    ).toBe(true);
  });

  it('returns false for user rules', () => {
    expect(
      isSampleRule({
        id: 'alert_user_1',
        name: 'My AAPL alert',
        enabled: true,
        condition: { type: 'price_threshold', symbol: 'AAPL', operator: 'less_than', value: 100 },
        notifications: ['log'],
      }),
    ).toBe(false);
  });
});

describe('slugify', () => {
  it('lowercases, strips junk, and caps length at 40', () => {
    expect(slugify('  Hello World!! ')).toBe('hello_world');
    expect(slugify('a'.repeat(50))).toHaveLength(40);
  });
});

describe('formatTestSuccess', () => {
  it('formats zero, one, and many notifiers', () => {
    expect(formatTestSuccess([])).toBe('Test notification sent.');
    expect(formatTestSuccess(['email'])).toBe('Test sent via email.');
    expect(formatTestSuccess(['email', 'webhook'])).toBe('Test sent via email and webhook.');
    expect(formatTestSuccess(['email', 'webhook', 'log'])).toBe(
      'Test sent via email, webhook and log.',
    );
  });
});

describe('formatDeliveryStatusLine', () => {
  it('labels channel outcome and test/live kind', () => {
    const line = formatDeliveryStatusLine({
      channel: 'webhook',
      success: false,
      test: true,
      timestamp: '2026-08-05T12:00:00.000Z',
    });
    expect(line).toContain('Discord/Slack');
    expect(line).toContain('Failed');
    expect(line).toContain('(test)');
  });
});

describe('formatCondition', () => {
  it('describes price thresholds and screening matches', () => {
    expect(
      formatCondition({
        id: '1',
        name: 'drop',
        enabled: true,
        condition: { type: 'price_threshold', symbol: 'AAPL', operator: 'less_than', value: 100 },
        notifications: ['log'],
      }),
    ).toBe('AAPL falls below $100.00');
    expect(
      formatCondition({
        id: '2',
        name: 'screen',
        enabled: true,
        condition: { type: 'screening_match' },
        notifications: ['log'],
      }),
    ).toBe('Matches your screening filters');
  });
});
