/**
 * Analytics-related API types.
 */

export interface DailySummary {
  date: string;
  account_id: string;
  gross_pnl: string;
  net_pnl: string;
  commissions: string;
  trade_count: number;
  win_count: number;
  loss_count: number;
}

export interface CalendarEntry {
  date: string;
  net_pnl: string;
  trade_count: number;
}

export interface SymbolBreakdown {
  symbol: string;
  net_pnl: string;
  trade_count: number;
  win_count: number;
  loss_count: number;
}

export interface StrategyBreakdown {
  strategy_tag: string;
  net_pnl: string;
  trade_count: number;
  group_count: number;
}

export interface PerformanceMetrics {
  total_pnl: string;
  total_commissions: string;
  net_pnl: string;
  total_trades: number;
  win_count: number;
  loss_count: number;
  win_rate: number;
  avg_win: string;
  avg_loss: string;
  profit_factor: number | null;
  expectancy: string;
  trading_days: number;
}
