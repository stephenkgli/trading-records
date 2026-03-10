import { useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { DailySummary } from "../api/client";

interface EquityCurveProps {
  data: DailySummary[];
}

export default function EquityCurve({ data }: EquityCurveProps) {
  const chartData = useMemo(() => {
    let cumulative = 0;
    return data.map((d) => {
      cumulative += Number(d.net_pnl || 0);
      return {
        date: d.date,
        pnl: cumulative,
      };
    });
  }, [data]);

  if (chartData.length === 0) {
    return <p className="text-sm text-[--color-text-muted] text-center py-8">No data available</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={250}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
        <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#8888a4" }} stroke="rgba(255,255,255,0.08)" />
        <YAxis tick={{ fontSize: 11, fill: "#8888a4" }} stroke="rgba(255,255,255,0.08)" />
        <Tooltip
          contentStyle={{
            backgroundColor: "#252540",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: "8px",
            color: "#e4e4f0",
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: 12,
          }}
          formatter={(value: number) => [new Intl.NumberFormat(undefined, { style: "currency", currency: "USD" }).format(value), "Cumulative P&L"]}
        />
        <Line
          type="monotone"
          dataKey="pnl"
          stroke="var(--color-accent)"
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
