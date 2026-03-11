import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { fetchGroupDetail } from "../api/endpoints/groups";
import { formatDateTime } from "../utils/date";

const ROLE_COLORS: Record<string, string> = {
  entry: "bg-profit-subtle text-profit",
  add: "bg-accent-subtle text-accent-hover",
  trim: "bg-[--color-warning-subtle] text-[--color-warning]",
  exit: "bg-loss-subtle text-loss",
};

export default function GroupDetailPage() {
  const { id = "" } = useParams();
  const { data, isLoading, error } = useQuery({
    queryKey: ["groupDetail", id],
    queryFn: () => fetchGroupDetail(id),
    enabled: Boolean(id),
  });

  if (isLoading) {
    return (
      <div className="space-y-5">
        <div className="h-8 w-48 bg-elevated animate-pulse rounded" />
        <div className="bg-surface rounded-lg border border-[--color-border] p-6">
          <div className="grid grid-cols-3 lg:grid-cols-6 gap-5">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="h-14 bg-elevated animate-pulse rounded" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-3">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--color-loss)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="opacity-60">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
        <p className="text-loss text-sm">Error: {(error as Error).message}</p>
        <Link to="/groups" className="text-sm text-accent hover:text-accent-hover transition-colors">
          Back to Groups
        </Link>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-3">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-muted)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="opacity-50">
          <path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9z" />
          <polyline points="13 2 13 9 20 9" />
        </svg>
        <p className="text-[--color-text-muted] text-sm">Group not found.</p>
        <Link to="/groups" className="text-sm text-accent hover:text-accent-hover transition-colors">
          Back to Groups
        </Link>
      </div>
    );
  }

  const pnlNum = data.realized_pnl != null ? Number(data.realized_pnl) : null;

  return (
    <div className="stagger-in space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            to="/groups"
            className="w-8 h-8 flex items-center justify-center rounded-md text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-bg-hover] transition-colors"
            aria-label="Back to Groups"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 12L6 8l4-4"/></svg>
          </Link>
          <h1 className="font-display text-3xl text-[--color-text-primary] tracking-tight">{data.symbol}</h1>
          <span className={`inline-flex px-2.5 py-1 rounded-full text-xs font-medium ${
            data.direction === "long" ? "bg-profit-subtle text-profit" : "bg-loss-subtle text-loss"
          }`}>
            {data.direction}
          </span>
          <span className={`inline-flex px-2.5 py-1 rounded-full text-xs font-medium ${
            data.status === "open" ? "bg-accent-subtle text-accent-hover" : "bg-elevated text-[--color-text-secondary]"
          }`}>
            {data.status}
          </span>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className={`bg-surface rounded-lg border border-[--color-border] p-5 ${
          pnlNum !== null && pnlNum >= 0 ? "card-glow-profit" : pnlNum !== null ? "card-glow-loss" : ""
        }`}>
          <p className="text-[10px] font-medium text-[--color-text-muted] uppercase tracking-widest mb-2">Realized P&L</p>
          <p className={`text-2xl font-semibold font-mono ${
            pnlNum === null ? "text-[--color-text-muted]" : pnlNum >= 0 ? "text-profit" : "text-loss"
          }`} style={{ fontVariantNumeric: "tabular-nums" }}>
            {pnlNum !== null ? `${pnlNum >= 0 ? "+" : ""}$${pnlNum.toFixed(2)}` : "\u2014"}
          </p>
        </div>
        <div className="bg-surface rounded-lg border border-[--color-border] p-5">
          <p className="text-[10px] font-medium text-[--color-text-muted] uppercase tracking-widest mb-2">Opened</p>
          <p className="text-sm text-[--color-text-primary] font-mono">{formatDateTime(data.opened_at)}</p>
        </div>
        <div className="bg-surface rounded-lg border border-[--color-border] p-5">
          <p className="text-[10px] font-medium text-[--color-text-muted] uppercase tracking-widest mb-2">Closed</p>
          <p className="text-sm text-[--color-text-primary] font-mono">{formatDateTime(data.closed_at)}</p>
        </div>
      </div>

      {/* Legs */}
      <div className="bg-surface rounded-lg border border-[--color-border] p-5">
        <h2 className="text-[10px] font-medium text-[--color-text-muted] mb-4 uppercase tracking-widest">
          Trade Legs ({data.legs.length})
        </h2>
        {data.legs.length > 0 ? (
          <div className="space-y-2">
            {data.legs.map((leg, i) => (
              <div
                key={leg.id}
                className="flex items-center gap-3 px-4 py-2.5 rounded-md bg-elevated border border-[--color-border] hover:border-[--color-border-strong] transition-colors"
                style={{ animationDelay: `${i * 40}ms` }}
              >
                <span className="text-xs text-[--color-text-muted] font-mono w-6">{i + 1}</span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-medium uppercase ${ROLE_COLORS[leg.role] ?? "bg-elevated text-[--color-text-secondary]"}`}>
                  {leg.role}
                </span>
                <span className="text-[--color-text-secondary] font-mono text-xs flex-1">{leg.trade_id}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center py-8 gap-2">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-muted)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="opacity-40">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
              <line x1="3" y1="9" x2="21" y2="9" />
            </svg>
            <p className="text-[--color-text-muted] text-sm">No legs recorded</p>
          </div>
        )}
      </div>
    </div>
  );
}
