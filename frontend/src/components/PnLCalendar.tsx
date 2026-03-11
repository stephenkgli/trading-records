import { useQuery } from "@tanstack/react-query";
import { useState, useMemo, lazy, Suspense } from "react";
import { createPortal } from "react-dom";
import { fetchCalendar } from "../api/endpoints/analytics";
import type { CalendarEntry } from "../api/types";

const DayTradesModal = lazy(() => import("./DayTradesModal"));

const preloadDayTrades = () => void import("./DayTradesModal");

/** Map PnL magnitude to opacity for intensity-based coloring. */
function pnlOpacity(pnl: number, maxAbs: number): number {
  if (maxAbs === 0) return 0.3;
  return Math.max(0.2, Math.min(0.7, Math.abs(pnl) / maxAbs));
}

export default function PnLCalendar() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  const { data } = useQuery({
    queryKey: ["calendar", year, month],
    queryFn: () => fetchCalendar(year, month),
  });

  const { calendarGrid, maxAbsPnl } = useMemo(() => {
    const firstDay = new Date(year, month - 1, 1);
    const lastDay = new Date(year, month, 0);
    const daysInMonth = lastDay.getDate();
    const startDow = firstDay.getDay(); // 0 = Sunday

    const dataMap = new Map<string, CalendarEntry>();
    let maxAbs = 0;
    data?.forEach((entry) => {
      dataMap.set(entry.date, entry);
      const abs = Math.abs(Number(entry.net_pnl));
      if (abs > maxAbs) maxAbs = abs;
    });

    const cells: Array<{ day: number | null; dateStr: string | null; entry: CalendarEntry | null }> = [];

    // Leading empty cells
    for (let i = 0; i < startDow; i++) {
      cells.push({ day: null, dateStr: null, entry: null });
    }

    // Day cells
    for (let d = 1; d <= daysInMonth; d++) {
      const dateStr = `${year}-${String(month).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
      cells.push({ day: d, dateStr, entry: dataMap.get(dateStr) || null });
    }

    return { calendarGrid: cells, maxAbsPnl: maxAbs };
  }, [year, month, data]);

  const prevMonth = () => {
    if (month === 1) {
      setYear(year - 1);
      setMonth(12);
    } else {
      setMonth(month - 1);
    }
  };

  const nextMonth = () => {
    if (month === 12) {
      setYear(year + 1);
      setMonth(1);
    } else {
      setMonth(month + 1);
    }
  };

  const monthName = new Date(year, month - 1).toLocaleString(undefined, { month: "long", year: "numeric" });

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <button
          onClick={prevMonth}
          aria-label="Previous month"
          className="w-8 h-8 flex items-center justify-center rounded-md text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-bg-hover] transition-colors focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M10 12L6 8l4-4"/></svg>
        </button>
        <span className="text-sm font-medium text-[--color-text-primary]">{monthName}</span>
        <button
          onClick={nextMonth}
          aria-label="Next month"
          className="w-8 h-8 flex items-center justify-center rounded-md text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-bg-hover] transition-colors focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M6 4l4 4-4 4"/></svg>
        </button>
      </div>

      <div className="grid grid-cols-7 gap-1 text-xs">
        {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
          <div key={d} className="text-center text-[--color-text-muted] font-medium py-1">{d}</div>
        ))}

        {calendarGrid.map((cell, i) => {
          if (cell.day === null) {
            return <div key={`empty-${i}`} />;
          }

          const pnl = cell.entry ? Number(cell.entry.net_pnl) : 0;
          const hasData = cell.entry !== null;
          const hasActivity = cell.entry?.has_activity === true;

          const bgStyle: React.CSSProperties = !hasData
            ? { backgroundColor: "var(--color-bg-elevated)" }
            : pnl > 0
              ? { backgroundColor: `rgba(16, 185, 129, ${pnlOpacity(pnl, maxAbsPnl)})` }
              : pnl < 0
                ? { backgroundColor: `rgba(244, 63, 94, ${pnlOpacity(pnl, maxAbsPnl)})` }
                : { backgroundColor: "rgba(99, 102, 241, 0.15)" };

          const cellClassName = `rounded p-1 min-h-[40px] flex flex-col items-center justify-center transition-all duration-150 ${
            hasActivity ? "cursor-pointer hover:ring-2 hover:ring-accent hover:brightness-110 focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none" : ""
          }`;
          const cellTitle = hasData ? `$${pnl.toFixed(2)} (${cell.entry!.trade_count} trades)` : "";
          const cellChildren = (
            <>
              <span className="text-[--color-text-secondary] text-[11px]">{cell.day}</span>
              {hasData ? (
                <span
                  className={`text-[10px] font-mono font-medium ${pnl >= 0 ? "text-profit" : "text-loss"}`}
                  style={{ fontVariantNumeric: "tabular-nums" }}
                >
                  ${Math.abs(pnl).toFixed(0)}
                </span>
              ) : null}
            </>
          );

          return hasActivity ? (
            <button
              type="button"
              key={`day-${year}-${month}-${cell.day}`}
              className={cellClassName}
              style={bgStyle}
              title={cellTitle}
              onClick={() => setSelectedDate(cell.dateStr)}
              onMouseEnter={preloadDayTrades}
            >
              {cellChildren}
            </button>
          ) : (
            <div
              key={`day-${year}-${month}-${cell.day}`}
              className={cellClassName}
              style={bgStyle}
              title={cellTitle}
            >
              {cellChildren}
            </div>
          );
        })}
      </div>

      {selectedDate && createPortal(
        <Suspense fallback={null}>
          <DayTradesModal
            date={selectedDate}
            onClose={() => setSelectedDate(null)}
          />
        </Suspense>,
        document.body,
      )}
    </div>
  );
}
