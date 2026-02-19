import { useState, useRef, useEffect, useMemo } from "react";

/** 资产类型的显示名称映射 */
const ASSET_CLASS_LABELS: Record<string, string> = {
  stock: "Stock",
  future: "Future",
  option: "Option",
  forex: "Forex",
  etf: "ETF",
  bond: "Bond",
  fund: "Fund",
  crypto: "Crypto",
};

/** 资产类型的图标/颜色标记 */
const ASSET_CLASS_COLORS: Record<string, string> = {
  stock: "bg-blue-100 text-blue-700",
  future: "bg-orange-100 text-orange-700",
  option: "bg-purple-100 text-purple-700",
  forex: "bg-green-100 text-green-700",
  etf: "bg-cyan-100 text-cyan-700",
  bond: "bg-gray-100 text-gray-700",
  fund: "bg-pink-100 text-pink-700",
  crypto: "bg-yellow-100 text-yellow-700",
};

function getLabel(ac: string): string {
  return ASSET_CLASS_LABELS[ac] || ac.charAt(0).toUpperCase() + ac.slice(1);
}

function getColorClass(ac: string): string {
  return ASSET_CLASS_COLORS[ac] || "bg-gray-100 text-gray-700";
}

interface Props {
  /** 所有可用资产类型列表（来自后端） */
  availableAssetClasses: string[];
  /** 当前选中的资产类型列表（空数组表示未选任何项） */
  selectedAssetClasses: string[];
  /** 选中变化回调 */
  onChange: (assetClasses: string[]) => void;
}

export default function AssetClassFilter({
  availableAssetClasses,
  selectedAssetClasses,
  onChange,
}: Props) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // 点击外部关闭下拉
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // 是否全选状态：选中数量等于全部可用数量
  const isAllSelected =
    availableAssetClasses.length > 0 &&
    selectedAssetClasses.length === availableAssetClasses.length;

  // 是否未选中任何项
  const isNoneSelected = selectedAssetClasses.length === 0;

  // 当前激活的资产类型集合
  const activeSet = useMemo(
    () => new Set(selectedAssetClasses),
    [selectedAssetClasses],
  );

  const handleToggle = (ac: string) => {
    if (activeSet.has(ac)) {
      // 取消勾选：直接移除，允许全部取消
      const newList = selectedAssetClasses.filter((s) => s !== ac);
      onChange(newList);
    } else {
      // 勾选：添加
      onChange([...selectedAssetClasses, ac]);
    }
  };

  const handleSelectAll = () => {
    // 只有点击 Select All 按钮时才全选
    onChange([...availableAssetClasses]);
  };

  const handleClearAll = () => {
    // 清除所有选中
    onChange([]);
  };

  // 显示标签文本
  const displayLabel = isAllSelected
    ? "All Types"
    : isNoneSelected
      ? "No Filter"
      : selectedAssetClasses.length === 1
        ? getLabel(selectedAssetClasses[0])
        : `${selectedAssetClasses.length} Types`;

  return (
    <div ref={containerRef} className="relative">
      {/* 触发按钮 */}
      <button
        onClick={() => setOpen(!open)}
        className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors
          ${
            isAllSelected || isNoneSelected
              ? "border-gray-200 bg-gray-50 text-gray-600 hover:bg-gray-100"
              : "border-blue-300 bg-blue-50 text-blue-700 hover:bg-blue-100"
          }
        `}
      >
        <svg
          className="w-3.5 h-3.5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
          />
        </svg>
        {displayLabel}
        <svg
          className={`w-3 h-3 transition-transform ${open ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {/* 下拉面板 */}
      {open && (
        <div className="absolute top-full left-0 mt-1 w-56 bg-white rounded-lg shadow-lg border border-gray-200 z-50">
          {/* 全选/清除按钮 */}
          <div className="flex gap-2 px-3 py-2 border-b border-gray-100">
            <button
              onClick={handleSelectAll}
              className={`text-xs px-2 py-0.5 rounded transition-colors ${
                isAllSelected
                  ? "bg-blue-100 text-blue-700"
                  : "text-blue-600 hover:bg-blue-50"
              }`}
            >
              Select All
            </button>
            <button
              onClick={handleClearAll}
              className="text-xs text-gray-500 hover:text-gray-700 px-2 py-0.5 rounded hover:bg-gray-50 transition-colors"
            >
              Clear
            </button>
            <span className="ml-auto text-xs text-gray-400">
              {selectedAssetClasses.length}/{availableAssetClasses.length}
            </span>
          </div>

          {/* 资产类型列表 */}
          <div className="py-1">
            {availableAssetClasses.length === 0 ? (
              <p className="text-xs text-gray-400 text-center py-3">
                No asset classes found
              </p>
            ) : (
              availableAssetClasses.map((ac) => {
                const isChecked = activeSet.has(ac);
                return (
                  <label
                    key={ac}
                    className="flex items-center gap-2.5 px-3 py-2 hover:bg-gray-50 cursor-pointer transition-colors"
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => handleToggle(ac)}
                      className="w-3.5 h-3.5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${getColorClass(ac)}`}
                    >
                      {getLabel(ac)}
                    </span>
                  </label>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
