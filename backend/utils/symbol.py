"""期货品种 symbol 归一化模块。

提供统一的接口将期货合约代码（如 MESZ5、ESZ24）归一化为标准基础品种代码（如 MES、ES）。
所有需要 symbol 归一化的业务模块统一从本模块导入，避免逻辑分散。

CME 期货品种命名规则：
    基础品种名 + 月份代码（1个字母）+ 年份（1~2位数字）
    月份代码: F=1月, G=2月, H=3月, J=4月, K=5月, M=6月,
              N=7月, Q=8月, U=9月, V=10月, X=11月, Z=12月

示例:
    MESU5  -> MES   (微型E-mini S&P 500, 2025年9月)
    MESH5  -> MES   (微型E-mini S&P 500, 2025年3月)
    ESZ24  -> ES    (E-mini S&P 500, 2024年12月)
    NQH5   -> NQ    (E-mini Nasdaq-100, 2025年3月)
    CLF25  -> CL    (原油, 2025年1月)
    GCZ5   -> GC    (黄金, 2025年12月)
    AAPL   -> AAPL  (股票，不变)
"""

from __future__ import annotations

import re

__all__ = ["normalize_futures_symbol", "FUTURES_MONTH_CODES", "FUTURES_SYMBOL_RE"]

# CME 期货月份代码（按月份顺序排列）
FUTURES_MONTH_CODES: str = "FGHJKMNQUVXZ"

# 期货品种正则：基础品种名(非贪婪) + 月份代码(1个字母) + 年份(1~2位数字)
FUTURES_SYMBOL_RE: re.Pattern[str] = re.compile(
    rf"^(.+?)[{FUTURES_MONTH_CODES}]\d{{1,2}}$"
)


def normalize_futures_symbol(
    symbol: str,
    asset_class: str | None = None,
) -> str:
    """将期货品种归一化为基础品种名。

    Args:
        symbol: 原始品种代码，如 "MESU5"、"AAPL"。
        asset_class: 资产类型。若为 "future" 则强制尝试归一化；
                     若为其他非空值则直接返回原值；
                     若为 None 则按正则匹配结果决定。

    Returns:
        归一化后的品种名。期货品种返回基础名（如 "MES"），
        其他品种原样返回。

    Examples:
        >>> normalize_futures_symbol("MESZ5", "future")
        'MES'
        >>> normalize_futures_symbol("AAPL", "stock")
        'AAPL'
        >>> normalize_futures_symbol("ESZ24")
        'ES'
    """
    if asset_class and asset_class != "future":
        return symbol
    m = FUTURES_SYMBOL_RE.match(symbol)
    if m:
        return m.group(1)
    return symbol
