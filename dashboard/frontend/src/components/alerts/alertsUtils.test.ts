import { describe, expect, it } from 'vitest';
import {
  buildNotifications,
  buildSymbolOptions,
  canPersistConfig,
  dedupeAlerts,
  emptyConfig,
  findDuplicatePriceRule,
  parseSymbolCatalog,
  priceAlertKey,
} from './alertsUtils';
import type { AlertRule, AlertsConfig, ChannelStatus } from '../../types';

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
