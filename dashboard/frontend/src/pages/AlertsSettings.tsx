import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import {
  BellAlertIcon,
  ChatBubbleLeftRightIcon,
  EnvelopeIcon,
} from '@heroicons/react/24/outline';
import { AlertComposer } from '../components/alerts/AlertComposer';
import { AlertsToast, PlatformChip } from '../components/alerts/AlertsUi';
import { DeliveryChannel } from '../components/alerts/DeliveryChannel';
import { RuleCard } from '../components/alerts/RuleCard';
import { useSymbolPrices } from '../components/alerts/useSymbolPrices';
import {
  buildNotifications,
  canPersistConfig,
  dedupeAlerts,
  emptyConfig,
  fieldClass,
  findDuplicatePriceRule,
  formatCondition,
  formatDeliveryStatusLine,
  formatTestSuccess,
  formSnapshot,
  isSampleRule,
  loadSymbolCatalog,
  ruleTitle,
  slugify,
  webhookInputClass,
  type SymbolOption,
} from '../components/alerts/alertsUtils';
import { alertsApi } from '../services/api';
import type { AlertRule, AlertsConfig, AlertsStatus, ChannelStatus, WebhookFormat } from '../types';

const COMPOSER_AFTER_COUNT = 3;

const AlertsSettings: React.FC = () => {
  const [config, setConfig] = useState<AlertsConfig>(emptyConfig());
  const [channels, setChannels] = useState<ChannelStatus | null>(null);
  const [exists, setExists] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [initializing, setInitializing] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [webhookDraft, setWebhookDraft] = useState('');
  const [savedSnapshot, setSavedSnapshot] = useState('');
  const [alertStatus, setAlertStatus] = useState<AlertsStatus | null>(null);

  const [newSymbol, setNewSymbol] = useState('AAPL');
  const [newOperator, setNewOperator] = useState<'less_than' | 'greater_than'>('less_than');
  const [newValue, setNewValue] = useState('150');
  const [symbolOptions, setSymbolOptions] = useState<SymbolOption[]>([]);
  const [symbolsLoading, setSymbolsLoading] = useState(true);
  const { symbolPrices, mergePrices, pricingPending, quotesUnavailable, apiReady, fetchPricesFor } =
    useSymbolPrices();

  const userRules = useMemo(
    () => config.alerts.filter((rule) => !isSampleRule(rule)),
    [config.alerts],
  );
  const activeCount = userRules.filter((rule) => rule.enabled).length;
  const notifyEmail = config.defaults?.notify_email ?? true;
  const notifyWebhook = config.defaults?.notify_webhook ?? false;

  const currentSnapshot = useMemo(() => formSnapshot(config, webhookDraft), [config, webhookDraft]);
  const dirty = exists && savedSnapshot !== '' && currentSnapshot !== savedSnapshot;
  const saveError = canPersistConfig(config, channels, webhookDraft);
  const canSave = saveError === null;

  const applyServerConfig = useCallback((data: AlertsConfig, channelStatus: ChannelStatus) => {
    const alerts = dedupeAlerts(data.alerts ?? []).filter((rule) => !isSampleRule(rule));
    const next: AlertsConfig = {
      defaults: {
        email_to: data.defaults?.email_to ?? '',
        webhook_format: data.defaults?.webhook_format ?? 'discord',
        notify_email: data.defaults?.notify_email ?? Boolean(data.defaults?.email_to),
        notify_webhook:
          data.defaults?.notify_webhook ??
          (channelStatus.webhook_url || alerts.some((rule) => rule.notifications.includes('webhook'))),
      },
      alerts,
    };
    setConfig(next);
    setSavedSnapshot(formSnapshot(next, ''));
    setWebhookDraft('');
  }, []);

  const refreshStatus = useCallback(async () => {
    try {
      const { data } = await alertsApi.getStatus();
      setAlertStatus(data);
    } catch {
      setAlertStatus(null);
    }
  }, []);

  const loadConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await alertsApi.getConfig();
      setExists(data.exists);
      setChannels(data.channels);
      if (data.exists) applyServerConfig(data.config, data.channels);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 401) {
        setError('Sign in required to access your Helmtower settings.');
      } else {
        setError(axios.isAxiosError(err) ? err.message : 'Failed to load alerts.');
      }
    } finally {
      setLoading(false);
    }
  }, [applyServerConfig]);

  useEffect(() => {
    void loadConfig();
    void refreshStatus();
    void alertsApi.runCheck().then(() => refreshStatus()).catch(() => {});
  }, [loadConfig, refreshStatus]);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setSymbolsLoading(true);
      try {
        const { options, prices } = await loadSymbolCatalog();
        if (cancelled) return;
        setSymbolOptions(options);
        if (Object.keys(prices).length > 0) {
          mergePrices(prices);
        }
        if (options.length > 0) {
          const preferred = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META'];
          const initial =
            preferred.find((symbol) => options.some((option) => option.value === symbol)) ??
            options[0].value;
          setNewSymbol((prev) => (options.some((option) => option.value === prev) ? prev : initial));
        }
      } catch {
        if (!cancelled) {
          setSymbolOptions([]);
          setError('Could not load companies — restart the backend and refresh.');
        }
      } finally {
        if (!cancelled) setSymbolsLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load catalog once on mount
  }, []);

  useEffect(() => {
    if (!apiReady || !newSymbol.trim()) return;
    void fetchPricesFor([newSymbol]);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fetch when API is ready
  }, [apiReady, newSymbol]);

  useEffect(() => {
    if (!apiReady) return;
    const watchSymbols = userRules
      .map((rule) =>
        rule.condition.type === 'price_threshold' ? rule.condition.symbol?.toUpperCase() : null,
      )
      .filter((symbol): symbol is string => Boolean(symbol));
    if (watchSymbols.length > 0) {
      void fetchPricesFor(watchSymbols);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- stable fetchPricesFor via refs
  }, [apiReady, userRules]);

  useEffect(() => {
    if (!success) return;
    const t = window.setTimeout(() => setSuccess(null), 4000);
    return () => window.clearTimeout(t);
  }, [success]);

  useEffect(() => {
    if (!error) return;
    const t = window.setTimeout(() => setError(null), 6000);
    return () => window.clearTimeout(t);
  }, [error]);

  const buildSavePayload = useCallback(
    (source: AlertsConfig): AlertsConfig => {
      const emailOn = source.defaults?.notify_email ?? false;
      const webhookOn = source.defaults?.notify_webhook ?? false;
      return {
        defaults: {
          email_to: emailOn ? source.defaults?.email_to?.trim() || undefined : undefined,
          webhook_format: source.defaults?.webhook_format,
          notify_email: emailOn,
          notify_webhook: webhookOn,
          ...(webhookDraft.trim() ? { webhook_url: webhookDraft.trim() } : {}),
        },
        alerts: dedupeAlerts(
          source.alerts
            .filter((rule) => !isSampleRule(rule))
            .map((rule) => ({
              ...rule,
              name: ruleTitle(rule),
              notifications: buildNotifications(emailOn, webhookOn),
            })),
        ),
      };
    },
    [webhookDraft],
  );

  const persistConfig = useCallback(
    async (source: AlertsConfig, successMessage?: string): Promise<boolean> => {
      const validationError = canPersistConfig(source, channels, webhookDraft);
      if (validationError) {
        setError(validationError);
        return false;
      }
      setSaving(true);
      setError(null);
      setSuccess(null);
      try {
        const { data } = await alertsApi.saveConfig(buildSavePayload(source));
        setExists(data.exists);
        setChannels(data.channels);
        applyServerConfig(data.config, data.channels);
        setSuccess(successMessage ?? 'All set — your watches are saved.');
        try {
          const { data: runData } = await alertsApi.runCheck();
          if (runData.triggered > 0) {
            setSuccess(`${runData.triggered} watch(es) triggered just now.`);
          }
        } catch {
          // Watch is saved; first check may have nothing to report yet.
        }
        void refreshStatus();
        return true;
      } catch (err) {
        setError(
          axios.isAxiosError(err)
            ? (err.response?.data as { detail?: string })?.detail ?? err.message
            : 'Save failed.',
        );
        return false;
      } finally {
        setSaving(false);
      }
    },
    [applyServerConfig, buildSavePayload, channels, refreshStatus, webhookDraft],
  );

  const handleSave = useCallback(async () => {
    if (!canSave) {
      setError(saveError);
      return false;
    }
    return persistConfig(config);
  }, [canSave, config, persistConfig, saveError]);

  const handleDiscard = () => {
    if (!savedSnapshot) return;
    const parsed = JSON.parse(savedSnapshot) as {
      defaults: AlertsConfig['defaults'];
      alerts: AlertRule[];
      webhookDraft?: string;
    };
    setConfig({ defaults: parsed.defaults ?? {}, alerts: parsed.alerts ?? [] });
    setWebhookDraft(parsed.webhookDraft ?? '');
    setError(null);
  };

  const handleInit = async () => {
    setInitializing(true);
    setError(null);
    try {
      await alertsApi.initConfig();
      await loadConfig();
      setSuccess('Helmtower is ready — pick how you want to be notified.');
    } catch (err) {
      setError(
        axios.isAxiosError(err)
          ? (err.response?.data as { detail?: string })?.detail ?? err.message
          : 'Setup failed.',
      );
    } finally {
      setInitializing(false);
    }
  };

  const handleTest = async (alertId: string) => {
    if (dirty) {
      setError('Save your changes before sending a test.');
      return;
    }
    setTestingId(alertId);
    setError(null);
    setSuccess(null);
    try {
      const { data } = await alertsApi.testAlert(alertId, false);
      setSuccess(formatTestSuccess(data.notifiers));
      await refreshStatus();
    } catch (err) {
      setError(
        axios.isAxiosError(err)
          ? (err.response?.data as { detail?: string })?.detail ?? err.message
          : 'Test failed.',
      );
    } finally {
      setTestingId(null);
    }
  };

  const handleRunCheck = async () => {
    if (dirty && canSave) {
      const ok = await handleSave();
      if (!ok) return;
    } else if (dirty) {
      setError('Save your changes before running a check.');
      return;
    }
    setChecking(true);
    setError(null);
    try {
      const { data } = await alertsApi.runCheck();
      if (data.triggered > 0) {
        setSuccess(`${data.triggered} watch(es) triggered on latest data.`);
      } else {
        setSuccess(data.message ?? 'No watches triggered on latest data.');
      }
      void refreshStatus();
    } catch (err) {
      setError(
        axios.isAxiosError(err)
          ? (err.response?.data as { detail?: string })?.detail ?? err.message
          : 'Check failed.',
      );
    } finally {
      setChecking(false);
    }
  };

  const updateRule = (index: number, patch: Partial<AlertRule>) => {
    setConfig((prev) => ({
      ...prev,
      alerts: prev.alerts.map((rule, i) => (i === index ? { ...rule, ...patch } : rule)),
    }));
  };

  const ruleIndex = (rule: AlertRule) => config.alerts.findIndex((item) => item.id === rule.id);

  const removeRule = (index: number) => {
    setConfig((prev) => ({ ...prev, alerts: prev.alerts.filter((_, i) => i !== index) }));
  };

  const setDeliveryPref = (key: 'notify_email' | 'notify_webhook', value: boolean) => {
    setConfig((prev) => ({ ...prev, defaults: { ...prev.defaults, [key]: value } }));
  };

  const handleAddRule = async () => {
    const symbol = newSymbol.trim().toUpperCase();
    const value = Number(newValue);
    if (!symbol || Number.isNaN(value)) {
      setError('Enter a valid symbol and price.');
      return;
    }
    const existing = findDuplicatePriceRule(config.alerts, symbol, newOperator, value);
    if (existing) {
      setSuccess(null);
      setError(`You already have a watch when ${formatCondition(existing).toLowerCase()}.`);
      return;
    }
    const rule: AlertRule = {
      id: slugify(`${symbol}_${newOperator}_${value}`) || 'price_alert',
      name: `${symbol} price alert`,
      enabled: true,
      condition: { type: 'price_threshold', symbol, operator: newOperator, value },
      notifications: buildNotifications(notifyEmail, notifyWebhook),
      cooldown_minutes: 60,
    };
    const nextConfig: AlertsConfig = { ...config, alerts: [...config.alerts, rule] };
    setConfig(nextConfig);
    setError(null);

    const readyToSave = canPersistConfig(nextConfig, channels, webhookDraft) === null;
    if (!readyToSave) {
      setSuccess(
        `${symbol} added — finish email or Discord/Slack above, then click Save now at the bottom.`,
      );
      return;
    }

    await persistConfig(
      nextConfig,
      `${symbol} is now watching — we check it automatically, no Fetch New needed.`,
    );
  };

  const composer = (
    <AlertComposer
      headline={userRules.length === 0 ? 'New watch' : 'Add another watch'}
      newSymbol={newSymbol}
      newOperator={newOperator}
      newValue={newValue}
      symbolOptions={symbolOptions}
      symbolsLoading={symbolsLoading}
      prices={symbolPrices}
      pendingPrices={pricingPending}
      quotesUnavailable={quotesUnavailable}
      apiReady={apiReady}
      onFetchPrices={(symbols) => void fetchPricesFor(symbols)}
      onSymbolChange={setNewSymbol}
      onOperatorChange={setNewOperator}
      onValueChange={setNewValue}
      onSubmit={() => void handleAddRule()}
      submitting={saving}
      canActivate={canSave}
    />
  );

  const watchesList =
    userRules.length > 0 ? (
      <div className={userRules.length >= COMPOSER_AFTER_COUNT ? 'mb-6' : 'mt-6'}>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.15em] text-slate-400">
          Active watches
        </h2>
        <ul className="space-y-3">
          {userRules.map((rule) => {
            const index = ruleIndex(rule);
            return (
              <RuleCard
                key={rule.id}
                rule={rule}
                index={index}
                testing={testingId === rule.id}
                symbolPrices={symbolPrices}
                allAlerts={config.alerts}
                onToggleEnabled={(i, enabled) => updateRule(i, { enabled })}
                onTest={(id) => void handleTest(id)}
                onRemove={removeRule}
                onUpdate={updateRule}
                onEditError={setError}
              />
            );
          })}
        </ul>
      </div>
    ) : null;

  if (loading) {
    return (
      <div className="alerts-page mx-auto max-w-2xl px-4 py-16 sm:px-6">
        <div className="space-y-4">
          <div className="h-8 w-48 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-700" />
          <div className="h-4 w-64 animate-pulse rounded bg-slate-100 dark:bg-slate-800" />
          <div className="alerts-card mt-8 h-48 animate-pulse bg-slate-50 dark:bg-slate-800/50" />
        </div>
      </div>
    );
  }

  return (
    <div className={`alerts-page ${dirty ? 'pb-28' : ''}`}>
      <div className="alerts-page-glow pointer-events-none absolute inset-x-0 top-0 h-80" aria-hidden />
      <AlertsToast error={error} success={success} />

      <div className="relative mx-auto max-w-2xl px-4 py-8 sm:px-6 lg:px-8">
        <header className="mb-8">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-600 dark:text-teal-400">
            Helmtower
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900 dark:text-slate-50">
            Price alerts
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Your portfolio lookout</p>
          <p className="mt-2 text-sm text-slate-600 dark:text-slate-400 sm:whitespace-nowrap">
            Set a target, walk away. We&apos;ll tap you the moment the market moves your way.
          </p>
          {exists && (
            <div className="mt-4 flex flex-wrap items-center gap-3">
              {userRules.length > 0 && (
                <div className="inline-flex items-center gap-2 rounded-full bg-white/80 px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm ring-1 ring-slate-200/80 dark:bg-slate-800/80 dark:text-slate-300 dark:ring-slate-700">
                  <span className="relative flex h-2 w-2">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-teal-400 opacity-60" />
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-teal-500" />
                  </span>
                  {activeCount} active · {userRules.length} total
                </div>
              )}
              <button
                type="button"
                onClick={() => void handleRunCheck()}
                disabled={checking || userRules.length === 0}
                className="rounded-full bg-white/80 px-3 py-1.5 text-xs font-medium text-teal-700 shadow-sm ring-1 ring-teal-200/80 transition hover:bg-teal-50 disabled:opacity-50 dark:bg-slate-800/80 dark:text-teal-400 dark:ring-teal-900"
              >
                {checking ? 'Checking…' : 'Check watches now'}
              </button>
            </div>
          )}
          {exists && alertStatus?.last_triggered_at && (
            <p className="mt-3 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
              Last alert: {new Date(alertStatus.last_triggered_at).toLocaleString()}.
            </p>
          )}
          {exists && (alertStatus?.latest_deliveries?.length ?? 0) > 0 && (
            <ul className="mt-2 space-y-1 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
              {alertStatus!.latest_deliveries.map((entry) => (
                <li
                  key={`${entry.channel}-${entry.timestamp}`}
                  className={
                    entry.success
                      ? 'text-slate-500 dark:text-slate-400'
                      : 'text-amber-700 dark:text-amber-300'
                  }
                >
                  {formatDeliveryStatusLine(entry)}
                </li>
              ))}
            </ul>
          )}
          {quotesUnavailable && (
            <p className="mt-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
              Live prices are unavailable — stop the old server on port 8000, then run{' '}
              <code className="font-mono">scripts/restart-dashboard-backend.ps1</code> and refresh.
            </p>
          )}
        </header>

        {!exists ? (
          <section className="alerts-onboard">
            <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-teal-400/10 blur-3xl" />
            <div className="relative">
              <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-teal-500 to-emerald-600 shadow-lg shadow-teal-500/30">
                <BellAlertIcon className="h-8 w-8 text-white" />
              </div>
              <h2 className="text-xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
                Helmtower keeps watch while you&apos;re away
              </h2>
              <p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                Set a price target on any company. We&apos;ll nudge you by email, Discord, or Slack.
              </p>
              <button
                type="button"
                onClick={() => void handleInit()}
                disabled={initializing}
                className="alerts-cta mt-8"
              >
                {initializing ? 'Setting up…' : 'Start watching'}
              </button>
            </div>
          </section>
        ) : (
          <div className="space-y-6">
            <section className="alerts-card p-6">
              <h2 className="text-sm font-semibold tracking-tight text-slate-900 dark:text-slate-100">
                How to reach you
              </h2>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Choose one or both — every watch uses the same channels.
              </p>
              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                <DeliveryChannel
                  enabled={notifyEmail}
                  onToggle={(v) => setDeliveryPref('notify_email', v)}
                  icon={EnvelopeIcon}
                  title="Email"
                  description="Inbox alerts"
                >
                  <input
                    type="email"
                    value={config.defaults?.email_to ?? ''}
                    onChange={(e) =>
                      setConfig((prev) => ({
                        ...prev,
                        defaults: { ...prev.defaults, email_to: e.target.value },
                      }))
                    }
                    placeholder="you@email.com"
                    className={fieldClass}
                  />
                  {channels && !channels.email_smtp && (
                    <p className="text-xs text-amber-600 dark:text-amber-400">
                      Email delivery isn&apos;t set up on this server yet.
                    </p>
                  )}
                </DeliveryChannel>

                <DeliveryChannel
                  enabled={notifyWebhook}
                  onToggle={(v) => setDeliveryPref('notify_webhook', v)}
                  icon={ChatBubbleLeftRightIcon}
                  title="Discord or Slack"
                  description="Channel notifications"
                >
                  {channels?.webhook_url && (
                    <p className="flex items-center gap-1.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                      Connected
                    </p>
                  )}
                  <div className="flex flex-wrap gap-2">
                    <PlatformChip
                      label="Discord"
                      active={config.defaults?.webhook_format !== 'slack'}
                      accent="discord"
                      disabled={!notifyWebhook}
                      onClick={() =>
                        setConfig((prev) => ({
                          ...prev,
                          defaults: { ...prev.defaults, webhook_format: 'discord' as WebhookFormat },
                        }))
                      }
                    />
                    <PlatformChip
                      label="Slack"
                      active={config.defaults?.webhook_format === 'slack'}
                      accent="slack"
                      disabled={!notifyWebhook}
                      onClick={() =>
                        setConfig((prev) => ({
                          ...prev,
                          defaults: { ...prev.defaults, webhook_format: 'slack' as WebhookFormat },
                        }))
                      }
                    />
                  </div>
                </DeliveryChannel>
              </div>

              {notifyWebhook && (
                <label htmlFor="webhook-url" className="mt-4 block">
                  <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
                    Webhook URL
                  </span>
                  <input
                    id="webhook-url"
                    type="password"
                    autoComplete="off"
                    spellCheck={false}
                    value={webhookDraft}
                    onChange={(e) => setWebhookDraft(e.target.value)}
                    placeholder={
                      channels?.webhook_url
                        ? 'Paste a new URL to replace the saved webhook'
                        : 'https://discord.com/api/webhooks/…'
                    }
                    className={`${webhookInputClass} mt-1.5`}
                  />
                  <span className="mt-1.5 block text-xs text-slate-400 dark:text-slate-500">
                    Stored on your server only — never shown in the UI after saving.
                  </span>
                </label>
              )}
            </section>

            <section>
              {userRules.length >= COMPOSER_AFTER_COUNT ? (
                <>
                  {watchesList}
                  {composer}
                </>
              ) : (
                <>
                  {composer}
                  {watchesList}
                </>
              )}
            </section>
          </div>
        )}
      </div>

      {dirty && (
        <div className="alerts-save-bar">
          <div className="mx-auto flex max-w-2xl items-center justify-between gap-4 px-4 py-3.5 sm:px-6">
            <p className="text-sm text-slate-600 dark:text-slate-300">
              {saving
                ? 'Saving…'
                : canSave
                  ? 'You have unsaved changes'
                  : 'Finish notification setup to save'}
            </p>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleDiscard}
                className="rounded-xl px-3 py-1.5 text-sm font-medium text-slate-600 transition hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                Discard
              </button>
              <button
                type="button"
                onClick={() => void handleSave()}
                disabled={saving || !canSave}
                className="alerts-cta px-4 py-1.5 text-sm disabled:opacity-50"
              >
                {saving ? 'Saving…' : 'Save now'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AlertsSettings;
