/**
 * Import API endpoints.
 */

import {
  getApiBase,
  getHeaders,
  getUploadHeaders,
  handleResponse,
} from "./http";
import type { ImportResult, ImportLogListResponse } from "../types";

export async function uploadCsv(file: File): Promise<ImportResult> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${getApiBase()}/import/csv`, {
    method: "POST",
    headers: getUploadHeaders(),
    body: formData,
  });
  return handleResponse(response);
}

export async function fetchImportLogs(
  page = 1
): Promise<ImportLogListResponse> {
  const response = await fetch(`${getApiBase()}/import/logs?page=${page}`, {
    headers: getHeaders(),
  });
  return handleResponse(response);
}
