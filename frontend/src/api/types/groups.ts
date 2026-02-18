/**
 * Group-related API types.
 */

export interface TradeGroup {
  id: string;
  account_id: string;
  symbol: string;
  asset_class: string;
  direction: string;
  strategy_tag: string | null;
  status: string;
  realized_pnl: string | null;
  opened_at: string;
  closed_at: string | null;
  notes: string | null;
}

export interface TradeGroupLeg {
  id: string;
  trade_group_id: string;
  trade_id: string;
  role: string;
}

export interface TradeGroupDetail extends TradeGroup {
  legs: TradeGroupLeg[];
}

export interface TradeGroupListResponse {
  groups: TradeGroup[];
  total: number;
  page: number;
  per_page: number;
}
