import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { fetchTrades, type TradeFilters } from "../api/client";
import TradeTable from "../components/TradeTable";

export default function TradesPage() {
  const [filters, setFilters] = useState<TradeFilters>({
    page: 1,
    per_page: 50,
    sort: "executed_at",
    order: "desc",
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ["trades", filters],
    queryFn: () => fetchTrades(filters),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Trades</h1>
        <div className="flex items-center space-x-2">
          <input
            type="text"
            placeholder="Filter by symbol..."
            className="border border-gray-300 rounded-md px-3 py-1.5 text-sm"
            value={filters.symbol || ""}
            onChange={(e) =>
              setFilters((f) => ({ ...f, symbol: e.target.value, page: 1 }))
            }
          />
          <select
            className="border border-gray-300 rounded-md px-3 py-1.5 text-sm"
            value={filters.broker || ""}
            onChange={(e) =>
              setFilters((f) => ({ ...f, broker: e.target.value, page: 1 }))
            }
          >
            <option value="">All Brokers</option>
            <option value="ibkr">IBKR</option>
            <option value="tradovate">Tradovate</option>
          </select>
        </div>
      </div>

      {isLoading && <div className="text-center py-8 text-gray-400">Loading trades...</div>}
      {error && <div className="text-center py-8 text-red-500">Error: {(error as Error).message}</div>}

      {data && (
        <>
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <TradeTable trades={data.trades} />
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between text-sm text-gray-500">
            <span>
              Showing {(data.page - 1) * data.per_page + 1}
              {" - "}
              {Math.min(data.page * data.per_page, data.total)} of {data.total}
            </span>
            <div className="flex space-x-2">
              <button
                onClick={() => setFilters((f) => ({ ...f, page: (f.page || 1) - 1 }))}
                disabled={data.page <= 1}
                className="px-3 py-1 border rounded disabled:opacity-50"
              >
                Previous
              </button>
              <button
                onClick={() => setFilters((f) => ({ ...f, page: (f.page || 1) + 1 }))}
                disabled={data.page >= data.pages}
                className="px-3 py-1 border rounded disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
