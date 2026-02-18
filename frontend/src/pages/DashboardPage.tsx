import { useQuery } from "@tanstack/react-query";
import { fetchPerformance, fetchBySymbol, fetchDailySummaries } from "../api/client";
import MetricsCards from "../components/MetricsCards";
import EquityCurve from "../components/EquityCurve";
import SymbolBreakdown from "../components/SymbolBreakdown";
import PnLCalendar from "../components/PnLCalendar";

export default function DashboardPage() {
  const { data: metrics } = useQuery({
    queryKey: ["performance"],
    queryFn: () => fetchPerformance(),
  });

  const { data: symbols } = useQuery({
    queryKey: ["bySymbol"],
    queryFn: () => fetchBySymbol(),
  });

  const { data: dailyData } = useQuery({
    queryKey: ["dailySummaries"],
    queryFn: () => fetchDailySummaries(),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Dashboard</h1>

      {metrics && <MetricsCards metrics={metrics} />}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-4">
          <h2 className="text-sm font-medium text-gray-500 mb-3">P&L Calendar</h2>
          <PnLCalendar />
        </div>

        <div className="bg-white rounded-lg shadow p-4">
          <h2 className="text-sm font-medium text-gray-500 mb-3">Equity Curve</h2>
          {dailyData && <EquityCurve data={dailyData} />}
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-4">
        <h2 className="text-sm font-medium text-gray-500 mb-3">P&L by Symbol</h2>
        {symbols && <SymbolBreakdown data={symbols} />}
      </div>
    </div>
  );
}
