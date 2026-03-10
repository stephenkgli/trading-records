import { useState, useMemo } from "react";
import {
  format,
  subDays,
  startOfMonth,
  startOfQuarter,
  startOfYear,
} from "date-fns";

export interface DateRange {
  from?: string; // "YYYY-MM-DD"
  to?: string;   // "YYYY-MM-DD"
}

type PresetKey = "all" | "7d" | "30d" | "mtd" | "qtd" | "ytd" | "custom";

interface PresetOption {
  key: PresetKey;
  label: string;
}

const PRESETS: PresetOption[] = [
  { key: "all", label: "All" },
  { key: "7d", label: "7D" },
  { key: "30d", label: "30D" },
  { key: "mtd", label: "MTD" },
  { key: "qtd", label: "QTD" },
  { key: "ytd", label: "YTD" },
  { key: "custom", label: "Custom" },
];

function computePresetRange(key: PresetKey): DateRange {
  const today = new Date();
  const todayStr = format(today, "yyyy-MM-dd");

  switch (key) {
    case "all":
      return {};
    case "7d":
      return { from: format(subDays(today, 6), "yyyy-MM-dd"), to: todayStr };
    case "30d":
      return { from: format(subDays(today, 29), "yyyy-MM-dd"), to: todayStr };
    case "mtd":
      return { from: format(startOfMonth(today), "yyyy-MM-dd"), to: todayStr };
    case "qtd":
      return { from: format(startOfQuarter(today), "yyyy-MM-dd"), to: todayStr };
    case "ytd":
      return { from: format(startOfYear(today), "yyyy-MM-dd"), to: todayStr };
    case "custom":
      return {};
    default:
      return {};
  }
}

interface Props {
  value: DateRange;
  onChange: (range: DateRange) => void;
}

export default function DateRangeSelector({ value, onChange }: Props) {
  const [activePreset, setActivePreset] = useState<PresetKey>("all");

  // 当预设不是 custom 时，自定义日期输入框不展示
  const showCustomInputs = activePreset === "custom";

  // 预设按钮点击
  const handlePresetClick = (key: PresetKey) => {
    setActivePreset(key);
    if (key !== "custom") {
      onChange(computePresetRange(key));
    }
  };

  // 自定义日期变更
  const handleFromChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange({ ...value, from: e.target.value || undefined });
  };

  const handleToChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange({ ...value, to: e.target.value || undefined });
  };

  // 显示当前时间范围的描述
  const rangeDescription = useMemo(() => {
    if (!value.from && !value.to) return "All time";
    if (value.from && value.to) return `${value.from} — ${value.to}`;
    if (value.from) return `From ${value.from}`;
    return `Until ${value.to}`;
  }, [value.from, value.to]);

  return (
    <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
      {/* 预设按钮组 */}
      <div className="flex rounded-lg border border-gray-200 bg-gray-50 overflow-hidden">
        {PRESETS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => handlePresetClick(key)}
            className={`px-3 py-1.5 text-xs font-medium transition-[color,background-color] focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none
              ${
                activePreset === key
                  ? "bg-blue-600 text-white"
                  : "text-gray-600 hover:bg-gray-100"
              }
            `}
          >
            {label}
          </button>
        ))}
      </div>

      {/* 自定义日期输入 */}
      {showCustomInputs && (
        <div className="flex items-center gap-2">
          <input
            type="date"
            name="date-from"
            autoComplete="off"
            aria-label="Start date"
            value={value.from ?? ""}
            onChange={handleFromChange}
            className="border border-gray-300 rounded-md px-2 py-1 text-xs outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:border-blue-500"
          />
          <span className="text-gray-400 text-xs">to</span>
          <input
            type="date"
            name="date-to"
            autoComplete="off"
            aria-label="End date"
            value={value.to ?? ""}
            onChange={handleToChange}
            className="border border-gray-300 rounded-md px-2 py-1 text-xs outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:border-blue-500"
          />
        </div>
      )}

      {/* 当前范围描述 */}
      <span className="text-xs text-gray-400 hidden sm:inline">{rangeDescription}</span>
    </div>
  );
}
