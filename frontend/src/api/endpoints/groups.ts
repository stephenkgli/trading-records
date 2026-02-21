/**
 * Groups API endpoints.
 */

import { getApiBase, getHeaders, handleResponse } from "./http";
import type { TradeGroupDetail, TradeGroupListResponse, GroupChartData } from "../types";

export async function fetchGroups(
  page = 1,
  status?: string,
  symbol?: string,
  sort?: string,
  order?: "asc" | "desc"
): Promise<TradeGroupListResponse> {
  const params = new URLSearchParams({ page: String(page) });
  if (status) params.set("status", status);
  if (symbol) params.set("symbol", symbol);
  if (sort) params.set("sort", sort);
  if (order) params.set("order", order);
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

export async function fetchGroupChart(
  groupId: string
): Promise<GroupChartData> {
  const response = await fetch(`${getApiBase()}/groups/${groupId}/chart`, {
    headers: getHeaders(),
  });
  return handleResponse(response);
}
