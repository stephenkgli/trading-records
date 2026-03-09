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

export interface ActiveGroup extends TradeGroup {
  day_roles: string[];
}

export interface ActiveGroupsListResponse {
  groups: ActiveGroup[];
}

export interface CandleData {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export type MarkerPosition = "aboveBar" | "belowBar" | "inBar";
export type MarkerShape = "arrowUp" | "arrowDown" | "circle" | "square";
export type TradeRole = "entry" | "add" | "trim" | "exit";

export interface MarkerData {
  time: number;
  price: number;
  position: MarkerPosition;
  color: string;
  shape: MarkerShape;
  text: string;
  role: TradeRole;
  trade_id: string;
}

export interface GroupChartSummary {
  direction: string;
  realized_pnl: string | null;
  opened_at: string;
  closed_at: string | null;
}

export interface GroupChartData {
  symbol: string;
  interval: string;
  candles: CandleData[];
  markers: MarkerData[];
  group: GroupChartSummary;
}
