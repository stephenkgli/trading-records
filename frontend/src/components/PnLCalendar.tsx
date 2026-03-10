import { useQuery } from "@tanstack/react-query";
import { useState, useMemo, lazy, Suspense } from "react";
import { fetchCalendar, type CalendarEntry } from "../api/client";

const DayTradesModal = lazy(() => import("./DayTradesModal"));

const preloadDayTrades = () => void import("./DayTradesModal");

export default function PnLCalendar() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  const { data } = useQuery({
    queryKey: ["calendar", year, month],
    queryFn: () => fetchCalendar(year, month),
  });

  const calendarGrid = useMemo(() => {
    const firstDay = new Date(year, month - 1, 1);
    const lastDay = new Date(year, month, 0);
    const daysInMonth = lastDay.getDate();
    const startDow = firstDay.getDay(); // 0 = Sunday

    const dataMap = new Map<string, CalendarEntry>();
    data?.forEach((entry) => {
      dataMap.set(entry.date, entry);
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

    return cells;
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
        <button onClick={prevMonth} aria-label="Previous month" className="px-2 py-1 text-gray-500 hover:text-gray-700 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none">&lt;</button>
        <span className="text-sm font-medium">{monthName}</span>
        <button onClick={nextMonth} aria-label="Next month" className="px-2 py-1 text-gray-500 hover:text-gray-700 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none">&gt;</button>
      </div>

      <div className="grid grid-cols-7 gap-1 text-xs">
        {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
          <div key={d} className="text-center text-gray-400 font-medium py-1">{d}</div>
        ))}

        {calendarGrid.map((cell, i) => {
          if (cell.day === null) {
            return <div key={`empty-${i}`} />;
          }

          const pnl = cell.entry ? Number(cell.entry.net_pnl) : 0;
          const hasData = cell.entry !== null;
          const hasActivity = cell.entry?.has_activity === true;
          const bgColor = !hasData
            ? "bg-gray-50"
            : pnl > 0
              ? "bg-green-100"
              : pnl < 0
                ? "bg-red-100"
                : "bg-gray-100";

          const cellClassName = `${bgColor} rounded p-1 min-h-[40px] flex flex-col items-center justify-center ${
            hasActivity ? "cursor-pointer hover:ring-2 hover:ring-blue-400" : ""
          }`;
          const cellTitle = hasData ? `$${pnl.toFixed(2)} (${cell.entry!.trade_count} trades)` : "";
          const cellChildren = (
            <>
              <span className="text-gray-600">{cell.day}</span>
              {hasData ? (
                <span
                  className={`text-[10px] font-medium ${pnl >= 0 ? "text-green-700" : "text-red-700"}`}
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
              title={cellTitle}
            >
              {cellChildren}
            </div>
          );
        })}
      </div>

      {selectedDate && (
        <Suspense fallback={null}>
          <DayTradesModal
            date={selectedDate}
            onClose={() => setSelectedDate(null)}
          />
        </Suspense>
      )}
    </div>
  );
}
