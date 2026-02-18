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
    return <p className="text-sm text-gray-400 text-center py-8">No data available</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={250}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip
          formatter={(value: number) => [`$${value.toFixed(2)}`, "Cumulative P&L"]}
        />
        <Line
          type="monotone"
          dataKey="pnl"
          stroke="#3b82f6"
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
