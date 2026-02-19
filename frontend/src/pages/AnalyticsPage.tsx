import { useState, useCallback, useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchBySymbol, fetchPerformance, fetchDailySummaries, fetchAvailableAssetClasses } from "../api/client";
import EquityCurve from "../components/EquityCurve";
import SymbolBreakdown from "../components/SymbolBreakdown";
import DateRangeSelector, { type DateRange } from "../components/DateRangeSelector";
import AssetClassFilter from "../components/AssetClassFilter";

const STORAGE_KEY = "analytics_asset_class_filter";

/** 从 localStorage 读取保存的选择；返回 null 表示无历史记录 */
function loadSavedSelection(): string[] | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === null) return null; // 无历史记录
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return parsed;
    return null;
  } catch {
    return null;
  }
}

/** 将选择持久化到 localStorage */
function saveSelection(assetClasses: string[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(assetClasses));
  } catch {
    // ignore quota errors
  }
}

export default function AnalyticsPage() {
  const [dateRange, setDateRange] = useState<DateRange>({});
  // null 表示尚未初始化（等待 availableAssetClasses 加载后确定初始值）
  const [selectedAssetClasses, setSelectedAssetClasses] = useState<string[] | null>(null);
  // 标记是否已完成初始化
  const initializedRef = useRef(false);

  // 获取可用资产类型列表
  const { data: availableAssetClasses = [] } = useQuery({
    queryKey: ["availableAssetClasses"],
    queryFn: fetchAvailableAssetClasses,
    staleTime: 5 * 60 * 1000, // 5分钟缓存
  });

  // 当 availableAssetClasses 加载完成后，初始化选择状态
  useEffect(() => {
    if (availableAssetClasses.length === 0 || initializedRef.current) return;
    initializedRef.current = true;

    const saved = loadSavedSelection();
    if (saved === null) {
      // 首次访问或无历史记录 → 默认全选
      setSelectedAssetClasses([...availableAssetClasses]);
    } else {
      // 有历史记录 → 恢复上次选择（过滤掉已不存在的资产类型）
      const validSet = new Set(availableAssetClasses);
      const restored = saved.filter((ac) => validSet.has(ac));
      setSelectedAssetClasses(restored);
    }
  }, [availableAssetClasses]);

  // 选择变化时持久化到 localStorage
  useEffect(() => {
    if (selectedAssetClasses === null) return; // 未初始化，不保存
    saveSelection(selectedAssetClasses);
  }, [selectedAssetClasses]);

  // 传给后端的 asset_classes 参数：
  // - undefined（初始加载、selectedAssetClasses 尚未初始化）: 不过滤，查询全部
  // - []（用户主动清空所有勾选）: 传空数组，后端返回空结果
  // - [...items]（用户勾选了部分/全部）: 按选中的资产类型过滤
  const assetClassesParam =
    selectedAssetClasses === null
      ? undefined                    // 尚未初始化，不过滤
      : selectedAssetClasses;        // 直接透传，包括空数组

  const { data: metrics } = useQuery({
    queryKey: ["performance", dateRange.from, dateRange.to, assetClassesParam],
    queryFn: () => fetchPerformance(dateRange.from, dateRange.to, assetClassesParam),
  });

  const { data: symbols } = useQuery({
    queryKey: ["bySymbol", dateRange.from, dateRange.to, assetClassesParam],
    queryFn: () => fetchBySymbol(dateRange.from, dateRange.to, assetClassesParam),
  });

  const { data: dailyData } = useQuery({
    queryKey: ["dailySummaries", dateRange.from, dateRange.to, assetClassesParam],
    queryFn: () => fetchDailySummaries(dateRange.from, dateRange.to, assetClassesParam),
  });

  const handleAssetClassChange = useCallback((acs: string[]) => {
    setSelectedAssetClasses(acs);
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h1 className="text-xl font-semibold">Analytics</h1>
        <div className="flex flex-wrap items-center gap-3">
          <AssetClassFilter
            availableAssetClasses={availableAssetClasses}
            selectedAssetClasses={selectedAssetClasses ?? []}
            onChange={handleAssetClassChange}
          />
          <DateRangeSelector value={dateRange} onChange={setDateRange} />
        </div>
      </div>

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
