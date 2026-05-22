import { getCompanyName } from '../../utils/formatters';
import { alertsApi, historyApi } from '../../services/api';
import type { AlertRule, AlertsConfig, ChannelStatus } from '../../types';

export type SymbolOption = {
  value: string;
  label: string;
  searchText: string;
};

export const SAMPLE_RULE_IDS = new Set([
  'alert_aapl_drop',
  'alert_high_volume_gainers',
  'alert_multi_channel',
  'alert_discord_example',
]);

export const SYMBOL_GRADIENTS = [
  'from-violet-500 to-indigo-600',
  'from-teal-500 to-emerald-600',
  'from-amber-500 to-orange-600',
  'from-rose-500 to-pink-600',
  'from-sky-500 to-blue-600',
  'from-fuchsia-500 to-purple-600',
];

export const fieldClass =
  'w-full rounded-xl border border-slate-200/80 bg-white px-3.5 py-2.5 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 transition focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500';

export const webhookInputClass = `${fieldClass} font-mono text-xs py-2`;

export const emptyConfig = (): AlertsConfig => ({
  defaults: { email_to: '', webhook_format: 'discord', notify_email: true, notify_webhook: false },
  alerts: [],
});

export function isSampleRule(rule: AlertRule): boolean {
  return SAMPLE_RULE_IDS.has(rule.id) || /^example:/i.test(rule.name.trim());
}

export function buildNotifications(
  notifyEmail: boolean,
  notifyWebhook: boolean,
): AlertRule['notifications'] {
  const channels: AlertRule['notifications'] = ['log'];
  if (notifyEmail) channels.push('email');
  if (notifyWebhook) channels.push('webhook');
  return channels;
}

export function formatPrice(value: number | string | undefined): string {
  const n = Number(value);
  if (Number.isNaN(n)) return String(value ?? '?');
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function formatQuotePrice(value: number | undefined | null): string | null {
  if (value == null || Number.isNaN(Number(value))) return null;
  return `$${formatPrice(value)}`;
}

export function formatCondition(rule: AlertRule): string {
  const condition = rule.condition;
  if (condition.type === 'price_threshold') {
    const op = condition.operator === 'greater_than' ? 'rises above' : 'falls below';
    return `${condition.symbol ?? '?'} ${op} $${formatPrice(condition.value)}`;
  }
  if (condition.type === 'screening_match') {
    return 'Matches your screening filters';
  }
  return 'Custom condition';
}

export function ruleTitle(rule: AlertRule): string {
  if (rule.condition.type === 'price_threshold') {
    return `${rule.condition.symbol ?? 'Stock'} price alert`;
  }
  return rule.name;
}

export function symbolGradient(symbol: string): string {
  const hash = symbol.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
  return SYMBOL_GRADIENTS[hash % SYMBOL_GRADIENTS.length];
}

export function priceAlertKey(condition: AlertRule['condition']): string | null {
  if (condition.type !== 'price_threshold') return null;
  const symbol = condition.symbol?.trim().toUpperCase();
  const operator = condition.operator;
  const value = condition.value;
  if (!symbol || !operator || value === undefined || Number.isNaN(Number(value))) return null;
  return `${symbol}|${operator}|${value}`;
}

export function dedupeAlerts(alerts: AlertRule[]): AlertRule[] {
  const seen = new Set<string>();
  const unique: AlertRule[] = [];
  for (const rule of alerts) {
    const key = priceAlertKey(rule.condition) ?? rule.id;
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(rule);
  }
  return unique;
}

export function findDuplicatePriceRule(
  alerts: AlertRule[],
  symbol: string,
  operator: AlertRule['condition']['operator'],
  value: number,
  excludeId?: string,
): AlertRule | undefined {
  const key = `${symbol}|${operator}|${value}`;
  return alerts.find((rule) => {
    if (excludeId && rule.id === excludeId) return false;
    return priceAlertKey(rule.condition) === key;
  });
}

export function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 40);
}

export function formatTestSuccess(notifiers: string[]): string {
  if (notifiers.length === 0) return 'Test notification sent.';
  if (notifiers.length === 1) return `Test sent via ${notifiers[0]}.`;
  const last = notifiers[notifiers.length - 1];
  return `Test sent via ${notifiers.slice(0, -1).join(', ')} and ${last}.`;
}

export function formSnapshot(config: AlertsConfig, webhookDraft: string): string {
  return JSON.stringify({
    defaults: config.defaults ?? {},
    alerts: config.alerts,
    webhookDraft: webhookDraft.trim(),
  });
}

export function canPersistConfig(
  config: AlertsConfig,
  channels: ChannelStatus | null,
  webhookDraft: string,
): string | null {
  const emailOn = config.defaults?.notify_email ?? false;
  const webhookOn = config.defaults?.notify_webhook ?? false;
  if (!emailOn && !webhookOn) return 'Turn on email or Discord/Slack.';
  if (emailOn && !config.defaults?.email_to?.trim()) {
    return 'Enter your email address, or turn off email notifications.';
  }
  if (webhookOn && !channels?.webhook_url && !webhookDraft.trim()) {
    return 'Paste a webhook URL, or turn off Discord/Slack notifications.';
  }
  return null;
}

export function buildSymbolOptions(symbols: string[], names: Record<string, string>): SymbolOption[] {
  return symbols
    .map((symbol) => {
      const name = getCompanyName(symbol, names[symbol]);
      const label = name !== symbol ? `${name} (${symbol})` : symbol;
      return {
        value: symbol,
        label,
        searchText: `${symbol} ${name}`.toLowerCase(),
      };
    })
    .sort((a, b) => a.label.localeCompare(b.label));
}

export function parseSymbolCatalog(data: unknown): SymbolOption[] | null {
  if (!data || typeof data !== 'object') return null;
  const payload = data as { symbols?: unknown; names?: Record<string, string> };
  if (!Array.isArray(payload.symbols) || payload.symbols.length === 0) return null;
  return buildSymbolOptions(payload.symbols as string[], payload.names ?? {});
}

export async function loadSymbolCatalog(): Promise<{
  options: SymbolOption[];
  prices: Record<string, number>;
}> {
  let best: SymbolOption[] = [];
  let prices: Record<string, number> = {};

  const consider = (data: unknown) => {
    const options = parseSymbolCatalog(data);
    if (!options) return;
    if (options.length > best.length) best = options;
    if (data && typeof data === 'object' && data !== null && 'prices' in data) {
      const payload = data as { prices?: Record<string, number> };
      if (payload.prices) prices = { ...prices, ...payload.prices };
    }
  };

  try {
    consider((await alertsApi.getSymbols()).data);
  } catch {
    // stale backend
  }

  try {
    consider((await historyApi.getSymbols()).data);
  } catch {
    // ignore
  }

  try {
    const res = await fetch('/symbols-catalog.json');
    if (res.ok) consider(await res.json());
  } catch {
    // ignore
  }

  if (best.length > 0) return { options: best, prices };
  throw new Error('Company list unavailable');
}

export async function loadTrackedSymbols(): Promise<Set<string>> {
  try {
    const { data } = await alertsApi.getSymbols();
    const tracked = (data as { tracked_symbols?: string[] }).tracked_symbols;
    if (Array.isArray(tracked)) return new Set(tracked.map((s) => s.toUpperCase()));
  } catch {
    // fall through
  }
  try {
    const { data } = await historyApi.getSymbols();
    if (Array.isArray(data.symbols)) return new Set(data.symbols.map((s) => s.toUpperCase()));
  } catch {
    // ignore
  }
  return new Set();
}
