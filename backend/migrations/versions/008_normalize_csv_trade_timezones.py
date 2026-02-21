"""Normalize historical CSV trade timestamps to UTC by broker timezone.

Revision ID: 008
Revises: 007
Create Date: 2026-02-21
"""

from __future__ import annotations

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def _recompute_trade_group_boundaries() -> None:
    """Re-align group open/close timestamps from leg trade timestamps."""
    op.execute(
        """
        UPDATE trade_groups AS tg
        SET
            opened_at = agg.min_executed_at,
            closed_at = CASE
                WHEN tg.status = 'closed' THEN agg.max_executed_at
                ELSE NULL
            END
        FROM (
            SELECT
                tgl.trade_group_id,
                MIN(t.executed_at) AS min_executed_at,
                MAX(t.executed_at) AS max_executed_at
            FROM trade_group_legs AS tgl
            JOIN trades AS t ON t.id = tgl.trade_id
            GROUP BY tgl.trade_group_id
        ) AS agg
        WHERE tg.id = agg.trade_group_id
        """
    )


def _refresh_daily_summaries_mv() -> None:
    """Refresh daily_summaries materialized view if present."""
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_matviews
                WHERE matviewname = 'daily_summaries'
            ) THEN
                REFRESH MATERIALIZED VIEW daily_summaries;
            END IF;
        END $$;
        """
    )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    # Historical behavior treated broker-local naive timestamps as UTC.
    # Correct by reinterpreting stored wall-clock as source timezone and
    # converting to real UTC.
    op.execute(
        """
        UPDATE trades
        SET executed_at = ((executed_at AT TIME ZONE 'UTC') AT TIME ZONE 'America/New_York')
        WHERE broker = 'ibkr'
        """
    )
    op.execute(
        """
        UPDATE trades
        SET executed_at = ((executed_at AT TIME ZONE 'UTC') AT TIME ZONE 'Asia/Shanghai')
        WHERE broker = 'tradovate'
        """
    )

    _recompute_trade_group_boundaries()
    _refresh_daily_summaries_mv()


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    # Revert to previous (incorrect) behavior for rollback compatibility.
    op.execute(
        """
        UPDATE trades
        SET executed_at = ((executed_at AT TIME ZONE 'America/New_York') AT TIME ZONE 'UTC')
        WHERE broker = 'ibkr'
        """
    )
    op.execute(
        """
        UPDATE trades
        SET executed_at = ((executed_at AT TIME ZONE 'Asia/Shanghai') AT TIME ZONE 'UTC')
        WHERE broker = 'tradovate'
        """
    )

    _recompute_trade_group_boundaries()
    _refresh_daily_summaries_mv()
