import { describe, expect, it } from "vitest";
import type { CandleData, MarkerData } from "../../api/types";
import { layoutTradeMarkers } from "./markerLayout";

describe("layoutTradeMarkers", () => {
  it("assigns independent lanes per (time, side) bucket", () => {
    const markers: MarkerData[] = [
      { time: 100, price: 10, side: "buy", text: "1", role: "entry", trade_id: "a" },
      { time: 100, price: 11, side: "buy", text: "1", role: "add", trade_id: "b" },
      { time: 100, price: 12, side: "sell", text: "1", role: "trim", trade_id: "c" },
      { time: 100, price: 13, side: "sell", text: "1", role: "exit", trade_id: "d" },
      { time: 200, price: 14, side: "buy", text: "1", role: "entry", trade_id: "e" },
    ];
    const candles: CandleData[] = [
      { time: 100, open: 9, high: 15, low: 8, close: 10, volume: 10 },
      { time: 200, open: 14, high: 16, low: 13, close: 15, volume: 10 },
    ];

    const result = layoutTradeMarkers(markers, candles);

    expect(result.map((m) => m.lane)).toEqual([0, 1, 0, 1, 0]);
    expect(result.map((m) => [m.barHigh, m.barLow])).toEqual([
      [15, 8],
      [15, 8],
      [15, 8],
      [15, 8],
      [16, 13],
    ]);
  });

  it("falls back to marker price when candle is missing", () => {
    const markers: MarkerData[] = [
      { time: 300, price: 21.5, side: "buy", text: "1", role: "entry", trade_id: "x" },
    ];

    const result = layoutTradeMarkers(markers, []);

    expect(result[0].barHigh).toBe(21.5);
    expect(result[0].barLow).toBe(21.5);
    expect(result[0].lane).toBe(0);
  });
});

