/**
 * Analytics API endpoints.
 *
 * Date-range views use the generic `makeDateRangeFetcher` factory.
 * Calendar keeps an explicit function due to its different parameters.
 */

import { getApiBase, getHeaders, handleResponse } from "./http";
import type {
  DailySummary,
  CalendarEntry,
  SymbolBreakdown,
  PerformanceMetrics,
} from "../types";

// -- Generic date-range fetcher factory --

function makeDateRangeFetcher<T>(path: string) {
  return async (from?: string, to?: string): Promise<T> => {
    const params = new URLSearchParams();
    if (from) params.set("from", from);
    if (to) params.set("to", to);
    const qs = params.toString();
    const url = `${getApiBase()}/analytics/${path}${qs ? `?${qs}` : ""}`;
    const response = await fetch(url, { headers: getHeaders() });
    return handleResponse(response);
  };
}

// -- Exported fetch functions (same signatures as before) --

export const fetchDailySummaries = makeDateRangeFetcher<DailySummary[]>("daily");
export const fetchBySymbol = makeDateRangeFetcher<SymbolBreakdown[]>("by-symbol");
export const fetchPerformance = makeDateRangeFetcher<PerformanceMetrics>("performance");

// Calendar has different params, stays explicit
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
