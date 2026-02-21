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

/**
 * 获取当前浏览器时区偏移（秒），用于将 UTC 时间戳转为本地时间显示。
 * lightweight-charts 内部按 UTC 解读时间戳，因此加上偏移后图表 x 轴显示的就是本地时间。
 *
 * getTimezoneOffset() 返回 UTC 与本地时间的差值（分钟），正值表示本地时间落后于 UTC。
 * 例如 UTC+8 时区返回 -480，我们需要 +8 小时 = +28800 秒，所以取负值并乘以 60。
 */
function getLocalOffsetSeconds(): number {
  return -(new Date().getTimezoneOffset() * 60);
}

function toChartCandles(candles: CandleData[]): CandlestickData<Time>[] {
  const offset = getLocalOffsetSeconds();
  return candles.map((c) => ({
    time: (c.time + offset) as UTCTimestamp,
    open: c.open,
    high: c.high,
    low: c.low,
    close: c.close,
  }));
}

/**
 * 将 marker 时间应用本地时区偏移。
 * marker 的 time 已在后端 snap 到正确的 candle bar，前端只需加时区偏移。
 */
function toChartMarkers(
  markers: MarkerData[],
): SeriesMarker<Time>[] {
  const offset = getLocalOffsetSeconds();
  return markers.map((m) => ({
    time: (m.time + offset) as UTCTimestamp,
    position: m.position,
    shape: m.shape,
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
