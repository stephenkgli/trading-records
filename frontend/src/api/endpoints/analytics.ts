/**
 * Analytics API endpoints.
 */

import { getApiBase, getHeaders, handleResponse } from "./http";
import type {
  DailySummary,
  CalendarEntry,
  SymbolBreakdown,
  PerformanceMetrics,
} from "../types";

export async function fetchDailySummaries(
  from?: string,
  to?: string
): Promise<DailySummary[]> {
  const params = new URLSearchParams();
  if (from) params.set("from", from);
  if (to) params.set("to", to);
  const response = await fetch(`${getApiBase()}/analytics/daily?${params}`, {
    headers: getHeaders(),
  });
  return handleResponse(response);
}

export async function fetchCalendar(
  year: number,
  month: number
): Promise<CalendarEntry[]> {
  const response = await fetch(
    `${getApiBase()}/analytics/calendar?year=${year}&month=${month}`,
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
  const response = await fetch(
    `${getApiBase()}/analytics/by-symbol?${params}`,
    {
      headers: getHeaders(),
    }
  );
  return handleResponse(response);
}

export async function fetchPerformance(
  from?: string,
  to?: string
): Promise<PerformanceMetrics> {
  const params = new URLSearchParams();
  if (from) params.set("from", from);
  if (to) params.set("to", to);
  const response = await fetch(
    `${getApiBase()}/analytics/performance?${params}`,
    {
      headers: getHeaders(),
    }
  );
  return handleResponse(response);
}
