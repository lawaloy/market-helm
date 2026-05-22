import { useState } from 'react';
import {
  ArrowTrendingDownIcon,
  ArrowTrendingUpIcon,
  BellAlertIcon,
  PaperAirplaneIcon,
  PencilSquareIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';
import type { AlertRule } from '../../types';
import {
  findDuplicatePriceRule,
  formatCondition,
  formatPrice,
  formatQuotePrice,
  ruleTitle,
  slugify,
  symbolGradient,
} from './alertsUtils';
import { SymbolBadge, Toggle } from './AlertsUi';

export function RuleCard({
  rule,
  index,
  testing,
  symbolPrices,
  onToggleEnabled,
  onTest,
  onRemove,
  onUpdate,
  onEditError,
  allAlerts,
}: {
  rule: AlertRule;
  index: number;
  testing: boolean;
  symbolPrices: Record<string, number>;
  onToggleEnabled: (index: number, enabled: boolean) => void;
  onTest: (id: string) => void;
  onRemove: (index: number) => void;
  onUpdate: (index: number, patch: Partial<AlertRule>) => void;
  onEditError: (message: string) => void;
  allAlerts: AlertRule[];
}) {
  const [editing, setEditing] = useState(false);
  const isPrice = rule.condition.type === 'price_threshold';
  const symbol = isPrice ? (rule.condition.symbol ?? '?').toUpperCase() : '?';
  const isRise = isPrice && rule.condition.operator === 'greater_than';
  const price = isPrice ? formatPrice(rule.condition.value) : null;
  const currentQuote = isPrice ? formatQuotePrice(symbolPrices[symbol]) : null;

  const [editOperator, setEditOperator] = useState<'less_than' | 'greater_than'>(
    isPrice && rule.condition.operator === 'greater_than' ? 'greater_than' : 'less_than',
  );
  const [editValue, setEditValue] = useState(
    isPrice && rule.condition.value !== undefined ? String(rule.condition.value) : '',
  );

  const saveEdit = () => {
    if (!isPrice) return;
    const value = Number(editValue);
    if (Number.isNaN(value)) {
      onEditError('Enter a valid price.');
      return;
    }
    const existing = findDuplicatePriceRule(allAlerts, symbol, editOperator, value);
    if (existing && existing.id !== rule.id) {
      onEditError(`You already have a watch when ${formatCondition(existing).toLowerCase()}.`);
      return;
    }
    onUpdate(index, {
      id: slugify(`${symbol}_${editOperator}_${value}`) || rule.id,
      condition: { type: 'price_threshold', symbol, operator: editOperator, value },
    });
    setEditing(false);
  };

  return (
    <li
      className={`alerts-rule-card group ${
        rule.enabled ? 'alerts-rule-card-active' : 'alerts-rule-card-paused'
      }`}
    >
      <div className="flex items-start gap-4">
        {isPrice ? (
          <SymbolBadge symbol={symbol} gradient={symbolGradient(symbol)} />
        ) : (
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-500 dark:bg-slate-700">
            <BellAlertIcon className="h-5 w-5" />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p
              className={`text-base font-semibold tracking-tight ${
                rule.enabled ? 'text-slate-900 dark:text-slate-100' : 'text-slate-500'
              }`}
            >
              {isPrice ? symbol : rule.name}
            </p>
            {currentQuote && (
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold tabular-nums tracking-wide text-slate-600 dark:bg-slate-700 dark:text-slate-300">
                Now {currentQuote}
              </span>
            )}
            {rule.enabled ? (
              <span className="rounded-full bg-teal-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-teal-700 dark:text-teal-400">
                Watching
              </span>
            ) : (
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:bg-slate-700">
                Paused
              </span>
            )}
          </div>
          {editing && isPrice ? (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <select
                value={editOperator}
                onChange={(e) => setEditOperator(e.target.value as 'less_than' | 'greater_than')}
                className="alerts-inline-select text-sm"
              >
                <option value="less_than">Falls below</option>
                <option value="greater_than">Rises above</option>
              </select>
              <span className="inline-flex items-center gap-0.5 text-sm text-slate-500">
                $
                <input
                  type="number"
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  className="alerts-inline-input w-24 text-sm"
                />
              </span>
              <button type="button" onClick={saveEdit} className="text-xs font-medium text-teal-600 hover:underline">
                Save
              </button>
              <button
                type="button"
                onClick={() => setEditing(false)}
                className="text-xs font-medium text-slate-500 hover:underline"
              >
                Cancel
              </button>
            </div>
          ) : (
            isPrice &&
            price && (
              <div className="mt-1.5 flex items-center gap-2">
                <span
                  className={`inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-xs font-medium ${
                    isRise
                      ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400'
                      : 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400'
                  }`}
                >
                  {isRise ? (
                    <ArrowTrendingUpIcon className="h-3.5 w-3.5" />
                  ) : (
                    <ArrowTrendingDownIcon className="h-3.5 w-3.5" />
                  )}
                  {isRise ? 'Rises above' : 'Falls below'}
                </span>
                <span className="text-lg font-semibold tabular-nums tracking-tight text-slate-900 dark:text-slate-100">
                  ${price}
                </span>
              </div>
            )
          )}
          {!isPrice && (
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{formatCondition(rule)}</p>
          )}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2 sm:flex-row sm:items-center">
          <Toggle
            enabled={rule.enabled}
            onChange={(enabled) => onToggleEnabled(index, enabled)}
            label={`Enable ${ruleTitle(rule)}`}
          />
          <div className="flex items-center gap-0.5 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100">
            {isPrice && !editing && (
              <button
                type="button"
                onClick={() => setEditing(true)}
                title="Edit"
                className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800"
              >
                <PencilSquareIcon className="h-4 w-4" />
              </button>
            )}
            <button
              type="button"
              onClick={() => onTest(rule.id)}
              disabled={testing}
              title="Send test"
              className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 hover:text-teal-600 dark:hover:bg-slate-800"
            >
              <PaperAirplaneIcon className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => onRemove(index)}
              title="Remove"
              className="rounded-lg p-2 text-slate-400 transition hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/30"
            >
              <TrashIcon className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </li>
  );
}
