import type { PerformanceMetrics } from "../api/client";

interface MetricsCardsProps {
  metrics: PerformanceMetrics;
}

export default function MetricsCards({ metrics }: MetricsCardsProps) {
  const cards = [
    {
      label: "Net P&L",
      value: `$${Number(metrics.net_pnl).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
      color: Number(metrics.net_pnl) >= 0 ? "text-green-600" : "text-red-600",
    },
    {
      label: "Win Rate",
      value: `${metrics.win_rate}%`,
      color: metrics.win_rate >= 50 ? "text-green-600" : "text-red-600",
    },
    {
label: "Win/Loss Ratio",
      value: metrics.win_loss_ratio !== null ? String(metrics.win_loss_ratio) : "N/A",
      color: metrics.win_loss_ratio !== null && metrics.win_loss_ratio >= 1 ? "text-green-600" : "text-red-600",
    },
    {
      label: "Total Trades",
      value: String(metrics.total_trades),
      color: "text-gray-900",
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card) => (
        <div key={card.label} className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">{card.label}</p>
          <p className={`text-2xl font-bold ${card.color}`}>{card.value}</p>
        </div>
      ))}
    </div>
  );
}
