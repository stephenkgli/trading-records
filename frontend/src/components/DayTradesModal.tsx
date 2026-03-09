import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useState } from "react";
import { fetchGroups } from "../api/client";
import { formatDateTime } from "../utils/date";

const TradeChartModal = lazy(() => import("./TradeChartModal"));

const preloadChart = () => void import("./TradeChartModal");

interface Props {
  date: string; // "YYYY-MM-DD"
  onClose: () => void;
}

const tableHeader = (
  <thead>
    <tr className="text-left text-gray-400 border-b border-gray-700">
      <th className="py-2 px-3">Symbol</th>
      <th className="py-2 px-3">Direction</th>
      <th className="py-2 px-3 text-right">P&L</th>
      <th className="py-2 px-3">Opened</th>
      <th className="py-2 px-3">Closed</th>
    </tr>
  </thead>
);

export default function DayTradesModal({ date, onClose }: Props) {
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  const closedFrom = `${date}T00:00:00Z`;
  const nextDay = new Date(date + "T00:00:00Z");
  nextDay.setUTCDate(nextDay.getUTCDate() + 1);
  const closedTo = nextDay.toISOString().split("T")[0] + "T00:00:00Z";

  const { data, isLoading, error } = useQuery({
    queryKey: ["dayGroups", date],
    queryFn: () =>
      fetchGroups(
        1,
        "closed",
        undefined,
        "closed_at",
        "asc",
        undefined,
        closedFrom,
        closedTo,
      ),
  });

  const groups = data?.groups ?? [];
  const totalPnl = groups.reduce(
    (sum, g) => sum + (g.realized_pnl ? Number(g.realized_pnl) : 0),
    0,
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 animate-fadeIn"
      onClick={onClose}
    >
      <div
        className="bg-[#1e1e2f] rounded-lg shadow-2xl max-w-[720px] w-[95vw] max-h-[90vh] overflow-hidden animate-scaleIn"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-gray-100">{date}</h2>
            {!isLoading && groups.length > 0 && (
              <>
                <span className="text-sm text-gray-400">
                  {groups.length} closed
                </span>
                <span
                  className={`text-sm font-medium ${
                    totalPnl >= 0 ? "text-green-400" : "text-red-400"
                  }`}
                >
                  P&L: {totalPnl >= 0 ? "+" : ""}
                  {totalPnl.toFixed(2)}
                </span>
              </>
            )}
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-full text-gray-400 hover:text-gray-200 hover:bg-gray-700 transition-colors text-xl leading-none"
          >
            &times;
          </button>
        </div>

        <div className="p-4 bg-[#1a1a2e] overflow-y-auto max-h-[calc(90vh-64px)]">
          {isLoading && (
            <div className="flex items-center justify-center h-32 text-gray-400">
              Loading...
            </div>
          )}
          {error && (
            <div className="text-red-400 text-center py-4">
              Failed to load trade groups
            </div>
          )}
          {data && groups.length === 0 && (
            <div className="text-gray-400 text-center py-4">
              No closed trades on this day
            </div>
          )}
          {groups.length > 0 && (
            <table className="w-full text-sm">
              {tableHeader}
              <tbody>
                {groups.map((g) => {
                  const pnl = g.realized_pnl ? Number(g.realized_pnl) : 0;
                  return (
                    <tr
                      key={g.id}
                      className="border-b border-gray-700/50 hover:bg-gray-800/30 cursor-pointer"
                      onClick={() => setSelectedGroupId(g.id)}
                      onMouseEnter={preloadChart}
                    >
                      <td className="py-2 px-3 text-gray-100 font-medium">
                        {g.symbol}
                      </td>
                      <td className="py-2 px-3">
                        <span
                          className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                            g.direction === "long"
                              ? "bg-green-900/50 text-green-400"
                              : "bg-red-900/50 text-red-400"
                          }`}
                        >
                          {g.direction.toUpperCase()}
                        </span>
                      </td>
                      <td
                        className={`py-2 px-3 text-right font-medium ${
                          pnl >= 0 ? "text-green-400" : "text-red-400"
                        }`}
                      >
                        {pnl >= 0 ? "+" : ""}
                        {pnl.toFixed(2)}
                      </td>
                      <td className="py-2 px-3 text-gray-400">
                        {formatDateTime(g.opened_at)}
                      </td>
                      <td className="py-2 px-3 text-gray-400">
                        {formatDateTime(g.closed_at)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {selectedGroupId && (
        <Suspense fallback={null}>
          <TradeChartModal
            groupId={selectedGroupId}
            onClose={() => setSelectedGroupId(null)}
          />
        </Suspense>
      )}
    </div>
  );
}
