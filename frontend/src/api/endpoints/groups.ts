/**
 * Groups API endpoints.
 */

import { getApiBase, getHeaders, handleResponse } from "./http";
import type { TradeGroupDetail, TradeGroupListResponse } from "../types";

export async function fetchGroups(
  page = 1,
  status?: string,
  symbol?: string
): Promise<TradeGroupListResponse> {
  const params = new URLSearchParams({ page: String(page) });
  if (status) params.set("status", status);
  if (symbol) params.set("symbol", symbol);
  const response = await fetch(`${getApiBase()}/groups?${params}`, {
    headers: getHeaders(),
  });
  return handleResponse(response);
}

export async function fetchGroupDetail(
  id: string
): Promise<TradeGroupDetail> {
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
