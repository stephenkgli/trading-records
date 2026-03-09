/**
 * Groups API endpoints.
 */

import { getApiBase, getHeaders, handleResponse } from "./http";
import type { TradeGroupDetail, TradeGroupListResponse, GroupChartData } from "../types";

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
