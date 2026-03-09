"""Add asset_class dimension to daily_summaries materialized view.

Revision ID: 010
Revises: 009
Create Date: 2026-03-05
"""

from __future__ import annotations

from alembic import op

# revision identifiers
revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("DROP MATERIALIZED VIEW IF EXISTS daily_summaries;")

    op.execute(
        """
        CREATE MATERIALIZED VIEW daily_summaries AS
        SELECT
            COALESCE(g_agg.date, t_agg.date) AS date,
            COALESCE(g_agg.account_id, t_agg.account_id) AS account_id,
            COALESCE(g_agg.asset_class, t_agg.asset_class) AS asset_class,
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
                tg.asset_class,
                SUM(tg.realized_pnl) AS gross_pnl,
                COUNT(*) FILTER (WHERE tg.realized_pnl > 0) AS win_count,
                COUNT(*) FILTER (WHERE tg.realized_pnl <= 0) AS loss_count
            FROM trade_groups tg
            WHERE tg.status = 'closed'
            GROUP BY 1, 2, 3
        ) g_agg
        FULL OUTER JOIN (
            SELECT
                date_trunc('day', t.executed_at AT TIME ZONE 'UTC')::date AS date,
                t.account_id,
                t.asset_class,
                SUM(ABS(t.commission)) AS commissions,
                COUNT(*) AS trade_count
            FROM trades t
            GROUP BY 1, 2, 3
        ) t_agg
            ON g_agg.date = t_agg.date
           AND g_agg.account_id = t_agg.account_id
           AND g_agg.asset_class = t_agg.asset_class;
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX idx_daily_summaries_unique
        ON daily_summaries (date, account_id, asset_class)
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("DROP MATERIALIZED VIEW IF EXISTS daily_summaries;")

    op.execute(
        """
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
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX idx_daily_summaries_unique
        ON daily_summaries (date, account_id)
        """
    )
