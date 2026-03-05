/**
 * tradeMarkers — custom overlay for rendering trade entry/exit markers
 * on a KLineChart at exact (timestamp, price) coordinates.
 *
 * Registers a `tradeMarker` overlay type that draws a small filled
 * triangle and a compact text label offset from the trade's execution
 * price. Entry/add markers sit below the candle; trim/exit markers sit
 * above. Triangle direction follows the buy/sell action: ▲ for buy,
 * ▼ for sell (independent of position).
 */

import { registerOverlay, type Chart } from "klinecharts";
import type { MarkerData, MarkerPosition, MarkerShape } from "../../api/types";

/** Triangle half-width and height in pixels. */
const TRI_HALF = 6;
const TRI_HEIGHT = 10;

/**
 * Vertical offset (px) from the price coordinate to push the marker
 * away from the candle body, reducing overlap.
 */
const PRICE_OFFSET = 12;

/** Vertical gap between triangle base and text label. */
const LABEL_GAP = 4;

/** Colour map for trade roles (optimised for dark background). */
const ROLE_COLORS: Record<string, string> = {
  entry: "#3b82f6", // blue — open position
  add: "#06b6d4", // cyan — add to position
  trim: "#f59e0b", // amber — reduce position
  exit: "#e879f9", // fuchsia — close position (avoids red/down confusion)
};

/**
 * Register the `tradeMarker` overlay type with KLineChart.
 * Must be called once before creating any trade marker overlays.
 *
 * The overlay expects `extendData` to be a `MarkerExtendData` object:
 * ```
 * { text: string; position: "aboveBar" | "belowBar"; color: string; shape: "arrowUp" | "arrowDown" }
 * ```
 */
interface MarkerExtendData {
  text: string;
  position: MarkerPosition;
  color: string;
  shape: MarkerShape;
}

let registered = false;

export function registerTradeMarkerOverlay(): void {
  if (registered) return;
  registered = true;

  registerOverlay<MarkerExtendData>({
    name: "tradeMarker",
    totalStep: 2,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: ({ overlay, coordinates }) => {
      if (coordinates.length === 0) return [];

      const x = coordinates[0].x;
      const y = coordinates[0].y;
      const ext = overlay.extendData as MarkerExtendData | undefined;
      if (!ext) return [];

      const below = ext.position === "belowBar";
      const upward = ext.shape === "arrowUp";
      const color = ext.color;

      // Canvas coordinate system: y increases downward.
      //
      // `position` controls vertical placement relative to candle:
      //   belowBar → marker sits below the candle body
      //   aboveBar → marker sits above the candle body
      //
      // `shape` controls triangle direction (buy/sell action):
      //   arrowUp (▲)  → buy
      //   arrowDown (▼) → sell

      // sign: +1 pushes away from price downward (belowBar),
      //        -1 pushes away upward (aboveBar)
      const sign = below ? 1 : -1;
      const anchorY = y + sign * PRICE_OFFSET;

      // Triangle tip/base geometry.
      // ▲ (arrowUp): tip at smallest Y (screen-top), base at largest Y.
      // ▼ (arrowDown): tip at largest Y (screen-bottom), base at smallest Y.
      const farY = anchorY + sign * TRI_HEIGHT;
      const tipY = upward ? Math.min(anchorY, farY) : Math.max(anchorY, farY);
      const baseY = upward ? Math.max(anchorY, farY) : Math.min(anchorY, farY);
      const triCoords = [
        { x, y: tipY },
        { x: x - TRI_HALF, y: baseY },
        { x: x + TRI_HALF, y: baseY },
      ];

      const textY = anchorY + sign * (TRI_HEIGHT + LABEL_GAP);
      const textBaseline = below ? "top" : "bottom";

      return [
        {
          type: "polygon",
          attrs: { coordinates: triCoords },
          styles: {
            style: "fill" as const,
            color,
            borderColor: "rgba(0, 0, 0, 0.3)",
            borderSize: 1,
          },
          ignoreEvent: true,
        },
        {
          type: "text",
          attrs: {
            x,
            y: textY,
            text: ext.text,
            align: "center",
            baseline: textBaseline,
          },
          styles: {
            color: "#ffffff",
            backgroundColor: color,
            borderRadius: 3,
            paddingLeft: 4,
            paddingRight: 4,
            paddingTop: 2,
            paddingBottom: 2,
            size: 11,
            family: "inherit",
            weight: "normal",
          },
          ignoreEvent: true,
        },
      ];
    },
  });
}

/**
 * Render trade entry/exit markers as locked KLineChart overlays.
 *
 * All markers share `groupId: "trade-markers"` so they can be
 * bulk-removed without touching user-drawn overlays.
 */
export function createTradeMarkers(
  chart: Chart,
  markers: MarkerData[],
): void {
  registerTradeMarkerOverlay();

  for (const m of markers) {
    const timestampMs = m.time * 1000;
    const color = ROLE_COLORS[m.role] ?? "#6b7280";

    chart.createOverlay({
      name: "tradeMarker",
      groupId: "trade-markers",
      lock: true,
      visible: true,
      points: [{ timestamp: timestampMs, value: m.price }],
      extendData: {
        text: m.text,
        position: m.position,
        color,
        shape: m.shape,
      } satisfies MarkerExtendData,
    });
  }
}
