/**
 * React hooks for API data fetching.
 *
 * These hooks encapsulate the fetch-state-error lifecycle so pages
 * can consume data without duplicating loading/error boilerplate.
 */

import { useCallback, useEffect, useState } from "react";

import {
  fetchImportLogs,
  fetchDailySummaries,
  fetchCalendar,
  fetchBySymbol,
  fetchPerformance,
  fetchGroups,
  fetchGroupDetail,
} from "../endpoints";

import type {
  ImportLogListResponse,
  DailySummary,
  CalendarEntry,
  SymbolBreakdown,
  PerformanceMetrics,
  TradeGroupDetail,
  TradeGroupListResponse,
} from "../types";

// ---------------------------------------------------------------------------
// Generic hook
// ---------------------------------------------------------------------------

interface UseQueryResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

function useQuery<T>(fetcher: () => Promise<T>, deps: unknown[]): UseQueryResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(() => {
    setLoading(true);
    setError(null);
    fetcher()
      .then(setData)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { data, loading, error, refetch };
}

// ---------------------------------------------------------------------------
// Import hooks
// ---------------------------------------------------------------------------

export function useImportLogs(page = 1): UseQueryResult<ImportLogListResponse> {
  return useQuery(() => fetchImportLogs(page), [page]);
}

// ---------------------------------------------------------------------------
// Analytics hooks
// ---------------------------------------------------------------------------

export function useDailySummaries(
  from?: string,
  to?: string
): UseQueryResult<DailySummary[]> {
  return useQuery(() => fetchDailySummaries(from, to), [from, to]);
}

export function useCalendar(
  year: number,
  month: number
): UseQueryResult<CalendarEntry[]> {
  return useQuery(() => fetchCalendar(year, month), [year, month]);
}

export function useBySymbol(
  from?: string,
  to?: string
): UseQueryResult<SymbolBreakdown[]> {
  return useQuery(() => fetchBySymbol(from, to), [from, to]);
}

export function usePerformance(
  from?: string,
  to?: string
): UseQueryResult<PerformanceMetrics> {
  return useQuery(() => fetchPerformance(from, to), [from, to]);
}

// ---------------------------------------------------------------------------
// Group hooks
// ---------------------------------------------------------------------------

export function useGroups(
  page = 1,
  status?: string,
  symbol?: string
): UseQueryResult<TradeGroupListResponse> {
  return useQuery(() => fetchGroups(page, status, symbol), [page, status, symbol]);
}

export function useGroupDetail(id: string): UseQueryResult<TradeGroupDetail> {
  return useQuery(() => fetchGroupDetail(id), [id]);
}
