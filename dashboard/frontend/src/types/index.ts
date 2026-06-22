// API Response Types

export interface IndexData {
  stocks: number;
  avgChange: number;
  gainers: number;
  losers: number;
}

export interface MarketOverview {
  date: string;
  totalStocks: number;
  gainers: number;
  losers: number;
  unchanged: number;
  averageChange: number;
  maxChange: number;
  minChange: number;
  indices: Record<string, IndexData>;
}

export interface StockMover {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number;
}

export interface MoversResponse {
  type: string;
  data: StockMover[];
}

export interface ProjectionsSummary {
  date: string;
  targetDate: string;
  totalProjections: number;
  averageConfidence: number;
  expectedMarketMove: number;
  sentiment: string;
  recommendations: Record<string, number>;
  trends: Record<string, number>;
  riskProfile: Record<string, number>;
}

export interface Opportunity {
  symbol: string;
  name: string;
  currentPrice: number;
  targetPrice: number;
  expectedChange: number;
  confidence: number;
  risk: string;
  trend: string;
  reason: string;
  volume: number;
  momentum?: number;
  volatility?: number;
}

export interface OpportunitiesResponse {
  type: string;
  count: number;
  opportunities: Opportunity[];
}

export interface CurrentData {
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  marketCap?: number;
}

export interface ProjectionData {
  targetDate: string;
  targetPrice: number;
  expectedChange: number;
  confidence: number;
  recommendation: string;
  risk: string;
  trend: string;
}

export interface TechnicalData {
  momentum?: number;
  volatility?: number;
  rsi?: number;
}

export interface StockDetail {
  symbol: string;
  name: string;
  currentData: CurrentData;
  projection?: ProjectionData;
  technical?: TechnicalData;
}

export interface HistoricalPoint {
  date: string;
  close: number;
  change: number;
  volume: number;
  projection?: {
    targetPrice: number;
    confidence: number;
    recommendation: string;
  };
}

export interface HistoricalData {
  symbol: string;
  data: HistoricalPoint[];
}

export interface DailySummaryPoint {
  date: string;
  totalProjections: number;
  averageConfidence: number;
  expectedMarketMove: number;
  sentiment: string;
  strongBuy: number;
  buy: number;
  hold: number;
  sell: number;
  strongSell: number;
}

export interface HistoricalSummaryResponse {
  dates: string[];
  data: DailySummaryPoint[];
  firstDate: string;
  lastDate: string;
  symbols?: string[];
  names?: Record<string, string>;
}

export interface AccuracyByRecommendation {
  count: number;
  meanAbsErrorPct: number | null;
}

export interface ProjectionAccuracyResponse {
  summary: {
    sampleCount: number;
    meanAbsErrorPct: number | null;
    byRecommendation: Record<string, AccuracyByRecommendation>;
  };
  samples: Array<{
    symbol: string;
    runDate: string;
    targetDate: string;
    actualDate: string;
    predicted: number;
    actual: number;
    absErrorPct: number;
    recommendation: string;
  }>;
}

export interface MarketSummaryResponse {
  date: string;
  summary: string;
  source: 'ai' | 'demo';
}

export type AlertNotification = 'log' | 'email' | 'webhook';
export type AlertOperator = 'less_than' | 'greater_than';
export type WebhookFormat = 'json' | 'slack' | 'discord';

export interface AlertCondition {
  type: 'price_threshold' | 'screening_match';
  symbol?: string;
  operator?: AlertOperator;
  value?: number;
  filters?: Record<string, number>;
}

export interface AlertRule {
  id: string;
  name: string;
  enabled: boolean;
  condition: AlertCondition;
  notifications: AlertNotification[];
  email_to?: string;
  webhook_url?: string;
  webhook_format?: WebhookFormat;
  cooldown_minutes?: number;
}

export interface AlertDefaults {
  email_to?: string;
  /** Write-only from the UI — never returned by the API after save. */
  webhook_url?: string;
  webhook_format?: WebhookFormat;
  notify_email?: boolean;
  notify_webhook?: boolean;
}

export interface AlertsConfig {
  defaults?: AlertDefaults;
  alerts: AlertRule[];
}

export interface ChannelStatus {
  email_smtp: boolean;
  email_recipients: boolean;
  webhook_url: boolean;
}

export interface AlertsConfigResponse {
  exists: boolean;
  config: AlertsConfig;
  channels: ChannelStatus;
}

export interface AlertTestResponse {
  alert_id: string;
  status: string;
  notifiers: string[];
  previews?: Array<{ notifier: string; payload: unknown }>;
}

export interface AlertDeliveryStatus {
  alert_id: string;
  channel: string;
  success: boolean;
  test: boolean;
  timestamp: string;
  error?: string | null;
}

export interface AlertsStatus {
  checks_on_fetch: boolean;
  last_data_date: string | null;
  tracked_symbols: string[];
  active_watches: number;
  last_triggered_at: string | null;
  latest_deliveries: AlertDeliveryStatus[];
}

export interface AlertsRunResponse {
  triggered: number;
  last_data_date: string | null;
  events: Array<{ alert_id: string; alert_name: string; symbols: string[] }>;
  message: string | null;
}

export interface User {
  id: string;
  email: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}
