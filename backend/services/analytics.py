"""Analytics service — computes stats from trades and materialized views."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
import time

import structlog
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.utils.db import session_scope
from backend.utils.symbol import normalize_futures_symbol

logger = structlog.get_logger(__name__)

# Sentinel indicating the caller should return an empty result immediately.
_EMPTY = object()


def _check_empty_asset_classes(asset_classes: list[str] | None) -> object | None:
    """Return ``_EMPTY`` if *asset_classes* is an explicit empty list.

    An empty list ``[]`` means the user deliberately selected no asset types,
    so the caller should short-circuit to an empty/zero-value result.
    ``None`` means the parameter was omitted (no filter).
    """
    if asset_classes is not None and len(asset_classes) == 0:
        return _EMPTY
    return None


def _build_asset_class_in_clause(
    asset_classes: list[str],
    prefix: str = "ac",
) -> tuple[str, dict]:
    """Build a SQL ``IN (...)`` placeholder fragment and matching params dict.

    Args:
        asset_classes: Non-empty list of asset class strings.
        prefix: Bind-parameter name prefix (must be unique per query context).

    Returns:
        Tuple of ``(placeholders_sql, params_dict)``
        e.g. ``(":ac_0, :ac_1", {"ac_0": "stock", "ac_1": "future"})``.
    """
    placeholders = ", ".join(f":{prefix}_{i}" for i in range(len(asset_classes)))
    params = {f"{prefix}_{i}": ac for i, ac in enumerate(asset_classes)}
    return placeholders, params


def _append_date_account_filters(
    query: str,
    params: dict,
    *,
    date_col: str,
    account_col: str,
    from_date: date | None = None,
    to_date: date | None = None,
    account_id: str | None = None,
) -> str:
    """Append date-range and account_id WHERE clauses to a raw SQL query.

    Mutates *params* in-place and returns the updated query string.

    Args:
        query: SQL query string being built.
        params: Bind-parameter dict (mutated in-place).
        date_col: SQL expression for the date column.
        account_col: SQL expression for the account column.
        from_date: Optional inclusive lower date bound.
        to_date: Optional inclusive upper date bound.
        account_id: Optional account ID equality filter.
    """
    if from_date:
        query += f" AND {date_col} >= :from_date"
        params["from_date"] = from_date
    if to_date:
        query += f" AND {date_col} <= :to_date"
        params["to_date"] = to_date
    if account_id:
        query += f" AND {account_col} = :account_id"
        params["account_id"] = account_id
    return query


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
    """Refresh the daily_summaries materialized view with safety guards."""
    with session_scope(db) as session:
        bind = session.get_bind()
        if not bind or bind.dialect.name != "postgresql":
            return

        start = time.perf_counter()
        has_unique_index = session.execute(
            text(
                """
                SELECT 1
                FROM pg_index i
                JOIN pg_class c ON c.oid = i.indrelid
                WHERE c.relname = 'daily_summaries'
                  AND i.indisunique
                LIMIT 1
                """
            )
        ).first() is not None

        if has_unique_index:
            try:
                session.execute(text("SET LOCAL statement_timeout = '60000'"))
                session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY daily_summaries"))
                logger.info(
                    "daily_summaries_refreshed",
                    mode="concurrent",
                    duration_ms=int((time.perf_counter() - start) * 1000),
                )
                return
            except (SQLAlchemyError, RuntimeError) as exc:
                logger.warning(
                    "daily_summaries_concurrent_refresh_failed",
                    error=str(exc),
                )

        try:
            session.execute(text("SET LOCAL statement_timeout = '120000'"))
            session.execute(text("REFRESH MATERIALIZED VIEW daily_summaries"))
            logger.info(
                "daily_summaries_refreshed",
                mode="exclusive",
                duration_ms=int((time.perf_counter() - start) * 1000),
            )
        except SQLAlchemyError as exc:
            logger.error(
                "daily_summaries_refresh_error",
                error=str(exc),
                mode="exclusive",
            )
            raise


def get_daily_summaries(
    db: Session,
    from_date: date | None = None,
    to_date: date | None = None,
    account_id: str | None = None,
    asset_classes: list[str] | None = None,
) -> list[dict]:
    """Fetch daily summaries from materialized view."""
    return _get_daily_summaries_from_view_or_trades(
        db, from_date=from_date, to_date=to_date, account_id=account_id,
        asset_classes=asset_classes,
    )


def _get_daily_summaries_from_view_or_trades(
    db: Session,
    from_date: date | None = None,
    to_date: date | None = None,
    account_id: str | None = None,
    asset_classes: list[str] | None = None,
) -> list[dict]:
    """Fetch daily summaries, falling back to computed summaries when needed."""

    if _check_empty_asset_classes(asset_classes) is _EMPTY:
        return []

    query = """
        SELECT
            date,
            account_id,
            SUM(gross_pnl) AS gross_pnl,
            SUM(net_pnl) AS net_pnl,
            SUM(commissions) AS commissions,
            SUM(trade_count) AS trade_count,
            SUM(win_count) AS win_count,
            SUM(loss_count) AS loss_count
        FROM daily_summaries
        WHERE 1=1
    """
    params: dict = {}

    query = _append_date_account_filters(
        query,
        params,
        date_col="date",
        account_col="account_id",
        from_date=from_date,
        to_date=to_date,
        account_id=account_id,
    )
    if asset_classes:
        ac_sql, ac_params = _build_asset_class_in_clause(asset_classes, prefix="mv_ac")
        query += f" AND asset_class IN ({ac_sql})"
        params.update(ac_params)

    query += " GROUP BY date, account_id ORDER BY date ASC"
    params = _sqlite_safe_params(db, params)

    try:
        rows = db.execute(text(query), params).mappings().all()
        return [dict(row) for row in rows]
    except SQLAlchemyError:
        logger.warning("daily_summaries_view_unavailable_fallback_to_trades")
        return _compute_daily_summaries_from_trades(
            db,
            from_date=from_date,
            to_date=to_date,
            account_id=account_id,
            asset_classes=asset_classes,
        )


def _compute_daily_summaries_from_trades(
    db: Session,
    from_date: date | None = None,
    to_date: date | None = None,
    account_id: str | None = None,
    asset_classes: list[str] | None = None,
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
            WHERE 1=1
            GROUP BY DATE(t.executed_at), t.account_id
        ) t_agg ON g_agg.date = t_agg.date AND g_agg.account_id = t_agg.account_id
        WHERE 1=1
    """
    params: dict = {}

    # 如果指定了资产类型过滤，使用专门的过滤查询
    if asset_classes:
        return _compute_daily_summaries_filtered_by_asset_classes(
            db, asset_classes=asset_classes, from_date=from_date, to_date=to_date,
            account_id=account_id,
        )

    query = _append_date_account_filters(
        query, params,
        date_col="COALESCE(g_agg.date, t_agg.date)",
        account_col="COALESCE(g_agg.account_id, t_agg.account_id)",
        from_date=from_date, to_date=to_date, account_id=account_id,
    )

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
    asset_classes: list[str] | None = None,
) -> list[dict]:
    """Get P&L breakdown by symbol using trade_groups realized_pnl.

    期货品种会被归一化（如 MESU5, MESH5 -> MES），然后按归一化后的名称聚合。
    """
    if _check_empty_asset_classes(asset_classes) is _EMPTY:
        return []

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
    if asset_classes:
        ac_sql, ac_params = _build_asset_class_in_clause(asset_classes)
        query += f" AND tg.asset_class IN ({ac_sql})"
        params.update(ac_params)

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

    # 如果指定了资产类型过滤，在查询结果基础上无需额外过滤（SQL 已处理）

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


def _compute_daily_summaries_filtered_by_asset_classes(
    db: Session,
    asset_classes: list[str],
    from_date: date | None = None,
    to_date: date | None = None,
    account_id: str | None = None,
) -> list[dict]:
    """按指定资产类型过滤计算每日汇总。

    asset_class 可以直接在 SQL 层过滤，无需 Python 层归一化。
    """
    ac_sql, params = _build_asset_class_in_clause(asset_classes)

    query = f"""
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
              AND tg.asset_class IN ({ac_sql})
            GROUP BY DATE(tg.closed_at), tg.account_id
        ) g_agg
        FULL OUTER JOIN (
            SELECT
                DATE(t.executed_at) AS date,
                t.account_id,
                SUM(ABS(t.commission)) AS commissions,
                COUNT(*) AS trade_count
            FROM trades t
            WHERE t.asset_class IN ({ac_sql})
            GROUP BY DATE(t.executed_at), t.account_id
        ) t_agg ON g_agg.date = t_agg.date AND g_agg.account_id = t_agg.account_id
        WHERE 1=1
    """
    query = _append_date_account_filters(
        query, params,
        date_col="COALESCE(g_agg.date, t_agg.date)",
        account_col="COALESCE(g_agg.account_id, t_agg.account_id)",
        from_date=from_date, to_date=to_date, account_id=account_id,
    )

    query += " ORDER BY date ASC"
    params = _sqlite_safe_params(db, params)
    rows = db.execute(text(query), params).mappings().all()
    return [dict(row) for row in rows]


def _get_win_loss_from_groups(
    db: Session,
    from_date: date | None = None,
    to_date: date | None = None,
    account_id: str | None = None,
    asset_classes: list[str] | None = None,
) -> dict:
    """从 trade_groups 表获取 win/loss count 及 avg_win/avg_loss（基于已关闭 round-trip 的 realized_pnl）。"""
    if _check_empty_asset_classes(asset_classes) is _EMPTY:
        return {"win_count": 0, "loss_count": 0, "avg_win": Decimal("0"), "avg_loss": Decimal("0")}

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

    query = _append_date_account_filters(
        query, params,
        date_col="DATE(tg.closed_at)", account_col="tg.account_id",
        from_date=from_date, to_date=to_date, account_id=account_id,
    )
    if asset_classes:
        ac_sql, ac_params = _build_asset_class_in_clause(asset_classes)
        query += f" AND tg.asset_class IN ({ac_sql})"
        params.update(ac_params)

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
    except SQLAlchemyError:
        logger.warning("trade_groups_win_loss_query_failed")

    return {"win_count": 0, "loss_count": 0, "avg_win": Decimal("0"), "avg_loss": Decimal("0")}


def get_performance_metrics(
    db: Session,
    from_date: date | None = None,
    to_date: date | None = None,
    account_id: str | None = None,
    asset_classes: list[str] | None = None,
) -> dict:
    """Compute overall performance metrics.

    P&L is derived from trade_groups.realized_pnl (closed round-trips),
    not from raw buy/sell amounts.
    """
    if _check_empty_asset_classes(asset_classes) is _EMPTY:
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
            "win_loss_ratio": None,
            "expectancy": Decimal("0"),
            "trading_days": 0,
        }

    group_metrics_sql = """
        SELECT
            COALESCE(SUM(tg.realized_pnl), 0) AS total_pnl,
            COALESCE(SUM(CASE WHEN tg.realized_pnl > 0 THEN 1 ELSE 0 END), 0) AS win_count,
            COALESCE(SUM(CASE WHEN tg.realized_pnl <= 0 THEN 1 ELSE 0 END), 0) AS loss_count,
            COALESCE(AVG(CASE WHEN tg.realized_pnl > 0 THEN tg.realized_pnl END), 0) AS avg_win,
            COALESCE(AVG(CASE WHEN tg.realized_pnl < 0 THEN tg.realized_pnl END), 0) AS avg_loss
        FROM trade_groups tg
        WHERE tg.status = 'closed'
    """
    trade_metrics_sql = """
        SELECT
            COALESCE(SUM(ABS(t.commission)), 0) AS total_commissions,
            COUNT(*) AS total_trades,
            COUNT(DISTINCT DATE(t.executed_at)) AS trading_days
        FROM trades t
        WHERE 1=1
    """

    params: dict = {}
    group_metrics_sql = _append_date_account_filters(
        group_metrics_sql,
        params,
        date_col="DATE(tg.closed_at)",
        account_col="tg.account_id",
        from_date=from_date,
        to_date=to_date,
        account_id=account_id,
    )
    trade_metrics_sql = _append_date_account_filters(
        trade_metrics_sql,
        params,
        date_col="DATE(t.executed_at)",
        account_col="t.account_id",
        from_date=from_date,
        to_date=to_date,
        account_id=account_id,
    )

    if asset_classes:
        g_ac_sql, g_ac_params = _build_asset_class_in_clause(asset_classes, prefix="g_ac")
        t_ac_sql, t_ac_params = _build_asset_class_in_clause(asset_classes, prefix="t_ac")
        group_metrics_sql += f" AND tg.asset_class IN ({g_ac_sql})"
        trade_metrics_sql += f" AND t.asset_class IN ({t_ac_sql})"
        params.update(g_ac_params)
        params.update(t_ac_params)

    query = f"""
        WITH group_metrics AS (
            {group_metrics_sql}
        ),
        trade_metrics AS (
            {trade_metrics_sql}
        )
        SELECT
            group_metrics.total_pnl,
            trade_metrics.total_commissions,
            trade_metrics.total_trades,
            trade_metrics.trading_days,
            group_metrics.win_count,
            group_metrics.loss_count,
            group_metrics.avg_win,
            group_metrics.avg_loss
        FROM group_metrics
        CROSS JOIN trade_metrics
    """

    params = _sqlite_safe_params(db, params)
    row = db.execute(text(query), params).mappings().first()

    if not row:
        row = {
            "total_pnl": 0,
            "total_commissions": 0,
            "total_trades": 0,
            "trading_days": 0,
            "win_count": 0,
            "loss_count": 0,
            "avg_win": 0,
            "avg_loss": 0,
        }

    total_pnl = Decimal(str(row["total_pnl"]))
    total_commissions = Decimal(str(row["total_commissions"]))
    total_trades = int(row["total_trades"])
    trading_days = int(row["trading_days"])
    win_count = int(row["win_count"])
    loss_count = int(row["loss_count"])
    avg_win = Decimal(str(row["avg_win"]))
    avg_loss = Decimal(str(row["avg_loss"]))

    net_pnl = total_pnl - total_commissions

    total_decided = win_count + loss_count
    win_rate = (win_count / total_decided * 100) if total_decided > 0 else 0.0

    abs_avg_loss = abs(avg_loss)
    win_loss_ratio = float(avg_win / abs_avg_loss) if abs_avg_loss > 0 else None

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


def get_available_asset_classes(db: Session) -> list[str]:
    """获取所有已关闭 trade_group 的资产类型列表（去重排序）。"""
    query = """
        SELECT DISTINCT tg.asset_class
        FROM trade_groups tg
        WHERE tg.status = 'closed'
        ORDER BY tg.asset_class ASC
    """
    rows = db.execute(text(query)).mappings().all()
    return [row["asset_class"] for row in rows]
