import type { ComponentType, ReactNode } from 'react';
import { Toggle } from './AlertsUi';

export function DeliveryChannel({
  enabled,
  onToggle,
  icon: Icon,
  title,
  description,
  children,
}: {
  enabled: boolean;
  onToggle: (value: boolean) => void;
  icon: ComponentType<{ className?: string }>;
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <div className={`alerts-channel ${enabled ? 'alerts-channel-active' : ''}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex gap-3">
          <div
            className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition-colors ${
              enabled
                ? 'bg-teal-500/15 text-teal-600 dark:text-teal-400'
                : 'bg-slate-200/80 text-slate-500 dark:bg-slate-700 dark:text-slate-400'
            }`}
          >
            <Icon className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{title}</p>
            <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{description}</p>
          </div>
        </div>
        <Toggle enabled={enabled} onChange={onToggle} label={title} />
      </div>
      {enabled && children && <div className="mt-4 space-y-3">{children}</div>}
    </div>
  );
}
