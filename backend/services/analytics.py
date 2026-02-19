"""Analytics service — computes stats from trades and materialized views."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.utils.symbol import normalize_futures_symbol

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
    """Compute daily summaries from trade_groups (realized_pnl) for test/dev databases.

    P&L is based on closed round-trip realized_pnl from trade_groups, not raw
    buy/sell amounts.  Commissions come from trades linked via trade_group_legs.
    """
    query = """
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
                DATE(tg.closed_at) AS date,
                tg.account_id,
                SUM(tg.realized_pnl) AS gross_pnl,
                SUM(CASE WHEN tg.realized_pnl > 0 THEN 1 ELSE 0 END) AS win_count,
                SUM(CASE WHEN tg.realized_pnl <= 0 THEN 1 ELSE 0 END) AS loss_count
            FROM trade_groups tg
            WHERE tg.status = 'closed'
            GROUP BY DATE(tg.closed_at), tg.account_id
        ) g_agg
        FULL OUTER JOIN (
            SELECT
                DATE(t.executed_at) AS date,
                t.account_id,
                SUM(ABS(t.commission)) AS commissions,
                COUNT(*) AS trade_count
            FROM trades t
            GROUP BY DATE(t.executed_at), t.account_id
        ) t_agg ON g_agg.date = t_agg.date AND g_agg.account_id = t_agg.account_id
        WHERE 1=1
    """
    params: dict = {}

    if from_date:
        query += " AND COALESCE(g_agg.date, t_agg.date) >= :from_date"
        params["from_date"] = from_date
    if to_date:
        query += " AND COALESCE(g_agg.date, t_agg.date) <= :to_date"
        params["to_date"] = to_date
    if account_id:
        query += " AND COALESCE(g_agg.account_id, t_agg.account_id) = :account_id"
        params["account_id"] = account_id

    query += " ORDER BY date ASC"
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
    """Get P&L breakdown by symbol using trade_groups realized_pnl.

    期货品种会被归一化（如 MESU5, MESH5 -> MES），然后按归一化后的名称聚合。
    """
    query = """
        SELECT
            tg.symbol,
            tg.asset_class,
            COALESCE(SUM(tg.realized_pnl), 0) AS net_pnl,
            COALESCE(trade_counts.cnt, 0) AS trade_count,
            SUM(CASE WHEN tg.realized_pnl > 0 THEN 1 ELSE 0 END) AS win_count,
            SUM(CASE WHEN tg.realized_pnl <= 0 THEN 1 ELSE 0 END) AS loss_count
        FROM trade_groups tg
        LEFT JOIN (
            SELECT t.symbol, t.account_id, COUNT(*) AS cnt
            FROM trades t
            WHERE 1=1
    """
    params: dict = {}
    trade_filter = ""

    if from_date:
        trade_filter += " AND t.executed_at >= :from_date"
        params["from_date"] = datetime.combine(from_date, datetime.min.time())
    if to_date:
        trade_filter += " AND t.executed_at < :to_date"
        params["to_date"] = datetime.combine(to_date, datetime.min.time())
    if account_id:
        trade_filter += " AND t.account_id = :account_id"
        params["account_id"] = account_id

    query += trade_filter
    query += """
            GROUP BY t.symbol, t.account_id
        ) trade_counts ON trade_counts.symbol = tg.symbol AND trade_counts.account_id = tg.account_id
        WHERE tg.status = 'closed'
    """

    if from_date:
        query += " AND DATE(tg.closed_at) >= :tg_from_date"
        params["tg_from_date"] = from_date
    if to_date:
        query += " AND DATE(tg.closed_at) <= :tg_to_date"
        params["tg_to_date"] = to_date
    if account_id:
        query += " AND tg.account_id = :account_id"

    query += " GROUP BY tg.symbol, tg.asset_class, trade_counts.cnt ORDER BY net_pnl DESC"
    params = _sqlite_safe_params(db, params)

    rows = db.execute(text(query), params).mappings().all()

    # 在 Python 层面按归一化后的 symbol 重新聚合
    aggregated: dict[str, dict] = defaultdict(lambda: {
        "symbol": "",
        "net_pnl": Decimal("0"),
        "trade_count": 0,
        "win_count": 0,
        "loss_count": 0,
    })
    for row in rows:
        normalized = normalize_futures_symbol(row["symbol"], row["asset_class"])
        entry = aggregated[normalized]
        entry["symbol"] = normalized
        entry["net_pnl"] += Decimal(str(row["net_pnl"]))
        entry["trade_count"] += int(row["trade_count"])
        entry["win_count"] += int(row["win_count"])
        entry["loss_count"] += int(row["loss_count"])

    # 按 net_pnl 降序排序
    result = sorted(aggregated.values(), key=lambda x: x["net_pnl"], reverse=True)
    return result


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
    """Compute overall performance metrics.

    P&L is derived from trade_groups.realized_pnl (closed round-trips),
    not from raw buy/sell amounts.
    """
    # 从 trade_groups 表获取正确的 win/loss count 和 avg_win/avg_loss
    wl = _get_win_loss_from_groups(
        db, from_date=from_date, to_date=to_date, account_id=account_id
    )
    win_count = wl["win_count"]
    loss_count = wl["loss_count"]
    avg_win = wl["avg_win"]
    avg_loss = wl["avg_loss"]

    # 从 trade_groups 计算总盈亏
    pnl_query = """
        SELECT
            COALESCE(SUM(tg.realized_pnl), 0) AS total_pnl
        FROM trade_groups tg
        WHERE tg.status = 'closed'
    """
    pnl_params: dict = {}
    if from_date:
        pnl_query += " AND DATE(tg.closed_at) >= :from_date"
        pnl_params["from_date"] = from_date
    if to_date:
        pnl_query += " AND DATE(tg.closed_at) <= :to_date"
        pnl_params["to_date"] = to_date
    if account_id:
        pnl_query += " AND tg.account_id = :account_id"
        pnl_params["account_id"] = account_id

    pnl_params = _sqlite_safe_params(db, pnl_params)
    pnl_row = db.execute(text(pnl_query), pnl_params).mappings().first()
    total_pnl = Decimal(str(pnl_row["total_pnl"])) if pnl_row else Decimal("0")

    # 从 trades 计算佣金和交易数
    comm_query = """
        SELECT
            COALESCE(SUM(ABS(t.commission)), 0) AS total_commissions,
            COUNT(*) AS total_trades,
            COUNT(DISTINCT DATE(t.executed_at)) AS trading_days
        FROM trades t
        WHERE 1=1
    """
    comm_params: dict = {}
    if from_date:
        comm_query += " AND DATE(t.executed_at) >= :from_date"
        comm_params["from_date"] = from_date
    if to_date:
        comm_query += " AND DATE(t.executed_at) <= :to_date"
        comm_params["to_date"] = to_date
    if account_id:
        comm_query += " AND t.account_id = :account_id"
        comm_params["account_id"] = account_id

    comm_params = _sqlite_safe_params(db, comm_params)
    comm_row = db.execute(text(comm_query), comm_params).mappings().first()

    total_commissions = Decimal(str(comm_row["total_commissions"])) if comm_row else Decimal("0")
    total_trades = int(comm_row["total_trades"]) if comm_row else 0
    trading_days = int(comm_row["trading_days"]) if comm_row else 0

    net_pnl = total_pnl - total_commissions

    total_decided = win_count + loss_count
    win_rate = (win_count / total_decided * 100) if total_decided > 0 else 0.0

    # 盈亏比: 平均盈利 / |平均亏损|
    abs_avg_loss = abs(avg_loss)
    win_loss_ratio = float(avg_win / abs_avg_loss) if abs_avg_loss > 0 else None

    # Expectancy: 基于每笔 round-trip 的平均期望值
    # E = avg_win × win_rate + avg_loss × (1 - win_rate)
    if total_decided > 0:
        wr = Decimal(str(win_count)) / Decimal(str(total_decided))
        expectancy = avg_win * wr + avg_loss * (Decimal("1") - wr)
    else:
        expectancy = Decimal("0")

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
        "win_loss_ratio": round(win_loss_ratio, 2) if win_loss_ratio is not None else None,
        "expectancy": expectancy,
        "trading_days": trading_days,
    }
