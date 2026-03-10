import { useState, useMemo, memo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchBySymbol, fetchPerformance, fetchDailySummaries } from "../api/client";
import EquityCurve from "../components/EquityCurve";
import SymbolBreakdown from "../components/SymbolBreakdown";
import DateRangeSelector, { type DateRange } from "../components/DateRangeSelector";
import AssetClassFilter from "../components/AssetClassFilter";
import { useAssetClassFilter } from "../hooks/useAssetClassFilter";

const Stat = memo(function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  const colorClass =
    color === "green" ? "text-profit" : color === "red" ? "text-loss" : "text-[--color-text-primary]";
  return (
    <div className="py-2">
      <span className="text-[--color-text-muted] block text-[10px] uppercase tracking-widest mb-1">{label}</span>
      <span className={`text-lg font-semibold font-mono ${colorClass}`} style={{ fontVariantNumeric: "tabular-nums" }}>{value}</span>
    </div>
  );
});

export default function AnalyticsPage() {
  const [dateRange, setDateRange] = useState<DateRange>({});
  const {
    availableAssetClasses,
    selectedAssetClasses,
    setSelectedAssetClasses,
    assetClassesParam,
    isInitialized,
  } = useAssetClassFilter("analytics_asset_class_filter");

  const { data: metrics, isLoading: metricsLoading } = useQuery({
    queryKey: ["performance", { from: dateRange.from, to: dateRange.to, assetClasses: assetClassesParam }],
    queryFn: () => fetchPerformance(dateRange.from, dateRange.to, assetClassesParam),
    enabled: isInitialized,
  });

  const { data: symbols } = useQuery({
    queryKey: ["bySymbol", { from: dateRange.from, to: dateRange.to, assetClasses: assetClassesParam }],
    queryFn: () => fetchBySymbol(dateRange.from, dateRange.to, assetClassesParam),
    enabled: isInitialized,
  });

  const { data: dailyData } = useQuery({
    queryKey: ["dailySummaries", { from: dateRange.from, to: dateRange.to, assetClasses: assetClassesParam }],
    queryFn: () => fetchDailySummaries(dateRange.from, dateRange.to, assetClassesParam),
    enabled: isInitialized,
  });

  const stats = useMemo(() => {
    if (!metrics) return [];

    const fmtCurrency = new Intl.NumberFormat(undefined, { style: "currency", currency: "USD" });

    return [
      {
        label: "Net P&L",
        value: fmtCurrency.format(Number(metrics.net_pnl)),
        color: Number(metrics.net_pnl) >= 0 ? "green" : "red",
      },
      { label: "Total Trades", value: new Intl.NumberFormat().format(metrics.total_trades) },
      {
        label: "Win Rate",
        value: `${metrics.win_rate}%`,
        color: metrics.win_rate >= 50 ? "green" : "red",
      },
      {
        label: "Win/Loss Ratio",
        value: metrics.win_loss_ratio !== null ? String(metrics.win_loss_ratio) : "N/A",
      },
      {
        label: "Avg Win",
        value: fmtCurrency.format(Number(metrics.avg_win)),
        color: "green",
      },
      {
        label: "Avg Loss",
        value: fmtCurrency.format(Number(metrics.avg_loss)),
        color: "red",
      },
      {
        label: "Expectancy",
        value: fmtCurrency.format(Number(metrics.expectancy)),
        color: Number(metrics.expectancy) >= 0 ? "green" : "red",
      },
      { label: "Trading Days", value: String(metrics.trading_days) },
    ];
  }, [metrics]);

  return (
    <div className="stagger-in space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h1 className="font-display text-3xl text-[--color-text-primary] tracking-tight">Analytics</h1>
        <div className="flex flex-wrap items-center gap-3">
          <AssetClassFilter
            availableAssetClasses={availableAssetClasses}
            selectedAssetClasses={selectedAssetClasses ?? []}
            onChange={setSelectedAssetClasses}
          />
          <DateRangeSelector value={dateRange} onChange={setDateRange} />
        </div>
      </div>

      {/* Performance Stats */}
      {metricsLoading ? (
        <div className="bg-surface rounded-lg border border-[--color-border] p-6">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="h-14 bg-elevated animate-pulse rounded" />
            ))}
          </div>
        </div>
      ) : metrics ? (
        <div className="bg-surface rounded-lg border border-[--color-border] p-6">
          <h2 className="text-[10px] font-medium text-[--color-text-muted] mb-4 uppercase tracking-widest">Performance Metrics</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-1 text-sm">
            {stats.map((stat) => (
              <Stat
                key={stat.label}
                label={stat.label}
                value={stat.value}
                color={stat.color}
              />
            ))}
          </div>
        </div>
      ) : null}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Equity Curve */}
        <div className="bg-surface rounded-lg border border-[--color-border] p-5">
          <h2 className="text-[10px] font-medium text-[--color-text-muted] mb-3 uppercase tracking-widest">Equity Curve</h2>
          {dailyData && <EquityCurve data={dailyData} />}
        </div>

        {/* Symbol Breakdown */}
        <div className="bg-surface rounded-lg border border-[--color-border] p-5">
          <h2 className="text-[10px] font-medium text-[--color-text-muted] mb-3 uppercase tracking-widest">P&L by Symbol</h2>
          {symbols && <SymbolBreakdown data={symbols} />}
        </div>
      </div>
    </div>
  );
}
