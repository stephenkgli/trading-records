import { useQuery } from "@tanstack/react-query";
import { fetchPerformance, fetchDailySummaries } from "../api/client";
import MetricsCards from "../components/MetricsCards";
import EquityCurve from "../components/EquityCurve";
import PnLCalendar from "../components/PnLCalendar";

export default function DashboardPage() {
  const { data: metrics, isLoading: metricsLoading, error: metricsError } = useQuery({
    queryKey: ["performance"],
    queryFn: () => fetchPerformance(),
  });

  const { data: dailyData, isLoading: dailyLoading, error: dailyError } = useQuery({
    queryKey: ["dailySummaries"],
    queryFn: () => fetchDailySummaries(),
  });

  return (
    <div className="stagger-in space-y-5">
      <h1 className="font-display text-3xl text-[--color-text-primary] tracking-tight">Dashboard</h1>

      {metricsLoading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-surface rounded-lg border border-[--color-border] p-4 h-[88px] animate-pulse" />
          ))}
        </div>
      ) : metricsError ? (
        <div className="bg-surface rounded-lg border border-[--color-border] p-6 text-center">
          <p className="text-loss text-sm">Failed to load performance metrics</p>
          <p className="text-[--color-text-muted] text-xs mt-1">Please check your connection and try again.</p>
        </div>
      ) : metrics ? (
        <MetricsCards metrics={metrics} />
      ) : null}

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
        <div className="lg:col-span-3 bg-surface rounded-lg border border-[--color-border] p-5">
          <h2 className="text-[10px] font-medium text-[--color-text-muted] mb-4 uppercase tracking-widest">P&L Calendar</h2>
          <PnLCalendar />
        </div>

        <div className="lg:col-span-2 bg-surface rounded-lg border border-[--color-border] p-5 flex flex-col">
          <h2 className="text-[10px] font-medium text-[--color-text-muted] mb-4 uppercase tracking-widest">Equity Curve</h2>
          <div className="flex-1 min-h-0">
            {dailyLoading ? (
              <div className="h-[250px] bg-elevated animate-pulse rounded" />
            ) : dailyError ? (
              <div className="flex items-center justify-center h-[250px]">
                <p className="text-loss text-sm">Failed to load equity data</p>
              </div>
            ) : dailyData ? (
              <EquityCurve data={dailyData} />
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
