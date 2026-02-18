/**
 * Trade-related API types.
 */

export interface Trade {
  id: string;
  broker: string;
  broker_exec_id: string;
  import_log_id: string | null;
  account_id: string;
  symbol: string;
  underlying: string | null;
  asset_class: string;
  side: string;
  quantity: string;
  price: string;
  commission: string;
  executed_at: string;
  order_id: string | null;
  exchange: string | null;
  currency: string;
  created_at: string;
  updated_at: string;
}

export interface TradeListResponse {
  trades: Trade[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface TradeFilters {
  symbol?: string;
  broker?: string;
  asset_class?: string;
  from?: string;
  to?: string;
  page?: number;
  per_page?: number;
  sort?: string;
  order?: string;
}
