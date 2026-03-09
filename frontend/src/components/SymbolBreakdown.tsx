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
import type { SymbolBreakdown as SymbolData } from "../api/client";

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
    return <p className="text-sm text-gray-400 text-center py-8">No data available</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={chartHeight}>
      <BarChart data={chartData} layout="vertical" margin={{ left: 60 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis type="number" tick={{ fontSize: 11 }} />
        <YAxis type="category" dataKey="symbol" tick={{ fontSize: 11 }} width={55} />
        <Tooltip
          formatter={(value: number) => [`$${value.toFixed(2)}`, "Net P&L"]}
        />
        <Bar dataKey="pnl" radius={[0, 4, 4, 0]}>
          {chartData.map((entry, index) => (
            <Cell
              key={`cell-${index}`}
              fill={entry.pnl >= 0 ? "#22c55e" : "#ef4444"}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
