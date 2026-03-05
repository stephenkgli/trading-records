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

/** Format P&L value with sign prefix and colour class. */
function pnlDisplay(pnl: number | string | null | undefined): {
  text: string;
  className: string;
} {
  if (pnl === null || pnl === undefined || pnl === "open") {
    return { text: "open", className: "text-gray-400" };
  }
  const num = typeof pnl === "string" ? parseFloat(pnl) : pnl;
  if (isNaN(num)) {
    return { text: String(pnl), className: "text-gray-400" };
  }
  if (num > 0) {
    return { text: `+${num}`, className: "text-green-400" };
  }
  if (num < 0) {
    return { text: String(num), className: "text-red-400" };
  }
  return { text: "0", className: "text-gray-400" };
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

  /** Handle Delete/Backspace key to remove selected overlay. */
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
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

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  /** Save overlays after style change (not captured by overlay event callbacks). */
  const handleStyleChange = useCallback(() => {
    if (!chart) return;
    save(groupId, collectOverlays(chart));
  }, [chart, groupId]);

  const pnl = data?.group ? pnlDisplay(data.group.realized_pnl) : null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 animate-fadeIn"
      onClick={onClose}
    >
      <div
        className="bg-[#1e1e2f] rounded-lg shadow-2xl max-w-[920px] w-[95vw] max-h-[90vh] overflow-hidden animate-scaleIn"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-gray-100">
              {data?.symbol ?? "Loading..."}
            </h2>
            {data?.group && (
              <>
                <span
                  className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    data.group.direction === "long"
                      ? "bg-green-900/50 text-green-400"
                      : "bg-red-900/50 text-red-400"
                  }`}
                >
                  {data.group.direction.toUpperCase()}
                </span>
                {pnl && (
                  <span className={`text-sm font-medium ${pnl.className}`}>
                    P&L: {pnl.text}
                  </span>
                )}
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

        <div className="p-4 bg-[#1a1a2e]">
          {isLoading && (
            <div className="flex flex-col gap-2">
              <div className="h-[320px] bg-gray-800 animate-pulse rounded" />
              <div className="h-[72px] bg-gray-800 animate-pulse rounded" />
            </div>
          )}
          {error && (
            <div className="flex flex-col items-center justify-center h-[400px] text-red-400 gap-2">
              <span>Failed to load chart data</span>
              <span className="text-sm text-gray-500">
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
                disabled={!chart}
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
