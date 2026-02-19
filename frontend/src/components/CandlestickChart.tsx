import {
  createChart,
  CandlestickSeries,
  CrosshairMode,
  createSeriesMarkers,
  type UTCTimestamp,
  type CandlestickData,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import { useRef, useEffect } from "react";
import type { CandleData, MarkerData } from "../api/types";

interface Props {
  candles: CandleData[];
  markers: MarkerData[];
  width?: number;
  height?: number;
}

function toChartCandles(candles: CandleData[]): CandlestickData<Time>[] {
  return candles.map((c) => ({
    time: c.time as UTCTimestamp,
    open: c.open,
    high: c.high,
    low: c.low,
    close: c.close,
  }));
}

function toChartMarkers(markers: MarkerData[]): SeriesMarker<Time>[] {
  return markers.map((m) => ({
    time: m.time as UTCTimestamp,
    position: m.position as "aboveBar" | "belowBar" | "inBar",
    shape: m.shape as "arrowUp" | "arrowDown" | "circle" | "square",
    color: m.color,
    text: m.text,
  }));
}

export default function CandlestickChart({
  candles,
  markers,
  width = 860,
  height = 400,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width,
      height,
      layout: { background: { color: "#ffffff" } },
      grid: {
        vertLines: { color: "#f0f0f0" },
        horzLines: { color: "#f0f0f0" },
      },
      timeScale: { timeVisible: true, secondsVisible: false },
      crosshair: { mode: CrosshairMode.Normal },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    const chartCandles = toChartCandles(candles);
    candleSeries.setData(chartCandles);

    const chartMarkers = toChartMarkers(markers);
    if (chartMarkers.length > 0) {
      createSeriesMarkers(candleSeries, chartMarkers);
    }

    chart.timeScale().fitContent();

    return () => chart.remove();
  }, [candles, markers, width, height]);

  return <div ref={containerRef} />;
}
