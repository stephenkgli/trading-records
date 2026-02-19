/**
 * Analytics API endpoints.
 *
 * Date-range views use the generic `makeDateRangeFetcher` factory.
 * Calendar and asset-class list keep explicit functions due to different parameters.
 */

import { getApiBase, getHeaders, handleResponse } from "./http";
import type {
  DailySummary,
  CalendarEntry,
  SymbolBreakdown,
  PerformanceMetrics,
} from "../types";

/**
 * Append `asset_classes` to the given URLSearchParams.
 *
 * Semantics match the backend contract:
 * - `undefined`  -> param omitted, backend returns all asset classes
 * - `[]`         -> param set to empty string, backend returns empty results
 * - `[...items]` -> param set to comma-joined values
 */
function applyAssetClassParams(
  params: URLSearchParams,
  assetClasses?: string[],
): void {
  if (assetClasses === undefined) return;
  if (assetClasses.length > 0) {
    params.set("asset_classes", assetClasses.join(","));
  } else {
    params.set("asset_classes", "");
  }
}

// -- Generic date-range fetcher factory --

function makeDateRangeFetcher<T>(path: string) {
  return async (
    from?: string,
    to?: string,
    assetClasses?: string[],
  ): Promise<T> => {
    const params = new URLSearchParams();
    if (from) params.set("from", from);
    if (to) params.set("to", to);
    applyAssetClassParams(params, assetClasses);
    const qs = params.toString();
    const url = `${getApiBase()}/analytics/${path}${qs ? `?${qs}` : ""}`;
    const response = await fetch(url, { headers: getHeaders() });
    return handleResponse(response);
  };
}

// -- Exported fetch functions --

export const fetchDailySummaries = makeDateRangeFetcher<DailySummary[]>("daily");
export const fetchBySymbol = makeDateRangeFetcher<SymbolBreakdown[]>("by-symbol");
export const fetchPerformance = makeDateRangeFetcher<PerformanceMetrics>("performance");

/** Calendar has different params (year/month), stays explicit. */
export async function fetchCalendar(
  year: number,
  month: number,
): Promise<CalendarEntry[]> {
  const response = await fetch(
    `${getApiBase()}/analytics/calendar?year=${year}&month=${month}`,
    { headers: getHeaders() },
  );
  return handleResponse(response);
}

/** Fetch the list of asset classes that have trade data. */
export async function fetchAvailableAssetClasses(): Promise<string[]> {
  const response = await fetch(`${getApiBase()}/analytics/asset-classes`, {
    headers: getHeaders(),
  });
  return handleResponse(response);
}
