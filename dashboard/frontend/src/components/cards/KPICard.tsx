import React from 'react';

interface KPICardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode;
  trend?: 'up' | 'down' | 'neutral';
}

const KPICard: React.FC<KPICardProps> = ({ title, value, subtitle, icon, trend }) => {
  const getTrendColor = () => {
    switch (trend) {
      case 'up':
        return 'text-green-700 dark:text-green-300';
      case 'down':
        return 'text-red-700 dark:text-red-300';
      default:
        return 'text-slate-600 dark:text-slate-400';
    }
  };

  return (
    <div className="min-w-0 border-l border-slate-200 pl-4 first:border-l-0 first:pl-0 dark:border-[#2a3b51]">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-slate-600 dark:text-slate-400">
            {title}
          </p>
          <p className="font-data mt-1 text-xl font-medium text-slate-950 dark:text-slate-50">
            {value}
          </p>
          {subtitle && <p className={`mt-1 text-xs ${getTrendColor()}`}>{subtitle}</p>}
        </div>
        {icon && <div className="text-slate-400 dark:text-slate-500">{icon}</div>}
      </div>
    </div>
  );
};

export default KPICard;
