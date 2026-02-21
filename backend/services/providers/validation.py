"""OHLCV bar data validation."""

from decimal import Decimal
from statistics import median

import structlog

from backend.services.market_data import OHLCVBar

logger = structlog.get_logger(__name__)

# 单根 K 线内部最大允许的 (high-low)/high 比例。
# 正常期货 5 分钟 K 线波幅极少超过 5%，50% 属于明显异常。
_MAX_INTRABAR_SPREAD_RATIO = Decimal("0.50")

# 跨 Bar 异常检测：偏离局部中位数超过此比例的 bar 被视为毛刺。
_OUTLIER_DEVIATION_RATIO = 0.30

# 滑动窗口大小（单侧）：取前后各 N 根 bar 作为参考。
# 对 5m K 线，10 根 = 前后约 50 分钟的邻居数据。
_WINDOW_SIZE = 10


def validate_bar(bar: OHLCVBar) -> bool:
    """Validate OHLCV bar data integrity.

    Checks:
    - high >= low, high >= open/close, low <= open/close
    - volume >= 0
    - all prices > 0
    - 单根 K 线内部价差不超过合理阈值（过滤极端毛刺）
    """
    if bar.high < bar.low:
        return False
    if bar.high < bar.open or bar.high < bar.close:
        return False
    if bar.low > bar.open or bar.low > bar.close:
        return False
    if bar.volume < 0:
        return False
    if any(p <= Decimal("0") for p in (bar.open, bar.high, bar.low, bar.close)):
        return False

    # 单 Bar 内部价差比例检查：如果 (high - low) / high 超过阈值，
    # 说明该 bar 包含异常价格（如合约换月回调错误、流动性空洞等）。
    if bar.high > 0:
        spread_ratio = (bar.high - bar.low) / bar.high
        if spread_ratio > _MAX_INTRABAR_SPREAD_RATIO:
            return False

    return True


def filter_outlier_bars(
    bars: list[OHLCVBar],
    deviation_ratio: float = _OUTLIER_DEVIATION_RATIO,
    window_size: int = _WINDOW_SIZE,
) -> list[OHLCVBar]:
    """过滤跨 Bar 的统计学异常（毛刺）。

    **两层检测**：

    1. **单 Bar 完整性检查** — 调用 ``validate_bar`` 过滤内部不一致
       的 bar（如 high-low 价差异常大）。
    2. **滑动窗口异常检测** — 对每根 bar，取其前后各 ``window_size``
       根 bar 的 close 中位数作为参考值。检查 OHLC 四个价格是否都
       在局部中位数的合理范围内。只要 open/high/low/close 中任一
       偏离超过 ``deviation_ratio``，即标记为异常。

    滑动窗口设计能正确处理：
    - 短时间间隔（5m）中的极端毛刺（如合约换月回调错误）
    - 长期趋势中的正常价格变化（如股价数月翻倍）

    至少需要 3 根 bar 才能进行异常检测，否则原样返回。
    """
    if len(bars) < 3:
        return bars

    # 第一层：单 Bar 完整性过滤（拦截 high-low 价差异常等）
    valid_bars: list[OHLCVBar] = []
    for bar in bars:
        if validate_bar(bar):
            valid_bars.append(bar)
        else:
            logger.warning(
                "invalid_bar_removed",
                time=bar.time,
                open=float(bar.open),
                high=float(bar.high),
                low=float(bar.low),
                close=float(bar.close),
            )

    if len(valid_bars) < 3:
        return valid_bars

    # 第二层：滑动窗口异常检测
    closes = [float(b.close) for b in valid_bars]
    n = len(closes)

    filtered: list[OHLCVBar] = []
    removed = 0

    for i, bar in enumerate(valid_bars):
        # 取以当前 bar 为中心的窗口
        start = max(0, i - window_size)
        end = min(n, i + window_size + 1)
        window = closes[start:end]

        # 排除当前 bar 自身来计算参考中位数
        neighbors = window[:i - start] + window[i - start + 1:]
        if not neighbors:
            filtered.append(bar)
            continue

        local_med = median(neighbors)
        if local_med <= 0:
            filtered.append(bar)
            continue

        # 检查 OHLC 四个价格是否都在合理范围内
        is_outlier = False
        for price_name, price_val in [
            ("open", float(bar.open)),
            ("high", float(bar.high)),
            ("low", float(bar.low)),
            ("close", float(bar.close)),
        ]:
            deviation = abs(price_val - local_med) / local_med
            if deviation > deviation_ratio:
                removed += 1
                logger.warning(
                    "outlier_bar_removed",
                    time=bar.time,
                    field=price_name,
                    value=price_val,
                    local_median=local_med,
                    deviation=f"{deviation:.2%}",
                )
                is_outlier = True
                break

        if not is_outlier:
            filtered.append(bar)

    if removed:
        logger.info("outlier_bars_filtered", total=len(valid_bars), removed=removed)

    return filtered
