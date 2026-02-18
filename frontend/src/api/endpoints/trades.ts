/**
 * Trade API endpoints.
 */

import { getApiBase, getHeaders, handleResponse } from "./http";
import type { Trade, TradeListResponse, TradeFilters } from "../types";

export async function fetchTrades(
  filters: TradeFilters = {}
): Promise<TradeListResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      params.set(key, String(value));
    }
  });
  const response = await fetch(`${getApiBase()}/trades?${params}`, {
    headers: getHeaders(),
  });
  return handleResponse(response);
}

export async function fetchTradeDetail(id: string): Promise<Trade> {
  const response = await fetch(`${getApiBase()}/trades/${id}`, {
    headers: getHeaders(),
  });
  return handleResponse(response);
}
