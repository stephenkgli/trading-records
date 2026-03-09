/**
 * API client for the Trading Records backend.
 */

import {
  applyAssetClassParams,
  getApiBase,
  getHeaders,
  getUploadHeaders,
  handleResponse,
} from "./endpoints/http";

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

export interface FileImportResult {
  filename: string;
  status: string;
  import_log_id: string | null;
  source: string;
  records_total: number;
  records_imported: number;
  records_skipped_dup: number;
  records_failed: number;
  errors: Array<Record<string, unknown>>;
  file_error: string | null;
}

export interface BatchImportAggregate {
  status: string;
  files_total: number;
  files_success: number;
  files_partial: number;
  files_failed: number;
  records_total: number;
  records_imported: number;
  records_skipped_dup: number;
  records_failed: number;
}

export interface BatchImportResponse {
  aggregate: BatchImportAggregate;
  files: FileImportResult[];
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
  trade_date_from: string | null;
  trade_date_to: string | null;
  broker: string | null;
}

export interface ImportLogListResponse {
  logs: ImportLog[];
  total: number;
  page: number;
  per_page: number;
}

export async function uploadCsv(files: File[]): Promise<BatchImportResponse> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("file", file);
  }

  const response = await fetch(`${getApiBase()}/import/csv`, {
    method: "POST",
    headers: getUploadHeaders(),
    body: formData,
  });
  return handleResponse(response);
}

export async function fetchImportLogs(page = 1): Promise<ImportLogListResponse> {
  const response = await fetch(`${getApiBase()}/import/logs?page=${page}`, {
    headers: getHeaders(),
  });
  return handleResponse(response);
}

// Analytics — re-exported from endpoints/analytics
export type {
  DailySummary,
  CalendarEntry,
  SymbolBreakdown,
  PerformanceMetrics,
} from "./types";

export {
  fetchDailySummaries,
  fetchCalendar,
  fetchBySymbol,
  fetchPerformance,
  fetchAvailableAssetClasses,
} from "./endpoints/analytics";

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
  symbol?: string,
  sort?: string,
  order?: "asc" | "desc",
  assetClasses?: string[],
  closedFrom?: string,
  closedTo?: string,
): Promise<TradeGroupListResponse> {
  const params = new URLSearchParams({ page: String(page) });
  if (status) params.set("status", status);
  if (symbol) params.set("symbol", symbol);
  if (sort) params.set("sort", sort);
  if (order) params.set("order", order);
  applyAssetClassParams(params, assetClasses);
  if (closedFrom) params.set("closed_from", closedFrom);
  if (closedTo) params.set("closed_to", closedTo);
  const response = await fetch(`${getApiBase()}/groups?${params}`, {
    headers: getHeaders(),
  });
  return handleResponse(response);
}

export async function fetchGroupDetail(id: string): Promise<TradeGroupDetail> {
  const response = await fetch(`${getApiBase()}/groups/${id}`, {
    headers: getHeaders(),
  });
  return handleResponse(response);
}

export async function recomputeGroups(
  symbol?: string
): Promise<{ groups_created: number; groups_closed: number }> {
  const params = symbol ? `?symbol=${symbol}` : "";
  const response = await fetch(`${getApiBase()}/groups/recompute${params}`, {
    method: "POST",
    headers: getHeaders(),
  });
  return handleResponse(response);
}
