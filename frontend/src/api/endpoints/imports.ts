/**
 * Import API endpoints.
 */

import {
  getApiBase,
  getHeaders,
  getUploadHeaders,
  handleResponse,
} from "./http";
import type { BatchImportResponse, ImportLogListResponse } from "../types";

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

export async function fetchImportLogs(
  page = 1
): Promise<ImportLogListResponse> {
  const response = await fetch(`${getApiBase()}/import/logs?page=${page}`, {
    headers: getHeaders(),
  });
  return handleResponse(response);
}
