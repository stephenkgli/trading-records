/**
 * tradeMarkers — custom overlay for rendering trade markers
 * on a KLineChart at exact (timestamp, price) coordinates.
 */

import { registerOverlay, type Chart } from "klinecharts";
import type { CandleData, MarkerData, MarkerSide, TradeRole } from "../../api/types";
import { layoutTradeMarkers } from "./markerLayout";

/** Triangle half-width and height in pixels. */
const TRI_HALF = 6;
const TRI_HEIGHT = 10;

/** Geometry constants for marker layout. */
const BASE_OFFSET = 8;
const LANE_GAP = 14;
const LABEL_GAP = 4;
const LABEL_BOX_HEIGHT = 16;
const EDGE_MARGIN = 6;
const TOTAL_STACK_HEIGHT = TRI_HEIGHT + LABEL_GAP + LABEL_BOX_HEIGHT;

/** Colour map for trade roles (optimised for dark background). */
const ROLE_COLORS: Record<TradeRole, string> = {
  entry: "#3b82f6", // blue — open position
  add: "#06b6d4", // cyan — add to position
  trim: "#f59e0b", // amber — reduce position
  exit: "#e879f9", // fuchsia — close position
};

type Placement = "above" | "below";

interface MarkerExtendData {
  text: string;
  color: string;
  side: MarkerSide;
  lane: number;
  barOpen: number;
  barClose: number;
}

interface MarkerGeometryInput {
  side: MarkerSide;
  lane: number;
  priceY: number;
  bodyTopY: number;
  bodyBottomY: number;
  paneTop: number;
  paneBottom: number;
}

interface PaneBounds {
  top: number;
  bottom: number;
}

interface MarkerGeometry {
  placement: Placement;
  sign: 1 | -1;
  anchorY: number;
  textBaseline: "top" | "bottom";
}

function oppositePlacement(placement: Placement): Placement {
  return placement === "below" ? "above" : "below";
}

function placementForSide(side: MarkerSide): Placement {
  return side === "buy" ? "below" : "above";
}

function buildGeometry(
  placement: Placement,
  lane: number,
  priceY: number,
  bodyTopY: number,
  bodyBottomY: number,
): MarkerGeometry {
  const sign: 1 | -1 = placement === "below" ? 1 : -1;
  const offset = BASE_OFFSET + lane * LANE_GAP;
  let anchorY: number;
  if (placement === "below") {
    // Prefer staying close to execution price, but never overlap candle body.
    anchorY = Math.max(priceY + offset, bodyBottomY + offset);
  } else {
    // Prefer staying close to execution price, but never overlap candle body.
    anchorY = Math.min(priceY - offset, bodyTopY - offset);
  }
  return {
    placement,
    sign,
    anchorY,
    textBaseline: placement === "below" ? "top" : "bottom",
  };
}

function getBounds(placement: Placement, anchorY: number): { top: number; bottom: number } {
  if (placement === "below") {
    return {
      top: anchorY,
      bottom: anchorY + TOTAL_STACK_HEIGHT,
    };
  }
  return {
    top: anchorY - TOTAL_STACK_HEIGHT,
    bottom: anchorY,
  };
}

function fitsInPane(
  geometry: MarkerGeometry,
  paneTop: number,
  paneBottom: number,
): boolean {
  const bounds = getBounds(geometry.placement, geometry.anchorY);
  return bounds.top >= paneTop + EDGE_MARGIN && bounds.bottom <= paneBottom - EDGE_MARGIN;
}

function clampAnchor(placement: Placement, anchorY: number, paneTop: number, paneBottom: number): number {
  let min: number;
  let max: number;
  if (placement === "below") {
    min = paneTop + EDGE_MARGIN;
    max = paneBottom - EDGE_MARGIN - TOTAL_STACK_HEIGHT;
  } else {
    min = paneTop + EDGE_MARGIN + TOTAL_STACK_HEIGHT;
    max = paneBottom - EDGE_MARGIN;
  }

  if (min > max) {
    return (min + max) / 2;
  }
  return Math.min(Math.max(anchorY, min), max);
}

function toFinite(value: number, fallback: number): number {
  return Number.isFinite(value) ? value : fallback;
}

/**
 * KLineChart overlay callbacks may provide `coordinates.y` in pane-local
 * coordinates while `bounding.top/bottom` can be absolute canvas offsets.
 * Infer the correct pane bounds in the same coordinate system as y values.
 */
export function resolvePaneBounds(samples: number[], bounding: { top: number; bottom: number; height: number }): PaneBounds {
  const EPS = 1;
  const localCount = samples.filter((y) => y >= -EPS && y <= bounding.height + EPS).length;
  const absoluteCount = samples.filter(
    (y) => y >= bounding.top - EPS && y <= bounding.bottom + EPS,
  ).length;
  const maxY = Math.max(...samples);
  const minY = Math.min(...samples);

  if (localCount === samples.length && minY >= -EPS && maxY <= bounding.height + EPS) {
    return { top: 0, bottom: bounding.height };
  }
  if (absoluteCount === samples.length) {
    return { top: bounding.top, bottom: bounding.bottom };
  }
  if (localCount >= absoluteCount) {
    return { top: 0, bottom: bounding.height };
  }
  return { top: bounding.top, bottom: bounding.bottom };
}

export function resolveMarkerGeometry(input: MarkerGeometryInput): MarkerGeometry {
  const preferred = buildGeometry(
    placementForSide(input.side),
    input.lane,
    input.priceY,
    input.bodyTopY,
    input.bodyBottomY,
  );
  if (fitsInPane(preferred, input.paneTop, input.paneBottom)) {
    return preferred;
  }

  const flipped = buildGeometry(
    oppositePlacement(preferred.placement),
    input.lane,
    input.priceY,
    input.bodyTopY,
    input.bodyBottomY,
  );
  if (fitsInPane(flipped, input.paneTop, input.paneBottom)) {
    return flipped;
  }

  return {
    ...flipped,
    anchorY: clampAnchor(
      flipped.placement,
      flipped.anchorY,
      input.paneTop,
      input.paneBottom,
    ),
  };
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
    createPointFigures: ({ overlay, coordinates, yAxis, bounding }) => {
      if (coordinates.length === 0) return [];

      const x = coordinates[0].x;
      const priceY = coordinates[0].y;
      const ext = overlay.extendData as MarkerExtendData | undefined;
      if (!ext) return [];

      const pointValue = overlay.points[0]?.value;
      const axisPriceYRaw = toFinite(
        yAxis && typeof pointValue === "number"
          ? yAxis.convertToPixel(pointValue)
          : priceY,
        priceY,
      );
      // Normalize axis-converted pixels to the same coordinate space as coordinates.y.
      const axisDelta = priceY - axisPriceYRaw;
      const openY = toFinite(
        yAxis ? yAxis.convertToPixel(ext.barOpen) + axisDelta : priceY,
        priceY,
      );
      const closeY = toFinite(
        yAxis ? yAxis.convertToPixel(ext.barClose) + axisDelta : priceY,
        priceY,
      );
      const bodyTopY = Math.min(openY, closeY);
      const bodyBottomY = Math.max(openY, closeY);
      const paneBounds = resolvePaneBounds([priceY, bodyTopY, bodyBottomY], bounding);

      const geometry = resolveMarkerGeometry({
        side: ext.side,
        lane: ext.lane,
        priceY,
        bodyTopY,
        bodyBottomY,
        paneTop: paneBounds.top,
        paneBottom: paneBounds.bottom,
      });

      const upward = ext.side === "buy";
      const color = ext.color;
      const farY = geometry.anchorY + geometry.sign * TRI_HEIGHT;
      const tipY = upward ? Math.min(geometry.anchorY, farY) : Math.max(geometry.anchorY, farY);
      const baseY = upward ? Math.max(geometry.anchorY, farY) : Math.min(geometry.anchorY, farY);
      const triCoords = [
        { x, y: tipY },
        { x: x - TRI_HALF, y: baseY },
        { x: x + TRI_HALF, y: baseY },
      ];

      const textY = geometry.anchorY + geometry.sign * (TRI_HEIGHT + LABEL_GAP);

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
            baseline: geometry.textBaseline,
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
 * Render trade markers as locked KLineChart overlays.
 *
 * All markers share `groupId: "trade-markers"` so they can be
 * bulk-removed without touching user-drawn overlays.
 */
export function createTradeMarkers(
  chart: Chart,
  markers: MarkerData[],
  candles: CandleData[],
): void {
  registerTradeMarkerOverlay();
  const laidOut = layoutTradeMarkers(markers, candles);

  for (const m of laidOut) {
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
        color,
        side: m.side,
        lane: m.lane,
        barOpen: m.barOpen,
        barClose: m.barClose,
      } satisfies MarkerExtendData,
    });
  }
}
