import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useState } from "react";
import { fetchGroupsByActivityDate } from "../api/endpoints/groups";

const TradeChartModal = lazy(() => import("./TradeChartModal"));

const preloadChart = () => void import("./TradeChartModal");

interface Props {
  date: string; // "YYYY-MM-DD"
  onClose: () => void;
}

const ROLE_STYLES: Record<string, string> = {
  entry: "bg-green-900/50 text-green-400",
  add: "bg-blue-900/50 text-blue-400",
  trim: "bg-orange-900/50 text-orange-400",
  exit: "bg-red-900/50 text-red-400",
};

const tableHeader = (
  <thead>
    <tr className="text-left text-gray-400 border-b border-gray-700">
      <th className="py-2 px-3">Symbol</th>
      <th className="py-2 px-3">Direction</th>
      <th className="py-2 px-3">Status</th>
      <th className="py-2 px-3 text-right">P&L</th>
      <th className="py-2 px-3">Activity</th>
    </tr>
  </thead>
);

export default function DayTradesModal({ date, onClose }: Props) {
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["dayActivity", date],
    queryFn: () => fetchGroupsByActivityDate(date),
  });

  const groups = data?.groups ?? [];
  const closedGroups = groups.filter((g) => g.status === "closed");
  const totalPnl = closedGroups.reduce(
    (sum, g) => sum + (g.realized_pnl ? Number(g.realized_pnl) : 0),
    0,
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 animate-fadeIn"
      role="dialog"
      aria-modal="true"
      aria-label="Day trades"
      onClick={onClose}
      onKeyDown={(e) => { if (e.key === "Escape") onClose(); }}
    >
      <div
        className="bg-[#1e1e2f] rounded-lg shadow-2xl max-w-[720px] w-[95vw] max-h-[90vh] overflow-hidden animate-scaleIn"
        style={{ overscrollBehavior: "contain" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-gray-100">{date}</h2>
            {!isLoading && groups.length > 0 && (
              <>
                <span className="text-sm text-gray-400">
                  {groups.length} group{groups.length !== 1 ? "s" : ""}
                </span>
                {closedGroups.length > 0 && (
                  <span
                    className={`text-sm font-medium ${
                      totalPnl >= 0 ? "text-green-400" : "text-red-400"
                    }`}
                    style={{ fontVariantNumeric: "tabular-nums" }}
                  >
                    P&L: {totalPnl >= 0 ? "+" : ""}
                    {totalPnl.toFixed(2)}
                  </span>
                )}
              </>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="w-8 h-8 flex items-center justify-center rounded-full text-gray-400 hover:text-gray-200 hover:bg-gray-700 transition-[color,background-color] text-xl leading-none"
          >
            &times;
          </button>
        </div>

        <div className="p-4 bg-[#1a1a2e] overflow-y-auto max-h-[calc(90vh-64px)]">
          {isLoading && (
            <div className="flex items-center justify-center h-32 text-gray-400" aria-live="polite">
              Loading\u2026
            </div>
          )}
          {error && (
            <div className="text-red-400 text-center py-4">
              Failed to load trade groups
            </div>
          )}
          {data && groups.length === 0 && (
            <div className="text-gray-400 text-center py-4">
              No trade activity on this day
            </div>
          )}
          {groups.length > 0 && (
            <table className="w-full text-sm">
              {tableHeader}
              <tbody>
                {groups.map((g) => {
                  const isClosed = g.status === "closed";
                  const pnl = isClosed && g.realized_pnl ? Number(g.realized_pnl) : 0;
                  return (
                    <tr
                      key={g.id}
                      className="border-b border-gray-700/50 hover:bg-gray-800/30 cursor-pointer"
                      onClick={() => setSelectedGroupId(g.id)}
                      onMouseEnter={preloadChart}
                      tabIndex={0}
                      role="button"
                      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelectedGroupId(g.id); } }}
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
                      <td className="py-2 px-3">
                        <span
                          className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                            isClosed
                              ? "bg-gray-700 text-gray-300"
                              : "bg-blue-900/50 text-blue-400"
                          }`}
                        >
                          {g.status.toUpperCase()}
                        </span>
                      </td>
                      <td
                        className={`py-2 px-3 text-right font-medium ${
                          !isClosed
                            ? "text-gray-500"
                            : pnl >= 0
                              ? "text-green-400"
                              : "text-red-400"
                        }`}
                        style={{ fontVariantNumeric: "tabular-nums" }}
                      >
                        {isClosed
                          ? `${pnl >= 0 ? "+" : ""}${pnl.toFixed(2)}`
                          : "\u2014"}
                      </td>
                      <td className="py-2 px-3">
                        <div className="flex gap-1 flex-wrap">
                          {g.day_roles.map((role) => (
                            <span
                              key={role}
                              className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                                ROLE_STYLES[role] ?? "bg-gray-700 text-gray-300"
                              }`}
                            >
                              {role}
                            </span>
                          ))}
                        </div>
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
