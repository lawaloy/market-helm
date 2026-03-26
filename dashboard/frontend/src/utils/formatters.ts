// Formatting utilities

export const formatPrice = (price: number): string => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(price);
};

export const formatNumber = (num: number): string => {
  return new Intl.NumberFormat('en-US').format(num);
};

export const formatPercentage = (percent: number, decimals: number = 2): string => {
  const sign = percent >= 0 ? '+' : '';
  return `${sign}${percent.toFixed(decimals)}%`;
};

export const formatVolume = (volume: number): string => {
  if (volume >= 1000000000) {
    return `${(volume / 1000000000).toFixed(2)}B`;
  } else if (volume >= 1000000) {
    return `${(volume / 1000000).toFixed(2)}M`;
  } else if (volume >= 1000) {
    return `${(volume / 1000).toFixed(2)}K`;
  }
  return volume.toString();
};

export const formatMarketCap = (marketCap: number): string => {
  if (marketCap >= 1000000000000) {
    return `$${(marketCap / 1000000000000).toFixed(2)}T`;
  } else if (marketCap >= 1000000000) {
    return `$${(marketCap / 1000000000).toFixed(2)}B`;
  } else if (marketCap >= 1000000) {
    return `$${(marketCap / 1000000).toFixed(2)}M`;
  }
  return `$${marketCap.toFixed(0)}`;
};

export const formatDate = (dateStr: string): string => {
  const parts = dateStr.split('-').map(Number);
  if (parts.length === 3 && parts.every((value) => !Number.isNaN(value))) {
    const [year, month, day] = parts;
    const date = new Date(year, month - 1, day);
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    }).format(date);
  }

  const date = new Date(dateStr);
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date);
};

export const getRecommendationColor = (recommendation: string): string => {
  switch (recommendation) {
    case 'STRONG BUY':
      return 'text-strong-buy bg-green-100 dark:bg-green-900/30';
    case 'BUY':
      return 'text-buy bg-green-50 dark:bg-green-900/20';
    case 'HOLD':
      return 'text-hold bg-slate-100 dark:bg-slate-700';
    case 'SELL':
      return 'text-sell bg-amber-100 dark:bg-amber-900/30';
    case 'STRONG SELL':
      return 'text-strong-sell bg-red-100 dark:bg-red-900/30';
    default:
      return 'text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-700';
  }
};

export const getRiskColor = (risk: string): string => {
  switch (risk) {
    case 'Low':
      return 'text-risk-low bg-green-100 dark:bg-green-900/30';
    case 'Medium':
      return 'text-risk-medium bg-amber-100 dark:bg-amber-900/30';
    case 'High':
      return 'text-risk-high bg-red-100 dark:bg-red-900/30';
    default:
      return 'text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-700';
  }
};

export const getTrendColor = (trend: string): string => {
  switch (trend) {
    case 'Bullish':
      return 'text-bullish';
    case 'Bearish':
      return 'text-bearish';
    default:
      return 'text-neutral';
  }
};

export const getTrendIcon = (trend: string): string => {
  switch (trend) {
    case 'Bullish':
      return '↗';
    case 'Bearish':
      return '↘';
    default:
      return '→';
  }
};

/** Display name from API when valid, else symbol */
export const getCompanyName = (symbol: string, apiName?: string): string =>
  apiName && apiName !== symbol ? apiName : symbol;

/** Narrow Recharts tooltip values (string | number | …) to a finite number. */
export function coerceTooltipNumber(value: unknown): number | undefined {
  if (value == null) return undefined;
  if (typeof value === 'number') return Number.isFinite(value) ? value : undefined;
  if (typeof value === 'string') {
    const n = Number(value);
    return Number.isFinite(n) ? n : undefined;
  }
  if (Array.isArray(value)) {
    const first = value[0];
    return coerceTooltipNumber(first);
  }
  return undefined;
}
