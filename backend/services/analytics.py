"""Analytics service — computes stats from trades and materialized views."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import SessionLocal

logger = structlog.get_logger(__name__)


def _sqlite_safe_params(db: Session, params: dict) -> dict:
    """Convert date/datetime bind params to strings for SQLite.

    Python 3.12 deprecates sqlite3's default date/datetime adapters.
    """
    bind = db.get_bind()
    if not bind or bind.dialect.name != "sqlite":
        return params

    converted: dict = {}
    for key, value in params.items():
        if isinstance(value, datetime):
            converted[key] = value.isoformat(sep=" ")
        elif isinstance(value, date):
            converted[key] = value.isoformat()
        else:
            converted[key] = value
    return converted


def refresh_daily_summaries(db: Session | None = None) -> None:
    """Refresh the daily_summaries materialized view concurrently."""
    own_session = db is None
    if own_session:
        db = SessionLocal()
    try:
        db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY daily_summaries"))
        if own_session:
            db.commit()
        logger.info("daily_summaries_refreshed")
    except Exception as e:
        logger.error("daily_summaries_refresh_error", error=str(e))
        # If CONCURRENTLY fails (e.g., no unique index populated), try without
        try:
            db.execute(text("REFRESH MATERIALIZED VIEW daily_summaries"))
            if own_session:
                db.commit()
            logger.info("daily_summaries_refreshed_non_concurrent")
        except Exception:
            if own_session:
                db.rollback()
            raise
    finally:
        if own_session:
            db.close()


def get_daily_summaries(
    db: Session,
    from_date: date | None = None,
    to_date: date | None = None,
    account_id: str | None = None,
) -> list[dict]:
    """Fetch daily summaries from materialized view."""
    return _get_daily_summaries_from_view_or_trades(
        db, from_date=from_date, to_date=to_date, account_id=account_id
    )


def _get_daily_summaries_from_view_or_trades(
    db: Session,
    from_date: date | None = None,
    to_date: date | None = None,
    account_id: str | None = None,
) -> list[dict]:
    """Fetch daily summaries, falling back to raw trades when the view is unavailable."""
    query = "SELECT * FROM daily_summaries WHERE 1=1"
    params: dict = {}

    if from_date:
        query += " AND date >= :from_date"
        params["from_date"] = from_date
    if to_date:
        query += " AND date <= :to_date"
        params["to_date"] = to_date
    if account_id:
        query += " AND account_id = :account_id"
        params["account_id"] = account_id

    query += " ORDER BY date ASC"
    params = _sqlite_safe_params(db, params)

    try:
        rows = db.execute(text(query), params).mappings().all()
        return [dict(row) for row in rows]
    except Exception:
        logger.warning("daily_summaries_view_unavailable_fallback_to_trades")
        return _compute_daily_summaries_from_trades(
            db, from_date=from_date, to_date=to_date, account_id=account_id
        )


def _compute_daily_summaries_from_trades(
    db: Session,
    from_date: date | None = None,
    to_date: date | None = None,
    account_id: str | None = None,
) -> list[dict]:
    """Compute daily summaries directly from trades for test/dev databases."""
    query = """
        SELECT
            DATE(t.executed_at) AS date,
            t.account_id AS account_id,
            SUM(CASE
                WHEN t.side = 'sell' THEN t.price * t.quantity
                WHEN t.side = 'buy' THEN -t.price * t.quantity
                ELSE 0
            END) AS gross_pnl,
            SUM(CASE
                WHEN t.side = 'sell' THEN t.price * t.quantity
                WHEN t.side = 'buy' THEN -t.price * t.quantity
                ELSE 0
            END) - SUM(ABS(t.commission)) AS net_pnl,
            SUM(ABS(t.commission)) AS commissions,
            COUNT(*) AS trade_count,
            0 AS win_count,
            0 AS loss_count
        FROM trades t
        WHERE 1=1
    """
    params: dict = {}

    if from_date:
        query += " AND DATE(t.executed_at) >= :from_date"
        params["from_date"] = from_date
    if to_date:
        query += " AND DATE(t.executed_at) <= :to_date"
        params["to_date"] = to_date
    if account_id:
        query += " AND t.account_id = :account_id"
        params["account_id"] = account_id

    query += " GROUP BY DATE(t.executed_at), t.account_id ORDER BY date ASC"
    params = _sqlite_safe_params(db, params)
    rows = db.execute(text(query), params).mappings().all()
    return [dict(row) for row in rows]


def get_calendar_data(
    db: Session,
    year: int,
    month: int,
    account_id: str | None = None,
) -> list[dict]:
    """Fetch calendar data for a specific month."""
    from_date = date(year, month, 1)
    if month == 12:
        to_date = date(year + 1, 1, 1)
    else:
        to_date = date(year, month + 1, 1)

    return get_daily_summaries(
        db, from_date=from_date, to_date=to_date, account_id=account_id
    )


def get_by_symbol(
    db: Session,
    from_date: date | None = None,
    to_date: date | None = None,
    account_id: str | None = None,
) -> list[dict]:
    """Get P&L breakdown by symbol."""
    query = """
        SELECT
            t.symbol,
            SUM(CASE
                WHEN t.side = 'sell' THEN t.price * t.quantity
                WHEN t.side = 'buy' THEN -t.price * t.quantity
            END) - SUM(ABS(t.commission)) AS net_pnl,
            COUNT(*) AS trade_count,
            COALESCE(g.win_count, 0) AS win_count,
            COALESCE(g.loss_count, 0) AS loss_count
        FROM trades t
        LEFT JOIN (
            SELECT
                tg.symbol,
                tg.account_id,
                SUM(CASE WHEN tg.realized_pnl > 0 THEN 1 ELSE 0 END) AS win_count,
                SUM(CASE WHEN tg.realized_pnl <= 0 THEN 1 ELSE 0 END) AS loss_count
            FROM trade_groups tg
            WHERE tg.status = 'closed'
            GROUP BY tg.symbol, tg.account_id
        ) g ON g.symbol = t.symbol AND g.account_id = t.account_id
        WHERE 1=1
    """
    params: dict = {}

    if from_date:
        query += " AND t.executed_at >= :from_date"
        params["from_date"] = datetime.combine(from_date, datetime.min.time())
    if to_date:
        query += " AND t.executed_at < :to_date"
        params["to_date"] = datetime.combine(to_date, datetime.min.time())
    if account_id:
        query += " AND t.account_id = :account_id"
        params["account_id"] = account_id

    query += " GROUP BY t.symbol ORDER BY net_pnl DESC"
    params = _sqlite_safe_params(db, params)

    rows = db.execute(text(query), params).mappings().all()
    return [dict(row) for row in rows]


def get_by_strategy(
    db: Session,
    from_date: date | None = None,
    to_date: date | None = None,
    account_id: str | None = None,
) -> list[dict]:
    """Get P&L breakdown by strategy tag."""
    query = """
        SELECT
            COALESCE(tg.strategy_tag, 'untagged') AS strategy_tag,
            SUM(COALESCE(tg.realized_pnl, 0)) AS net_pnl,
            COUNT(DISTINCT tgl.trade_id) AS trade_count,
            COUNT(DISTINCT tg.id) AS group_count
        FROM trade_groups tg
        JOIN trade_group_legs tgl ON tgl.trade_group_id = tg.id
        WHERE tg.status = 'closed'
    """
    params: dict = {}

    if account_id:
        query += " AND tg.account_id = :account_id"
        params["account_id"] = account_id

    query += " GROUP BY COALESCE(tg.strategy_tag, 'untagged') ORDER BY net_pnl DESC"

    rows = db.execute(text(query), params).mappings().all()
    return [dict(row) for row in rows]


def _get_win_loss_from_groups(
    db: Session,
    from_date: date | None = None,
    to_date: date | None = None,
    account_id: str | None = None,
) -> dict:
    """从 trade_groups 表获取 win/loss count 及 avg_win/avg_loss（基于已关闭 round-trip 的 realized_pnl）。"""
    query = """
        SELECT
            COALESCE(SUM(CASE WHEN tg.realized_pnl > 0 THEN 1 ELSE 0 END), 0) AS win_count,
            COALESCE(SUM(CASE WHEN tg.realized_pnl <= 0 THEN 1 ELSE 0 END), 0) AS loss_count,
            COALESCE(AVG(CASE WHEN tg.realized_pnl > 0 THEN tg.realized_pnl END), 0) AS avg_win,
            COALESCE(AVG(CASE WHEN tg.realized_pnl < 0 THEN tg.realized_pnl END), 0) AS avg_loss
        FROM trade_groups tg
        WHERE tg.status = 'closed'
    """
    params: dict = {}

    if from_date:
        query += " AND DATE(tg.closed_at) >= :from_date"
        params["from_date"] = from_date
    if to_date:
        query += " AND DATE(tg.closed_at) <= :to_date"
        params["to_date"] = to_date
    if account_id:
        query += " AND tg.account_id = :account_id"
        params["account_id"] = account_id

    params = _sqlite_safe_params(db, params)

    try:
        row = db.execute(text(query), params).mappings().first()
        if row:
            return {
                "win_count": int(row["win_count"]),
                "loss_count": int(row["loss_count"]),
                "avg_win": Decimal(str(row["avg_win"])),
                "avg_loss": Decimal(str(row["avg_loss"])),
            }
    except Exception:
        logger.warning("trade_groups_win_loss_query_failed")

    return {"win_count": 0, "loss_count": 0, "avg_win": Decimal("0"), "avg_loss": Decimal("0")}


def get_performance_metrics(
    db: Session,
    from_date: date | None = None,
    to_date: date | None = None,
    account_id: str | None = None,
) -> dict:
    """Compute overall performance metrics."""
    rows = _get_daily_summaries_from_view_or_trades(
        db, from_date=from_date, to_date=to_date, account_id=account_id
    )

    if not rows:
        return {
            "total_pnl": Decimal("0"),
            "total_commissions": Decimal("0"),
            "net_pnl": Decimal("0"),
            "total_trades": 0,
            "win_count": 0,
            "loss_count": 0,
            "win_rate": 0.0,
            "avg_win": Decimal("0"),
            "avg_loss": Decimal("0"),
            "profit_factor": None,
            "expectancy": Decimal("0"),
            "trading_days": 0,
        }

    total_pnl = sum(Decimal(str(r["gross_pnl"] or 0)) for r in rows)
    total_commissions = sum(Decimal(str(r["commissions"] or 0)) for r in rows)
    net_pnl = total_pnl - total_commissions
    total_trades = sum(int(r["trade_count"] or 0) for r in rows)
    trading_days = len(rows)

    # 从 trade_groups 表获取正确的 win/loss count 和 avg_win/avg_loss
    # （基于已关闭的 round-trip realized_pnl，而非日汇总数据）
    wl = _get_win_loss_from_groups(
        db, from_date=from_date, to_date=to_date, account_id=account_id
    )
    win_count = wl["win_count"]
    loss_count = wl["loss_count"]
    avg_win = wl["avg_win"]
    avg_loss = wl["avg_loss"]

    total_decided = win_count + loss_count
    win_rate = (win_count / total_decided * 100) if total_decided > 0 else 0.0

    # Profit factor: 总盈利 / 总亏损（基于每笔交易，而非日汇总）
    gross_wins = avg_win * win_count
    gross_losses = abs(avg_loss * loss_count)
    profit_factor = float(gross_wins / gross_losses) if gross_losses > 0 else None

    # Expectancy
    expectancy = net_pnl / total_trades if total_trades > 0 else Decimal("0")

    return {
        "total_pnl": total_pnl,
        "total_commissions": total_commissions,
        "net_pnl": net_pnl,
        "total_trades": total_trades,
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate": round(win_rate, 2),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": round(profit_factor, 2) if profit_factor is not None else None,
        "expectancy": expectancy,
        "trading_days": trading_days,
    }
