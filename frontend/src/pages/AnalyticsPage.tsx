import { useQuery } from "@tanstack/react-query";
import { fetchBySymbol, fetchPerformance, fetchDailySummaries } from "../api/client";
import EquityCurve from "../components/EquityCurve";
import SymbolBreakdown from "../components/SymbolBreakdown";

export default function AnalyticsPage() {
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
      <h1 className="text-xl font-semibold">Analytics</h1>

      {/* Performance Stats */}
      {metrics && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-medium mb-4">Performance Metrics</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 text-sm">
            <Stat label="Net P&L" value={`$${Number(metrics.net_pnl).toFixed(2)}`}
              color={Number(metrics.net_pnl) >= 0 ? "green" : "red"} />
            <Stat label="Total Trades" value={String(metrics.total_trades)} />
            <Stat label="Win Rate" value={`${metrics.win_rate}%`}
              color={metrics.win_rate >= 50 ? "green" : "red"} />
<Stat label="Win/Loss Ratio" value={metrics.win_loss_ratio !== null ? String(metrics.win_loss_ratio) : "N/A"} />
            <Stat label="Avg Win" value={`$${Number(metrics.avg_win).toFixed(2)}`} color="green" />
            <Stat label="Avg Loss" value={`$${Number(metrics.avg_loss).toFixed(2)}`} color="red" />
            <Stat label="Expectancy" value={`$${Number(metrics.expectancy).toFixed(2)}`}
              color={Number(metrics.expectancy) >= 0 ? "green" : "red"} />
            <Stat label="Trading Days" value={String(metrics.trading_days)} />
          </div>
        </div>
      )}

      {/* Equity Curve */}
      <div className="bg-white rounded-lg shadow p-4">
        <h2 className="text-sm font-medium text-gray-500 mb-3">Equity Curve</h2>
        {dailyData && <EquityCurve data={dailyData} />}
      </div>

      {/* Symbol Breakdown */}
      <div className="bg-white rounded-lg shadow p-4">
        <h2 className="text-sm font-medium text-gray-500 mb-3">P&L by Symbol</h2>
        {symbols && <SymbolBreakdown data={symbols} />}
      </div>
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  const colorClass =
    color === "green" ? "text-green-600" : color === "red" ? "text-red-600" : "text-gray-900";
  return (
    <div>
      <span className="text-gray-500 block">{label}</span>
      <span className={`text-lg font-semibold ${colorClass}`}>{value}</span>
    </div>
  );
}
