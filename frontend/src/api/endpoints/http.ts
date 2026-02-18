/**
 * Shared HTTP utilities for API endpoints.
 */

const API_BASE = "/api/v1";

export function getApiBase(): string {
  return API_BASE;
}

export function getHeaders(): HeadersInit {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };
  const apiKey = localStorage.getItem("apiKey");
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }
  return headers;
}

export function getUploadHeaders(): HeadersInit {
  const headers: HeadersInit = {};
  const apiKey = localStorage.getItem("apiKey");
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }
  return headers;
}

export async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}
