import { CheckCircleIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline';

export function Toggle({
  enabled,
  onChange,
  label,
}: {
  enabled: boolean;
  onChange: (value: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      aria-label={label}
      onClick={() => onChange(!enabled)}
      className={`relative inline-flex h-7 w-12 shrink-0 rounded-full transition-all duration-200 ${
        enabled ? 'alerts-toggle-on' : 'bg-slate-200 dark:bg-slate-600'
      }`}
    >
      <span
        className={`inline-block h-6 w-6 translate-y-0.5 rounded-full bg-white shadow-md transition-transform duration-200 ${
          enabled ? 'translate-x-5' : 'translate-x-0.5'
        }`}
      />
    </button>
  );
}

export function PlatformChip({
  label,
  active,
  accent,
  disabled,
  onClick,
}: {
  label: string;
  active: boolean;
  accent?: 'discord' | 'slack';
  disabled?: boolean;
  onClick: () => void;
}) {
  const activeClass =
    accent === 'discord'
      ? 'bg-[#5865F2] text-white shadow-md shadow-[#5865F2]/30'
      : accent === 'slack'
        ? 'bg-[#4A154B] text-white shadow-md shadow-[#4A154B]/30'
        : 'bg-teal-600 text-white shadow-md shadow-teal-600/25';

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`rounded-full px-4 py-1.5 text-xs font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-40 ${
        active
          ? activeClass
          : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-600'
      }`}
    >
      {label}
    </button>
  );
}

export function SymbolBadge({ symbol, gradient }: { symbol: string; gradient: string }) {
  return (
    <div
      className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${gradient} text-xs font-bold tracking-tight text-white shadow-md`}
    >
      {symbol.slice(0, 4)}
    </div>
  );
}

export function AlertsToast({ error, success }: { error: string | null; success: string | null }) {
  if (!error && !success) return null;
  return (
    <div
      className={`alerts-toast ${
        error
          ? 'border-amber-200/80 bg-amber-50/95 text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/90 dark:text-amber-100'
          : 'border-emerald-200/80 bg-emerald-50/95 text-emerald-900 dark:border-emerald-900/50 dark:bg-emerald-950/90 dark:text-emerald-100'
      }`}
      role="status"
    >
      {error ? (
        <ExclamationTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" />
      ) : (
        <CheckCircleIcon className="mt-0.5 h-4 w-4 shrink-0" />
      )}
      <span>{error ?? success}</span>
    </div>
  );
}
