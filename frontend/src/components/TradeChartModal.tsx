import { useState, useCallback, useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import type { Chart } from "klinecharts";
import { fetchGroupChart } from "../api/endpoints/groups";
import KLineChartView from "./chart/KLineChartView";
import DrawingToolbar from "./chart/DrawingToolbar";
import { collectOverlays, save } from "./chart/drawingStorage";

interface Props {
  groupId: string;
  onClose: () => void;
}

const chartLoadingSkeleton = (
  <div className="flex flex-col gap-2">
    <div className="h-[320px] bg-elevated animate-pulse rounded" />
    <div className="h-[72px] bg-elevated animate-pulse rounded" />
  </div>
);

/** Format P&L value with sign prefix and colour class. */
function pnlDisplay(pnl: number | string | null | undefined): {
  text: string;
  className: string;
} {
  if (pnl === null || pnl === undefined || pnl === "open") {
    return { text: "open", className: "text-[--color-text-muted]" };
  }
  const num = typeof pnl === "string" ? parseFloat(pnl) : pnl;
  if (isNaN(num)) {
    return { text: String(pnl), className: "text-[--color-text-muted]" };
  }
  if (num > 0) {
    return { text: `+${num}`, className: "text-profit" };
  }
  if (num < 0) {
    return { text: String(num), className: "text-loss" };
  }
  return { text: "0", className: "text-[--color-text-muted]" };
}

export default function TradeChartModal({ groupId, onClose }: Props) {
  const [chart, setChart] = useState<Chart | null>(null);
  const [selectedOverlayId, setSelectedOverlayId] = useState<string | null>(
    null,
  );

  const { data, isLoading, error } = useQuery({
    queryKey: ["groupChart", groupId],
    queryFn: () => fetchGroupChart(groupId),
  });

  const handleChartReady = useCallback((c: Chart) => {
    setChart(c);
  }, []);

  /** Track selected overlay via onSelected/onDeselected props on overlays. */
  const selectedOverlayIdRef = useRef(selectedOverlayId);
  selectedOverlayIdRef.current = selectedOverlayId;

  const chartRef = useRef(chart);
  chartRef.current = chart;

  /** Handle Delete/Backspace key to remove selected overlay, Escape to close. */
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.stopImmediatePropagation();
        onClose();
        return;
      }
      if (
        (e.key === "Delete" || e.key === "Backspace") &&
        selectedOverlayIdRef.current &&
        chartRef.current
      ) {
        chartRef.current.removeOverlay({
          id: selectedOverlayIdRef.current,
        });
        setSelectedOverlayId(null);
      }
    }

    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  }, [onClose]);

  /** Save overlays after style change (not captured by overlay event callbacks). */
  const handleStyleChange = useCallback(() => {
    if (!chart) return;
    save(groupId, collectOverlays(chart));
  }, [chart, groupId]);

  const pnl = data?.group ? pnlDisplay(data.group.realized_pnl) : null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Trade chart"
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 animate-fadeIn backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-surface rounded-lg shadow-2xl max-w-[920px] w-[95vw] max-h-[90vh] overflow-hidden animate-scaleIn border border-[--color-border]"
        style={{ overscrollBehavior: "contain" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-[--color-border]">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-[--color-text-primary]">
              {data?.symbol ?? "Loading\u2026"}
            </h2>
            {data?.group && (
              <>
                <span
                  className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    data.group.direction === "long"
                      ? "bg-profit-subtle text-profit"
                      : "bg-loss-subtle text-loss"
                  }`}
                >
                  {data.group.direction.toUpperCase()}
                </span>
                {pnl && (
                  <span className={`text-sm font-medium font-mono ${pnl.className}`}>
                    P&L: {pnl.text}
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

        <div className="p-4 bg-[--color-bg-primary]">
          {isLoading && chartLoadingSkeleton}
          {error && (
            <div className="flex flex-col items-center justify-center h-[400px] text-loss gap-2">
              <span>Failed to load chart data</span>
              <span className="text-sm text-[--color-text-muted]">
                Unable to fetch K-line data for this symbol. The data source may
                be temporarily unavailable, or historical data for this interval
                may not exist.
              </span>
            </div>
          )}
          {data && (
            <>
              <DrawingToolbar
                chart={chart}
                selectedOverlayId={selectedOverlayId}
                onDeleteSelected={() => setSelectedOverlayId(null)}
                onClearAll={() => setSelectedOverlayId(null)}
                onStyleChange={handleStyleChange}
              />
              <KLineChartView
                candles={data.candles}
                markers={data.markers}
                groupId={groupId}
                symbol={data.symbol}
                onChartReady={handleChartReady}
                onOverlaySelected={setSelectedOverlayId}
                onOverlayDeselected={() => setSelectedOverlayId(null)}
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
