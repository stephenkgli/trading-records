/**
 * API client for the Trading Records backend.
 * Reads API key from localStorage and includes it in all requests.
 */

const API_BASE = "/api/v1";

function getHeaders(): HeadersInit {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };
  const apiKey = localStorage.getItem("apiKey");
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }
  return headers;
}

function getUploadHeaders(): HeadersInit {
  const headers: HeadersInit = {};
  const apiKey = localStorage.getItem("apiKey");
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }
  return headers;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

// Trades
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

export async function fetchTrades(filters: TradeFilters = {}): Promise<TradeListResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      params.set(key, String(value));
    }
  });
  const response = await fetch(`${API_BASE}/trades?${params}`, {
    headers: getHeaders(),
  });
  return handleResponse(response);
}

export async function fetchTradeDetail(id: string): Promise<Trade> {
  const response = await fetch(`${API_BASE}/trades/${id}`, {
    headers: getHeaders(),
  });
  return handleResponse(response);
}

// Import
export interface ImportResult {
  import_log_id: string;
  source: string;
  status: string;
  records_total: number;
  records_imported: number;
  records_skipped_dup: number;
  records_failed: number;
  errors: Array<Record<string, unknown>>;
}

export interface ImportLog {
  id: string;
  source: string;
  status: string;
  records_total: number;
  records_imported: number;
  records_skipped_dup: number;
  records_failed: number;
  errors: Record<string, unknown> | null;
  started_at: string;
  completed_at: string | null;
}

export interface ImportLogListResponse {
  logs: ImportLog[];
  total: number;
  page: number;
  per_page: number;
}

export async function uploadCsv(file: File): Promise<ImportResult> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE}/import/csv`, {
    method: "POST",
    headers: getUploadHeaders(),
    body: formData,
  });
  return handleResponse(response);
}

export async function triggerFlexQuery(): Promise<ImportResult> {
  const response = await fetch(`${API_BASE}/import/flex/trigger`, {
    method: "POST",
    headers: getHeaders(),
  });
  return handleResponse(response);
}

export async function fetchImportLogs(page = 1): Promise<ImportLogListResponse> {
  const response = await fetch(`${API_BASE}/import/logs?page=${page}`, {
    headers: getHeaders(),
  });
  return handleResponse(response);
}

// Analytics
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

export async function fetchDailySummaries(
  from?: string,
  to?: string
): Promise<DailySummary[]> {
  const params = new URLSearchParams();
  if (from) params.set("from", from);
  if (to) params.set("to", to);
  const response = await fetch(`${API_BASE}/analytics/daily?${params}`, {
    headers: getHeaders(),
  });
  return handleResponse(response);
}

export async function fetchCalendar(
  year: number,
  month: number
): Promise<CalendarEntry[]> {
  const response = await fetch(
    `${API_BASE}/analytics/calendar?year=${year}&month=${month}`,
    { headers: getHeaders() }
  );
  return handleResponse(response);
}

export async function fetchBySymbol(
  from?: string,
  to?: string
): Promise<SymbolBreakdown[]> {
  const params = new URLSearchParams();
  if (from) params.set("from", from);
  if (to) params.set("to", to);
  const response = await fetch(`${API_BASE}/analytics/by-symbol?${params}`, {
    headers: getHeaders(),
  });
  return handleResponse(response);
}

export async function fetchPerformance(
  from?: string,
  to?: string
): Promise<PerformanceMetrics> {
  const params = new URLSearchParams();
  if (from) params.set("from", from);
  if (to) params.set("to", to);
  const response = await fetch(`${API_BASE}/analytics/performance?${params}`, {
    headers: getHeaders(),
  });
  return handleResponse(response);
}

// Groups
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

export async function fetchGroups(
  page = 1,
  status?: string,
  symbol?: string
): Promise<TradeGroupListResponse> {
  const params = new URLSearchParams({ page: String(page) });
  if (status) params.set("status", status);
  if (symbol) params.set("symbol", symbol);
  const response = await fetch(`${API_BASE}/groups?${params}`, {
    headers: getHeaders(),
  });
  return handleResponse(response);
}

export async function fetchGroupDetail(id: string): Promise<TradeGroupDetail> {
  const response = await fetch(`${API_BASE}/groups/${id}`, {
    headers: getHeaders(),
  });
  return handleResponse(response);
}

export async function recomputeGroups(
  symbol?: string
): Promise<{ groups_created: number; groups_closed: number }> {
  const params = symbol ? `?symbol=${symbol}` : "";
  const response = await fetch(`${API_BASE}/groups/recompute${params}`, {
    method: "POST",
    headers: getHeaders(),
  });
  return handleResponse(response);
}
