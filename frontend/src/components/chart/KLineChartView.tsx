/**
 * KLineChartView — KLineChart-based candlestick chart component.
 *
 * Renders OHLC data with trade markers using the klinecharts library.
 * Exposes the chart instance via `onChartReady` callback for external
 * tool integration (e.g. DrawingToolbar).
 */

import { useRef, useEffect, useCallback } from "react";
import {
  init,
  dispose,
  type Chart,
  type KLineData,
  type Period,
} from "klinecharts";
import type { CandleData, MarkerData } from "../../api/types";
import { createTradeMarkers } from "./tradeMarkers";
import { collectOverlays, save, load } from "./drawingStorage";

interface KLineChartViewProps {
  candles: CandleData[];
  markers: MarkerData[];
  groupId: string;
  /** Symbol ticker for KLineChart (e.g. "MES"). */
  symbol?: string;
  /** Chart period/interval. Defaults to { type: "minute", span: 5 }. */
  period?: Period;
  width?: number;
  height?: number;
  /** Called once after the chart instance is created. */
  onChartReady?: (chart: Chart) => void;
  /** Called when a user-drawn overlay is selected. */
  onOverlaySelected?: (overlayId: string) => void;
  /** Called when a user-drawn overlay is deselected. */
  onOverlayDeselected?: () => void;
}

/**
 * Convert UTC-second timestamps to millisecond timestamps for KLineChart.
 *
 * KLineChart interprets `timestamp` via `Intl.DateTimeFormat` using
 * the configured timezone, so we just convert seconds to milliseconds.
 */
function convertCandles(candles: CandleData[]): KLineData[] {
  return candles.map((c) => ({
    timestamp: c.time * 1000,
    open: c.open,
    high: c.high,
    low: c.low,
    close: c.close,
  }));
}

const OVERLAY_PATCH_POLL_MS = 1000;

export { convertCandles };
export type { KLineChartViewProps };

export default function KLineChartView({
  candles,
  markers,
  groupId,
  symbol = "UNKNOWN",
  period = { type: "minute", span: 5 },
  width = 860,
  height = 400,
  onChartReady,
  onOverlaySelected,
  onOverlayDeselected,
}: KLineChartViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<Chart | null>(null);

  // Keep latest callbacks/values in refs to avoid effect re-runs
  const onChartReadyRef = useRef(onChartReady);
  onChartReadyRef.current = onChartReady;

  const onOverlaySelectedRef = useRef(onOverlaySelected);
  onOverlaySelectedRef.current = onOverlaySelected;

  const onOverlayDeselectedRef = useRef(onOverlayDeselected);
  onOverlayDeselectedRef.current = onOverlayDeselected;

  const candlesRef = useRef(candles);
  candlesRef.current = candles;

  const markersRef = useRef(markers);
  markersRef.current = markers;

  const groupIdRef = useRef(groupId);
  groupIdRef.current = groupId;

  const symbolRef = useRef(symbol);
  symbolRef.current = symbol;

  const periodRef = useRef(period);
  periodRef.current = period;

  /** Debounced auto-save: collect overlays and persist to localStorage. */
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const debouncedSave = useCallback(() => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      const chart = chartRef.current;
      if (!chart) return;
      const data = collectOverlays(chart);
      save(groupIdRef.current, data);
    }, 500);
  }, []);

  /** Set of overlay IDs already patched with event callbacks. */
  const patchedIdsRef = useRef<Set<string>>(new Set());

  /**
   * Patch a single overlay with selection + persistence event callbacks.
   * Idempotent: skips overlays already patched.
   */
  const patchOverlay = useCallback(
    (chart: Chart, overlayId: string) => {
      if (patchedIdsRef.current.has(overlayId)) return;
      patchedIdsRef.current.add(overlayId);

      chart.overrideOverlay({
        id: overlayId,
        onSelected: (event) => {
          onOverlaySelectedRef.current?.(event.overlay.id);
        },
        onDeselected: () => {
          onOverlayDeselectedRef.current?.();
        },
        onDrawEnd: () => {
          debouncedSave();
        },
        onPressedMoveEnd: () => {
          debouncedSave();
        },
        onRemoved: () => {
          // Clean up patched tracking
          patchedIdsRef.current.delete(overlayId);
          debouncedSave();
        },
      });
    },
    [debouncedSave],
  );

  /**
   * Initialise chart once; load data via DataLoader callback.
   */
  const initChart = useCallback(() => {
    if (!containerRef.current) return;

    const chart = init(containerRef.current, {
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      styles: {
        grid: {
          horizontal: { show: true, color: "rgba(255, 255, 255, 0.06)" },
          vertical: { show: true, color: "rgba(255, 255, 255, 0.06)" },
        },
        candle: {
          bar: {
            upColor: "#00c087",
            downColor: "#ff4757",
            noChangeColor: "#888888",
            upBorderColor: "#00c087",
            downBorderColor: "#ff4757",
            noChangeBorderColor: "#888888",
            upWickColor: "#00c087",
            downWickColor: "#ff4757",
            noChangeWickColor: "#888888",
          },
          tooltip: {
            legend: {
              color: "#e0e0e8",
              marginLeft: 8,
              marginTop: 6,
              marginRight: 8,
              marginBottom: 0,
              size: 12,
            },
          },
        },
        crosshair: {
          horizontal: {
            show: true,
            line: {
              show: true,
              color: "rgba(150, 150, 180, 0.4)",
              dashedValue: [4, 3],
            },
            text: {
              show: true,
              color: "#e0e0e8",
              backgroundColor: "rgba(30, 30, 47, 0.95)",
              borderColor: "rgba(150, 150, 180, 0.3)",
              paddingLeft: 4,
              paddingRight: 4,
              paddingTop: 2,
              paddingBottom: 2,
            },
          },
          vertical: {
            show: true,
            line: {
              show: true,
              color: "rgba(150, 150, 180, 0.4)",
              dashedValue: [4, 3],
            },
            text: {
              show: true,
              color: "#e0e0e8",
              backgroundColor: "rgba(30, 30, 47, 0.95)",
              borderColor: "rgba(150, 150, 180, 0.3)",
              paddingLeft: 4,
              paddingRight: 4,
              paddingTop: 2,
              paddingBottom: 2,
            },
          },
        },
        xAxis: {
          axisLine: { color: "rgba(255, 255, 255, 0.1)" },
          tickLine: { color: "rgba(255, 255, 255, 0.1)" },
          tickText: { color: "#a0a0b0" },
        },
        yAxis: {
          axisLine: { color: "rgba(255, 255, 255, 0.1)" },
          tickLine: { color: "rgba(255, 255, 255, 0.1)" },
          tickText: { color: "#a0a0b0" },
        },
      },
    });

    if (!chart) return;

    chartRef.current = chart;

    // Load candle data via DataLoader.
    // KLineChart v10 requires symbol + period + dataLoader to be set
    // before getBars fires. setPeriod (called last) triggers the initial load.
    chart.setDataLoader({
      getBars: ({ callback }) => {
        const converted = convertCandles(candlesRef.current);
        callback(converted, false);
      },
    });
    chart.setSymbol({ ticker: symbolRef.current });
    chart.setPeriod(periodRef.current);

    // Render trade markers
    if (markersRef.current.length > 0) {
      createTradeMarkers(chart, markersRef.current, candlesRef.current);
    }

    // Restore saved overlays
    const saved = load(groupIdRef.current);
    if (saved && saved.length > 0) {
      for (const item of saved) {
        const id = chart.createOverlay({
          name: item.name,
          groupId: "user-drawings",
          points: item.points,
          ...(item.styles && { styles: item.styles }),
        });
        if (typeof id === "string" && id) {
          patchOverlay(chart, id);
        }
      }
    }

    onChartReadyRef.current?.(chart);
  }, [patchOverlay]);

  useEffect(() => {
    initChart();

    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      if (containerRef.current) {
        dispose(containerRef.current);
      }
      chartRef.current = null;
      patchedIdsRef.current.clear();
    };
  }, [initChart]);

  /**
   * When candles or markers change (e.g. different groupId), reload data.
   * Skip initial render (handled by initChart).
   */
  const isInitialMount = useRef(true);
  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }

    const chart = chartRef.current;
    if (!chart) return;

    chart.resetData();

    chart.removeOverlay({ groupId: "trade-markers" });
    if (markers.length > 0) {
      createTradeMarkers(chart, markers, candles);
    }
  }, [candles, markers]);

  /**
   * Poll for new user-drawn overlays and patch them with event callbacks.
   * This is needed because overlays are created by DrawingToolbar (external
   * to this component) and KLineChart v10 doesn't provide a global
   * "overlay created" event.
   */
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const patchUserDrawingOverlays = () => {
      const overlays = chart.getOverlays({ groupId: "user-drawings" });
      for (const ov of overlays) {
        patchOverlay(chart, ov.id);
      }
    };

    // Run once immediately to reduce first-patch latency.
    patchUserDrawingOverlays();

    const interval = setInterval(patchUserDrawingOverlays, OVERLAY_PATCH_POLL_MS);

    return () => clearInterval(interval);
  }, [patchOverlay]);

  return (
    <div
      ref={containerRef}
      style={{
        width: `${width}px`,
        height: `${height}px`,
        backgroundColor: "#1a1a2e",
      }}
    />
  );
}
