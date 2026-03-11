import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useState, useEffect, useRef, useCallback } from "react";
import { createPortal } from "react-dom";
import { fetchGroupsByActivityDate } from "../api/endpoints/groups";

const TradeChartModal = lazy(() => import("./TradeChartModal"));

const preloadChart = () => void import("./TradeChartModal");

interface Props {
  date: string; // "YYYY-MM-DD"
  onClose: () => void;
}

function pnlColorClass(isClosed: boolean, pnl: number): string {
  if (!isClosed) return "text-[--color-text-muted]";
  return pnl >= 0 ? "text-profit" : "text-loss";
}

const ROLE_STYLES: Record<string, string> = {
  entry: "bg-profit-subtle text-profit",
  add: "bg-accent-subtle text-accent-hover",
  trim: "bg-[rgba(245,158,11,0.15)] text-[#f59e0b]",
  exit: "bg-loss-subtle text-loss",
};

const tableHeader = (
  <thead>
    <tr className="text-left text-[--color-text-muted] border-b border-[--color-border]">
      <th className="py-2 px-3 text-[10px] font-medium uppercase tracking-widest">Symbol</th>
      <th className="py-2 px-3 text-[10px] font-medium uppercase tracking-widest">Direction</th>
      <th className="py-2 px-3 text-[10px] font-medium uppercase tracking-widest">Status</th>
      <th className="py-2 px-3 text-right text-[10px] font-medium uppercase tracking-widest">P&L</th>
      <th className="py-2 px-3 text-[10px] font-medium uppercase tracking-widest">Activity</th>
    </tr>
  </thead>
);

export default function DayTradesModal({ date, onClose }: Props) {
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["dayActivity", date],
    queryFn: () => fetchGroupsByActivityDate(date),
  });

  // Focus trap: focus the dialog on mount + lock body scroll
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    const prevOverflow = document.body.style.overflow;
    dialogRef.current?.focus();
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prevOverflow;
      prev?.focus();
    };
  }, []);

  // Escape key handler — only when chart modal is NOT open
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && !selectedGroupId) {
        onClose();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose, selectedGroupId]);

  const groups = data?.groups ?? [];
  const exitedGroups = groups.filter(
    (g) => g.status === "closed" && g.day_roles.includes("exit"),
  );
  const totalPnl = exitedGroups.reduce(
    (sum, g) => sum + (g.realized_pnl ? Number(g.realized_pnl) : 0),
    0,
  );

  const handleBackdropClick = useCallback(() => {
    if (!selectedGroupId) {
      onClose();
    }
  }, [onClose, selectedGroupId]);

  return (
    <div
      ref={dialogRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 animate-fadeIn backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label={`Trades on ${date}`}
      tabIndex={-1}
      onClick={handleBackdropClick}
    >
      <div
        className="bg-surface rounded-lg shadow-2xl max-w-[720px] w-[95vw] max-h-[90vh] overflow-hidden animate-scaleIn border border-[--color-border]"
        style={{ overscrollBehavior: "contain" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-[--color-border]">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-[--color-text-primary] font-mono">{date}</h2>
            {!isLoading && groups.length > 0 && (
              <>
                <span className="text-sm text-[--color-text-secondary]">
                  {groups.length} group{groups.length !== 1 ? "s" : ""}
                </span>
                {exitedGroups.length > 0 && (
                  <span
                    className={`text-sm font-medium font-mono ${
                      totalPnl >= 0 ? "text-profit" : "text-loss"
                    }`}
                    style={{ fontVariantNumeric: "tabular-nums" }}
                  >
                    P&L: {totalPnl >= 0 ? "+" : ""}
                    ${Math.abs(totalPnl).toFixed(2)}
                  </span>
                )}
              </>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="w-8 h-8 flex items-center justify-center rounded-full text-[--color-text-muted] hover:text-[--color-text-primary] hover:bg-[--color-bg-hover] transition-all duration-150 text-xl leading-none"
          >
            &times;
          </button>
        </div>

        <div className="p-4 bg-[--color-bg-primary] overflow-y-auto max-h-[calc(90vh-64px)]">
          {isLoading && (
            <div className="flex items-center justify-center h-32 text-[--color-text-muted]" aria-live="polite">
              Loading&hellip;
            </div>
          )}
          {error && (
            <div className="text-loss text-center py-4">
              Failed to load trade groups
            </div>
          )}
          {data && groups.length === 0 && (
            <div className="text-[--color-text-muted] text-center py-4">
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
                      className="border-b border-[--color-border] hover:bg-[--color-bg-hover] cursor-pointer transition-colors"
                      onClick={() => setSelectedGroupId(g.id)}
                      onMouseEnter={preloadChart}
                      tabIndex={0}
                      role="button"
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setSelectedGroupId(g.id);
                        }
                      }}
                    >
                      <td className="py-2 px-3 text-[--color-text-primary] font-medium">
                        {g.symbol}
                      </td>
                      <td className="py-2 px-3">
                        <span
                          className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                            g.direction === "long"
                              ? "bg-profit-subtle text-profit"
                              : "bg-loss-subtle text-loss"
                          }`}
                        >
                          {g.direction}
                        </span>
                      </td>
                      <td className="py-2 px-3">
                        <span
                          className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                            isClosed
                              ? "bg-elevated text-[--color-text-secondary]"
                              : "bg-accent-subtle text-accent-hover"
                          }`}
                        >
                          {g.status}
                        </span>
                      </td>
                      <td
                        className={`py-2 px-3 text-right font-medium font-mono ${pnlColorClass(isClosed, pnl)}`}
                        style={{ fontVariantNumeric: "tabular-nums" }}
                      >
                        {isClosed
                          ? `${pnl >= 0 ? "+" : "-"}$${Math.abs(pnl).toFixed(2)}`
                          : "\u2014"}
                      </td>
                      <td className="py-2 px-3">
                        <div className="flex gap-1 flex-wrap">
                          {g.day_roles.map((role) => (
                            <span
                              key={role}
                              className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                                ROLE_STYLES[role] ?? "bg-elevated text-[--color-text-secondary]"
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

      {selectedGroupId && createPortal(
        <Suspense fallback={null}>
          <TradeChartModal
            groupId={selectedGroupId}
            onClose={() => setSelectedGroupId(null)}
          />
        </Suspense>,
        document.body,
      )}
    </div>
  );
}
