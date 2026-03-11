import { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { SymbolBreakdown as SymbolData } from "../api/types";

interface SymbolBreakdownProps {
  data: SymbolData[];
}

export default function SymbolBreakdown({ data }: SymbolBreakdownProps) {
  const { chartData, chartHeight } = useMemo(
    () => {
      const items = data.map((d) => ({
        symbol: d.symbol,
        pnl: Number(d.net_pnl),
        trades: d.trade_count,
      }));
      return { chartData: items, chartHeight: Math.max(200, items.length * 35) };
    },
    [data],
  );

  if (chartData.length === 0) {
    return <p className="text-sm text-[--color-text-muted] text-center py-8">No data available</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={chartHeight}>
      <BarChart data={chartData} layout="vertical" margin={{ left: 60 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
        <XAxis type="number" tick={{ fontSize: 11, fill: "var(--color-text-secondary)" }} stroke="var(--color-border)" />
        <YAxis type="category" dataKey="symbol" tick={{ fontSize: 11, fill: "var(--color-text-secondary)" }} width={55} stroke="var(--color-border)" />
        <Tooltip
          contentStyle={{
            backgroundColor: "var(--color-bg-elevated)",
            border: "1px solid var(--color-border-strong)",
            borderRadius: "8px",
            color: "var(--color-text-primary)",
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: 12,
          }}
          formatter={(value: number) => [new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value), "Net P&L"]}
        />
        <Bar dataKey="pnl" radius={[0, 4, 4, 0]}>
          {chartData.map((entry, index) => (
            <Cell
              key={`cell-${index}`}
              fill={entry.pnl >= 0 ? "var(--color-profit)" : "var(--color-loss)"}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
