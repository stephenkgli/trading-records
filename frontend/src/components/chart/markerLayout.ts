import type { CandleData, MarkerData } from "../../api/types";

export interface LaidOutMarker extends MarkerData {
  lane: number;
  barOpen: number;
  barClose: number;
  barHigh: number;
  barLow: number;
}

/**
 * Assign deterministic lanes for markers sharing the same bar and side.
 * Also attaches bar high/low for geometric anchoring.
 */
export function layoutTradeMarkers(
  markers: MarkerData[],
  candles: CandleData[],
): LaidOutMarker[] {
  const candleByTime = new Map<number, CandleData>();
  for (const c of candles) {
    candleByTime.set(c.time, c);
  }

  const laneCounter = new Map<string, number>();
  const laidOut: LaidOutMarker[] = [];

  for (const marker of markers) {
    const laneKey = `${marker.time}:${marker.side}`;
    const lane = laneCounter.get(laneKey) ?? 0;
    laneCounter.set(laneKey, lane + 1);

    const candle = candleByTime.get(marker.time);
    laidOut.push({
      ...marker,
      lane,
      barOpen: candle?.open ?? marker.price,
      barClose: candle?.close ?? marker.price,
      barHigh: candle?.high ?? marker.price,
      barLow: candle?.low ?? marker.price,
    });
  }

  return laidOut;
}
