import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  getApiBase,
  getHeaders,
  getUploadHeaders,
  applyAssetClassParams,
  handleResponse,
} from "./http";

describe("getApiBase", () => {
  it("returns /api/v1", () => {
    expect(getApiBase()).toBe("/api/v1");
  });
});

describe("getHeaders", () => {
  it("includes Content-Type application/json", () => {
    const headers = getHeaders();
    expect(headers).toEqual({ "Content-Type": "application/json" });
  });
});

describe("getUploadHeaders", () => {
  it("returns empty object (browser sets multipart boundary)", () => {
    expect(getUploadHeaders()).toEqual({});
  });
});

describe("applyAssetClassParams", () => {
  it("does nothing when assetClasses is undefined", () => {
    const params = new URLSearchParams();
    applyAssetClassParams(params, undefined);
    expect(params.has("asset_classes")).toBe(false);
  });

  it("sets comma-separated asset_classes for non-empty array", () => {
    const params = new URLSearchParams();
    applyAssetClassParams(params, ["STK", "FUT"]);
    expect(params.get("asset_classes")).toBe("STK,FUT");
  });

  it("sets empty string for empty array", () => {
    const params = new URLSearchParams();
    applyAssetClassParams(params, []);
    expect(params.get("asset_classes")).toBe("");
  });
});

describe("handleResponse", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("returns parsed JSON for ok response", async () => {
    const data = { id: "123", name: "test" };
    const response = new Response(JSON.stringify(data), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
    const result = await handleResponse(response);
    expect(result).toEqual(data);
  });

  it("throws with detail message for error response", async () => {
    const response = new Response(JSON.stringify({ detail: "Not found" }), {
      status: 404,
      headers: { "Content-Type": "application/json" },
    });
    await expect(handleResponse(response)).rejects.toThrow("Not found");
  });

  it("throws with HTTP status when error response is not JSON", async () => {
    const response = new Response("server error", {
      status: 500,
      statusText: "Internal Server Error",
    });
    await expect(handleResponse(response)).rejects.toThrow("Internal Server Error");
  });
});
