/**
 * drawingStorage — localStorage-based persistence for user-drawn
 * KLineChart overlays, keyed by trade group ID.
 */

import type { Chart, Point } from "klinecharts";

/** Minimal serialisable representation of a user-drawn overlay. */
export interface SerializedOverlay {
  name: string;
  points: Array<Partial<Point>>;
  styles?: Record<string, unknown>;
}

const STORAGE_PREFIX = "trading-records:drawings:";

/**
 * Save serialised overlays for a given trade group.
 * Silently warns on failure (quota exceeded, etc.) — never throws.
 */
export function save(groupId: string, overlays: SerializedOverlay[]): void {
  try {
    localStorage.setItem(
      `${STORAGE_PREFIX}${groupId}`,
      JSON.stringify(overlays),
    );
  } catch (err) {
    console.warn("[drawingStorage] save failed:", err);
  }
}

/**
 * Load previously saved overlays for a trade group.
 * Returns `null` when nothing is stored or data is corrupt.
 */
export function load(groupId: string): SerializedOverlay[] | null {
  try {
    const raw = localStorage.getItem(`${STORAGE_PREFIX}${groupId}`);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return null;
    return parsed as SerializedOverlay[];
  } catch {
    return null;
  }
}

/**
 * Remove all saved overlay data for a trade group.
 */
export function remove(groupId: string): void {
  localStorage.removeItem(`${STORAGE_PREFIX}${groupId}`);
}

/**
 * Collect all user-drawn overlays from the chart, ready for serialisation.
 *
 * Excludes trade markers (identified by `groupId === "trade-markers"`)
 * and overlays that are still being drawn (`currentStep < totalStep`).
 */
export function collectOverlays(chart: Chart): SerializedOverlay[] {
  const overlays = chart.getOverlays({ groupId: "user-drawings" });
  const result: SerializedOverlay[] = [];

  for (const ov of overlays) {
    // Skip incomplete overlays (still being drawn)
    if (ov.currentStep < ov.totalStep) continue;

    result.push({
      name: ov.name,
      points: ov.points.map((p) => ({
        ...(p.timestamp !== undefined && { timestamp: p.timestamp }),
        ...(p.value !== undefined && { value: p.value }),
        ...(p.dataIndex !== undefined && { dataIndex: p.dataIndex }),
      })),
      ...(ov.styles && { styles: ov.styles as unknown as Record<string, unknown> }),
    });
  }

  return result;
}
