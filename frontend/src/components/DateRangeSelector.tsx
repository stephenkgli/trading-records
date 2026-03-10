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

  const showCustomInputs = activePreset === "custom";

  const handlePresetClick = (key: PresetKey) => {
    setActivePreset(key);
    if (key !== "custom") {
      onChange(computePresetRange(key));
    }
  };

  const handleFromChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange({ ...value, from: e.target.value || undefined });
  };

  const handleToChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange({ ...value, to: e.target.value || undefined });
  };

  const rangeDescription = useMemo(() => {
    if (!value.from && !value.to) return "All time";
    if (value.from && value.to) return `${value.from} — ${value.to}`;
    if (value.from) return `From ${value.from}`;
    return `Until ${value.to}`;
  }, [value.from, value.to]);

  return (
    <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
      <div className="flex rounded-lg border border-[--color-border] bg-elevated overflow-hidden">
        {PRESETS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => handlePresetClick(key)}
            className={`px-3 py-1.5 text-xs font-medium transition-all duration-150 focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none
              ${
                activePreset === key
                  ? "bg-accent text-white"
                  : "text-[--color-text-secondary] hover:bg-[--color-bg-hover] hover:text-[--color-text-primary]"
              }
            `}
          >
            {label}
          </button>
        ))}
      </div>

      {showCustomInputs && (
        <div className="flex items-center gap-2">
          <input
            type="date"
            name="date-from"
            autoComplete="off"
            aria-label="Start date"
            value={value.from ?? ""}
            onChange={handleFromChange}
            className="bg-elevated border border-[--color-border] rounded-md px-2 py-1 text-xs text-[--color-text-primary] outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:border-accent"
          />
          <span className="text-[--color-text-muted] text-xs">to</span>
          <input
            type="date"
            name="date-to"
            autoComplete="off"
            aria-label="End date"
            value={value.to ?? ""}
            onChange={handleToChange}
            className="bg-elevated border border-[--color-border] rounded-md px-2 py-1 text-xs text-[--color-text-primary] outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:border-accent"
          />
        </div>
      )}

      <span className="text-xs text-[--color-text-muted] hidden sm:inline">{rangeDescription}</span>
    </div>
  );
}
