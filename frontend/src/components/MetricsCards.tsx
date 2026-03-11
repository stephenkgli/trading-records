import { useMemo } from "react";
import type { PerformanceMetrics } from "../api/types";

interface MetricsCardsProps {
  metrics: PerformanceMetrics;
}

export default function MetricsCards({ metrics }: MetricsCardsProps) {
  const cards = useMemo(
    () => [
      {
        label: "Net P&L",
        value: new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(metrics.net_pnl)),
        sentiment: Number(metrics.net_pnl) >= 0 ? "profit" : "loss",
        hero: true,
      },
      {
        label: "Win Rate",
        value: `${metrics.win_rate}%`,
        sentiment: metrics.win_rate >= 50 ? "profit" : "loss",
        hero: false,
      },
      {
        label: "Win/Loss Ratio",
        value: metrics.win_loss_ratio !== null ? String(metrics.win_loss_ratio) : "N/A",
        sentiment:
          metrics.win_loss_ratio !== null && metrics.win_loss_ratio >= 1
            ? "profit"
            : "loss",
        hero: false,
      },
      {
        label: "Total Trades",
        value: new Intl.NumberFormat().format(metrics.total_trades),
        sentiment: "neutral" as const,
        hero: false,
      },
    ],
    [metrics.net_pnl, metrics.win_rate, metrics.win_loss_ratio, metrics.total_trades],
  );

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {cards.map((card, i) => {
        let colorClass = "text-[--color-text-primary]";
        if (card.sentiment === "profit") colorClass = "text-profit";
        else if (card.sentiment === "loss") colorClass = "text-loss";

        let glowClass = "";
        if (card.hero && card.sentiment === "profit") glowClass = "card-glow-profit";
        else if (card.hero && card.sentiment === "loss") glowClass = "card-glow-loss";

        return (
          <div
            key={card.label}
            className={`bg-surface rounded-lg border border-[--color-border] p-4 transition-all duration-300 hover:border-[--color-border-strong] hover:bg-elevated ${glowClass} ${card.hero ? "lg:row-span-1" : ""}`}
            style={{ animationDelay: `${i * 60}ms` }}
          >
            <p className="text-[10px] font-medium text-[--color-text-muted] uppercase tracking-widest mb-2">{card.label}</p>
            <p
              className={`${card.hero ? "text-3xl font-display" : "text-xl"} font-semibold ${colorClass} font-mono leading-tight`}
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {card.value}
            </p>
            {card.hero && (
              <div className={`mt-2 h-0.5 w-12 rounded-full ${card.sentiment === "profit" ? "bg-profit/40" : "bg-loss/40"}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}
