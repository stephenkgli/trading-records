import { useState, useRef, useEffect, useMemo, useCallback } from "react";
import { createPortal } from "react-dom";

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

const ASSET_CLASS_COLORS: Record<string, string> = {
  stock: "bg-[rgba(59,130,246,0.15)] text-[#60a5fa]",
  future: "bg-[rgba(249,115,22,0.15)] text-[#fb923c]",
  option: "bg-[rgba(168,85,247,0.15)] text-[#c084fc]",
  forex: "bg-profit-subtle text-profit",
  etf: "bg-[rgba(34,211,238,0.15)] text-[#22d3ee]",
  bond: "bg-elevated text-[--color-text-secondary]",
  fund: "bg-[rgba(236,72,153,0.15)] text-[#f472b6]",
  crypto: "bg-[rgba(250,204,21,0.15)] text-[#facc15]",
};

function getLabel(ac: string): string {
  return ASSET_CLASS_LABELS[ac] || ac.charAt(0).toUpperCase() + ac.slice(1);
}

function getColorClass(ac: string): string {
  return ASSET_CLASS_COLORS[ac] || "bg-elevated text-[--color-text-secondary]";
}

interface Props {
  availableAssetClasses: string[];
  selectedAssetClasses: string[];
  onChange: (assetClasses: string[]) => void;
}

export default function AssetClassFilter({
  availableAssetClasses,
  selectedAssetClasses,
  onChange,
}: Props) {
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const [dropdownStyle, setDropdownStyle] = useState<React.CSSProperties>({});

  // Position dropdown below button when opened
  useEffect(() => {
    if (open && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      setDropdownStyle({
        top: rect.bottom + 4,
        left: rect.left,
      });
    }
  }, [open]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function handleClickOutside(e: MouseEvent) {
      const target = e.target as Node;
      if (
        buttonRef.current && !buttonRef.current.contains(target) &&
        dropdownRef.current && !dropdownRef.current.contains(target)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const isAllSelected =
    availableAssetClasses.length > 0 &&
    selectedAssetClasses.length === availableAssetClasses.length;

  const isNoneSelected = selectedAssetClasses.length === 0;

  const activeSet = useMemo(
    () => new Set(selectedAssetClasses),
    [selectedAssetClasses],
  );

  const handleToggle = useCallback((ac: string) => {
    if (activeSet.has(ac)) {
      const newList = selectedAssetClasses.filter((s) => s !== ac);
      onChange(newList);
    } else {
      onChange([...selectedAssetClasses, ac]);
    }
  }, [activeSet, selectedAssetClasses, onChange]);

  const handleSelectAll = useCallback(() => {
    onChange([...availableAssetClasses]);
  }, [availableAssetClasses, onChange]);

  const handleClearAll = useCallback(() => {
    onChange([]);
  }, [onChange]);

  const displayLabel = isAllSelected
    ? "All Types"
    : isNoneSelected
      ? "No Filter"
      : selectedAssetClasses.length === 1
        ? getLabel(selectedAssetClasses[0])
        : `${selectedAssetClasses.length} Types`;

  return (
    <div className="relative">
      <button
        ref={buttonRef}
        onClick={() => setOpen(!open)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label="Filter by asset class"
        className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border transition-all duration-150 focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none
          ${
            isAllSelected || isNoneSelected
              ? "border-[--color-border] bg-elevated text-[--color-text-secondary] hover:bg-[--color-bg-hover]"
              : "border-accent/40 bg-accent-subtle text-accent-hover hover:bg-accent/20"
          }
        `}
      >
        <svg
          className="w-3.5 h-3.5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
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
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {open && createPortal(
        <div
          ref={dropdownRef}
          className="fixed w-56 bg-surface rounded-lg shadow-lg border border-[--color-border] z-[100] backdrop-blur-xl"
          style={dropdownStyle}
          onKeyDown={(e) => { if (e.key === "Escape") setOpen(false); }}
        >
          <div className="flex gap-2 px-3 py-2 border-b border-[--color-border]">
            <button
              onClick={handleSelectAll}
              className={`text-xs px-2 py-0.5 rounded transition-all duration-150 focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none ${
                isAllSelected
                  ? "bg-accent-subtle text-accent-hover"
                  : "text-accent hover:bg-accent-subtle"
              }`}
            >
              Select All
            </button>
            <button
              onClick={handleClearAll}
              className="text-xs text-[--color-text-muted] hover:text-[--color-text-primary] px-2 py-0.5 rounded hover:bg-[--color-bg-hover] transition-all duration-150 focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
            >
              Clear
            </button>
            <span className="ml-auto text-xs text-[--color-text-muted]">
              {selectedAssetClasses.length}/{availableAssetClasses.length}
            </span>
          </div>

          <div className="py-1">
            {availableAssetClasses.length === 0 ? (
              <p className="text-xs text-[--color-text-muted] text-center py-3">
                No asset classes found
              </p>
            ) : (
              availableAssetClasses.map((ac) => {
                const isChecked = activeSet.has(ac);
                return (
                  <label
                    key={ac}
                    className="flex items-center gap-2.5 px-3 py-2 hover:bg-[--color-bg-hover] cursor-pointer transition-colors"
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => handleToggle(ac)}
                      className="w-3.5 h-3.5 rounded border-[--color-border-strong] text-accent focus:ring-accent bg-elevated"
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
        </div>,
        document.body,
      )}
    </div>
  );
}
