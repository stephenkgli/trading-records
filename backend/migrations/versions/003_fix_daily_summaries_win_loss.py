"""Fix daily_summaries win/loss count — use trade_groups.realized_pnl.

The previous view computed win_count as sells where price*quantity > 0,
which is always true (both are positive), so win_count was always equal to
all sells and loss_count was always 0.

This migration rebuilds the view to derive win/loss from closed trade_groups.

Revision ID: 003
Revises: 002
Create Date: 2026-02-18
"""

from alembic import op

# revision identifiers
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 删除旧的物化视图
    op.execute("DROP MATERIALIZED VIEW IF EXISTS daily_summaries;")

    # 重建物化视图：win/loss 基于 trade_groups 的 realized_pnl
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
                    WHEN t.side = 'sell' THEN t.price * t.quantity
                    WHEN t.side = 'buy' THEN -t.price * t.quantity
                END) AS gross_pnl,
                SUM(CASE
                    WHEN t.side = 'sell' THEN t.price * t.quantity
                    WHEN t.side = 'buy' THEN -t.price * t.quantity
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


def downgrade() -> None:
    # 回退到旧的物化视图
    op.execute("DROP MATERIALIZED VIEW IF EXISTS daily_summaries;")

    op.execute("""
        CREATE MATERIALIZED VIEW daily_summaries AS
        SELECT
            date_trunc('day', t.executed_at AT TIME ZONE 'UTC')::date AS date,
            t.account_id,
            SUM(CASE
                WHEN t.side = 'sell' THEN t.price * t.quantity
                WHEN t.side = 'buy' THEN -t.price * t.quantity
            END) AS gross_pnl,
            SUM(CASE
                WHEN t.side = 'sell' THEN t.price * t.quantity
                WHEN t.side = 'buy' THEN -t.price * t.quantity
            END) - SUM(ABS(t.commission)) AS net_pnl,
            SUM(ABS(t.commission)) AS commissions,
            COUNT(*) AS trade_count,
            COUNT(*) FILTER (WHERE t.side = 'sell' AND t.price * t.quantity > 0) AS win_count,
            COUNT(*) FILTER (WHERE t.side = 'sell' AND t.price * t.quantity <= 0) AS loss_count
        FROM trades t
        GROUP BY 1, 2;
    """)

    op.execute(
        "CREATE UNIQUE INDEX ON daily_summaries (date, account_id);"
    )
