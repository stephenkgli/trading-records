"""Fix daily_summaries to use trade_groups.realized_pnl instead of raw buy/sell amounts.

The previous daily_summaries materialized view computed gross_pnl as
``SUM(sell_amount - buy_amount)`` which is NOT real P&L — it is cash flow.
When trades span multiple days (e.g., buy on day 1, sell on day 2), the
buy day shows a huge negative number and the sell day a huge positive.

This migration rebuilds the view so that:
- gross_pnl comes from ``trade_groups.realized_pnl`` (closed round-trips),
  bucketed by ``closed_at`` date.
- commissions and trade_count still come from the trades table.
- win_count / loss_count come from trade_groups as before.

Revision ID: 005
Revises: 004
Create Date: 2026-02-18
"""

from alembic import op

# revision identifiers
revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS daily_summaries;")

    op.execute("""
        CREATE MATERIALIZED VIEW daily_summaries AS
        SELECT
            COALESCE(g_agg.date, t_agg.date) AS date,
            COALESCE(g_agg.account_id, t_agg.account_id) AS account_id,
            COALESCE(g_agg.gross_pnl, 0) AS gross_pnl,
            COALESCE(g_agg.gross_pnl, 0) - COALESCE(t_agg.commissions, 0) AS net_pnl,
            COALESCE(t_agg.commissions, 0) AS commissions,
            COALESCE(t_agg.trade_count, 0) AS trade_count,
            COALESCE(g_agg.win_count, 0) AS win_count,
            COALESCE(g_agg.loss_count, 0) AS loss_count
        FROM (
            SELECT
                date_trunc('day', tg.closed_at AT TIME ZONE 'UTC')::date AS date,
                tg.account_id,
                SUM(tg.realized_pnl) AS gross_pnl,
                COUNT(*) FILTER (WHERE tg.realized_pnl > 0) AS win_count,
                COUNT(*) FILTER (WHERE tg.realized_pnl <= 0) AS loss_count
            FROM trade_groups tg
            WHERE tg.status = 'closed'
            GROUP BY 1, 2
        ) g_agg
        FULL OUTER JOIN (
            SELECT
                date_trunc('day', t.executed_at AT TIME ZONE 'UTC')::date AS date,
                t.account_id,
                SUM(ABS(t.commission)) AS commissions,
                COUNT(*) AS trade_count
            FROM trades t
            GROUP BY 1, 2
        ) t_agg ON g_agg.date = t_agg.date AND g_agg.account_id = t_agg.account_id;
    """)

    op.execute(
        "CREATE UNIQUE INDEX ON daily_summaries (date, account_id);"
    )


def downgrade() -> None:
    # Restore old view with sell-buy amount P&L calculation
    op.execute("DROP MATERIALIZED VIEW IF EXISTS daily_summaries;")

    op.execute("""
        CREATE MATERIALIZED VIEW daily_summaries AS
        SELECT
            COALESCE(t_agg.date, g_agg.date) AS date,
            COALESCE(t_agg.account_id, g_agg.account_id) AS account_id,
            COALESCE(t_agg.gross_pnl, 0) AS gross_pnl,
            COALESCE(t_agg.net_pnl, 0) AS net_pnl,
            COALESCE(t_agg.commissions, 0) AS commissions,
            COALESCE(t_agg.trade_count, 0) AS trade_count,
            COALESCE(g_agg.win_count, 0) AS win_count,
            COALESCE(g_agg.loss_count, 0) AS loss_count
        FROM (
            SELECT
                date_trunc('day', t.executed_at AT TIME ZONE 'UTC')::date AS date,
                t.account_id,
                SUM(CASE
                    WHEN t.side = 'sell' THEN t.price * t.quantity * t.multiplier
                    WHEN t.side = 'buy' THEN -t.price * t.quantity * t.multiplier
                END) AS gross_pnl,
                SUM(CASE
                    WHEN t.side = 'sell' THEN t.price * t.quantity * t.multiplier
                    WHEN t.side = 'buy' THEN -t.price * t.quantity * t.multiplier
                END) - SUM(ABS(t.commission)) AS net_pnl,
                SUM(ABS(t.commission)) AS commissions,
                COUNT(*) AS trade_count
            FROM trades t
            GROUP BY 1, 2
        ) t_agg
        FULL OUTER JOIN (
            SELECT
                date_trunc('day', tg.closed_at AT TIME ZONE 'UTC')::date AS date,
                tg.account_id,
                COUNT(*) FILTER (WHERE tg.realized_pnl > 0) AS win_count,
                COUNT(*) FILTER (WHERE tg.realized_pnl <= 0) AS loss_count
            FROM trade_groups tg
            WHERE tg.status = 'closed'
            GROUP BY 1, 2
        ) g_agg ON t_agg.date = g_agg.date AND t_agg.account_id = g_agg.account_id;
    """)

    op.execute(
        "CREATE UNIQUE INDEX ON daily_summaries (date, account_id);"
    )
