import { describe, it, expect, vi, beforeEach } from "vitest";
import { uploadCsv, fetchImportLogs } from "./endpoints/imports";
import { fetchGroups } from "./endpoints/groups";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  mockFetch.mockReset();
});

describe("uploadCsv", () => {
  it("sends POST with FormData to /api/v1/import/csv", async () => {
    const responseData = {
      aggregate: {
        status: "success",
        files_total: 1,
        files_success: 1,
        files_partial: 0,
        files_failed: 0,
        records_total: 10,
        records_imported: 10,
        records_skipped_dup: 0,
        records_failed: 0,
      },
      files: [],
    };
    mockFetch.mockResolvedValueOnce(jsonResponse(responseData));

    const file = new File(["test"], "trades.csv", { type: "text/csv" });
    const result = await uploadCsv([file]);

    expect(mockFetch).toHaveBeenCalledOnce();
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/v1/import/csv");
    expect(options.method).toBe("POST");
    expect(options.body).toBeInstanceOf(FormData);
    expect(result.aggregate.status).toBe("success");
  });
});

describe("fetchImportLogs", () => {
  it("fetches import logs with default page=1", async () => {
    const responseData = { logs: [], total: 0, page: 1, per_page: 20 };
    mockFetch.mockResolvedValueOnce(jsonResponse(responseData));

    const result = await fetchImportLogs();

    expect(mockFetch).toHaveBeenCalledOnce();
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/v1/import/logs?page=1");
    expect(result.total).toBe(0);
  });
});

describe("fetchGroups", () => {
  it("builds query params correctly", async () => {
    const responseData = { groups: [], total: 0, page: 1, per_page: 20 };
    mockFetch.mockResolvedValueOnce(jsonResponse(responseData));

    await fetchGroups(2, "closed", "ES", "realized_pnl", "desc", ["FUT"]);

    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain("page=2");
    expect(url).toContain("status=closed");
    expect(url).toContain("symbol=ES");
    expect(url).toContain("sort=realized_pnl");
    expect(url).toContain("order=desc");
    expect(url).toContain("asset_classes=FUT");
  });

  it("omits optional params when not provided", async () => {
    const responseData = { groups: [], total: 0, page: 1, per_page: 20 };
    mockFetch.mockResolvedValueOnce(jsonResponse(responseData));

    await fetchGroups();

    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/v1/groups?page=1");
  });
});
