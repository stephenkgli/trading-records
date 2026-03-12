/**
 * DrawingToolbar — toolbar for KLineChart drawing overlay tools.
 *
 * Provides buttons for 9 drawing tools mapped to KLineChart built-in
 * overlay types, plus style editing (colour/line width), "delete selected",
 * and "clear all" actions.
 *
 * Tools are visually grouped by category with separators.
 */

import { useState } from "react";
import type { Chart } from "klinecharts";

/** Tool definition mapping display label to KLineChart overlay name. */
interface DrawingTool {
  readonly label: string;
  readonly overlayName: string;
}

/**
 * Tool groups for visual separation.
 * Each group renders its tools then a divider (except the last group).
 */
const TOOL_GROUPS: readonly { readonly tools: readonly DrawingTool[] }[] = [
  {
    // Lines
    tools: [
      { label: "Trend", overlayName: "segment" },
      { label: "Ray", overlayName: "rayLine" },
    ],
  },
  {
    // Guides
    tools: [
      { label: "H.Line", overlayName: "horizontalStraightLine" },
    ],
  },
  {
    // Channels
    tools: [
      { label: "Parallel", overlayName: "parallelStraightLine" },
    ],
  },
  {
    // Analysis
    tools: [
      { label: "Fibonacci", overlayName: "fibonacciLine" },
    ],
  },
] as const;

/** Flat list of all tools (for exports / backward compat). */
const DRAWING_TOOLS: readonly DrawingTool[] = TOOL_GROUPS.flatMap(
  (g) => g.tools,
);

/** Preset colours for overlay styling. */
const PRESET_COLORS = [
  "#2563eb", // blue
  "#ef4444", // red
  "#22c55e", // green
  "#f59e0b", // amber
  "#8b5cf6", // violet
  "#ec4899", // pink
  "#64748b", // slate
  "#ffffff", // white (replaces black for dark theme)
] as const;

/** Preset line widths. */
const LINE_WIDTHS = [1, 2, 3, 4] as const;

/** Shared class fragments to avoid duplication across toolbar buttons. */
const BTN_BASE =
  "px-2.5 py-1.5 text-xs rounded transition-[color,background-color,border-color,transform,box-shadow] disabled:opacity-40 disabled:cursor-not-allowed";
const BTN_SECONDARY =
  "bg-elevated text-t-primary border border-border-strong hover:bg-surface-hover hover:-translate-y-px hover:shadow-sm";
const DIVIDER = "w-px h-5 bg-border-strong mx-1";

interface DrawingToolbarProps {
  chart: Chart | null;
  /** Currently selected overlay ID (set by parent via onSelected callback). */
  selectedOverlayId: string | null;
  /** Called after "clear all" so parent can update persistence. */
  onClearAll?: () => void;
  /** Called after "delete selected" so parent can update persistence. */
  onDeleteSelected?: () => void;
  /** Called after style change so parent can trigger save. */
  onStyleChange?: () => void;
}

export default function DrawingToolbar({
  chart,
  selectedOverlayId,
  onClearAll,
  onDeleteSelected,
  onStyleChange,
}: DrawingToolbarProps) {
  const isDisabled = !chart;
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const [activeColor, setActiveColor] = useState<string | null>(null);
  const [activeLineWidth, setActiveLineWidth] = useState<number | null>(null);

  function handleToolClick(overlayName: string) {
    if (!chart) return;

    if (activeTool === overlayName) {
      setActiveTool(null);
      return;
    }

    setActiveTool(overlayName);
    chart.createOverlay({
      name: overlayName,
      groupId: "user-drawings",
    });
  }

  function handleColorChange(color: string) {
    if (!chart || !selectedOverlayId) return;
    setActiveColor(color);
    chart.overrideOverlay({
      id: selectedOverlayId,
      styles: { line: { color } },
    });
    onStyleChange?.();
  }

  function handleLineWidthChange(size: number) {
    if (!chart || !selectedOverlayId) return;
    setActiveLineWidth(size);
    chart.overrideOverlay({
      id: selectedOverlayId,
      styles: { line: { size } },
    });
    onStyleChange?.();
  }

  function handleDeleteSelected() {
    if (!chart || !selectedOverlayId) return;
    chart.removeOverlay({ id: selectedOverlayId });
    onDeleteSelected?.();
  }

  function handleClearAll() {
    if (!chart) return;
    chart.removeOverlay({ groupId: "user-drawings" });
    setActiveTool(null);
    onClearAll?.();
  }

  const hasSelection = !!selectedOverlayId;

  return (
    <div className="flex flex-wrap items-center gap-1 px-2 py-1.5 border-b border-border bg-surface/90 backdrop-blur-sm">
      {/* Drawing tools — grouped with dividers */}
      {TOOL_GROUPS.map((group, gi) => (
        <div key={gi} className="flex items-center gap-1">
          {group.tools.map((tool) => (
            <button
              key={tool.overlayName}
              type="button"
              disabled={isDisabled}
              onClick={() => handleToolClick(tool.overlayName)}
              className={`${BTN_BASE} ${
                activeTool === tool.overlayName
                  ? "bg-accent text-white border-l-2 border-accent-hover shadow-sm"
                  : BTN_SECONDARY
              }`}
            >
              {tool.label}
            </button>
          ))}
          {gi < TOOL_GROUPS.length - 1 && (
            <div className={DIVIDER} />
          )}
        </div>
      ))}

      <div className={DIVIDER} />

      {/* Style controls — visible when an overlay is selected */}
      {hasSelection && (
        <>
          {PRESET_COLORS.map((color) => (
            <button
              key={color}
              type="button"
              onClick={() => handleColorChange(color)}
              className={`w-6 h-6 rounded-full border transition-shadow ${
                activeColor === color
                  ? "ring-2 ring-offset-1 ring-accent-hover border-accent-hover ring-offset-surface"
                  : "border-border-strong hover:ring-2 hover:ring-accent-hover hover:ring-offset-1 hover:ring-offset-surface"
              }`}
              style={{ backgroundColor: color }}
              aria-label={`Color: ${color}`}
              title={`Color: ${color}`}
            />
          ))}

          <div className={DIVIDER} />

          {LINE_WIDTHS.map((w) => (
            <button
              key={w}
              type="button"
              onClick={() => handleLineWidthChange(w)}
              className={`w-7 h-7 flex items-center justify-center rounded transition-shadow ${
                activeLineWidth === w
                  ? "ring-2 ring-offset-1 ring-accent-hover ring-offset-surface bg-surface-hover"
                  : "bg-elevated border border-border-strong hover:bg-surface-hover"
              }`}
              aria-label={`Line width: ${w}px`}
              title={`Line width: ${w}px`}
            >
              <div
                className="w-4 rounded-full bg-t-secondary"
                style={{ height: `${w}px` }}
              />
            </button>
          ))}

          <div className={DIVIDER} />
        </>
      )}

      {/* Actions */}
      <button
        type="button"
        disabled={isDisabled || !hasSelection}
        onClick={handleDeleteSelected}
        className={`${BTN_BASE} ${BTN_SECONDARY}`}
      >
        Delete
      </button>

      <button
        type="button"
        disabled={isDisabled}
        onClick={handleClearAll}
        className={`${BTN_BASE} bg-elevated text-loss border border-loss/40 hover:bg-loss-subtle hover:-translate-y-px hover:shadow-sm`}
      >
        Clear All
      </button>
    </div>
  );
}

export { DRAWING_TOOLS };
export type { DrawingToolbarProps };
