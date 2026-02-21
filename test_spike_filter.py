"""验证 filter_outlier_bars 滑动窗口算法对 MES 毛刺和 SNDK 长期趋势的处理。"""
from decimal import Decimal
import sys
sys.path.insert(0, ".")
from backend.services.market_data import OHLCVBar
from backend.services.providers.validation import filter_outlier_bars

# ========== 测试 1: MES 期货毛刺 (5m K 线) ==========
print("=== MES 期货毛刺检测 ===")
# 模拟 MES 5m K线数据，中间有 3 根毛刺 bar (close 跌到 55)
mes_bars = []
for i in range(50):
    close = Decimal("6400") + Decimal(str(i * 2))  # 正常: 6400~6498
    mes_bars.append(OHLCVBar(time=1000 + i * 300, open=close, high=close + 10, low=close - 10, close=close, volume=1000))

# 插入毛刺 bar (close = 55)
mes_bars[20] = OHLCVBar(time=mes_bars[20].time, open=Decimal("6440"), high=Decimal("6540"), low=Decimal("55.10"), close=Decimal("55.20"), volume=3446)
mes_bars[25] = OHLCVBar(time=mes_bars[25].time, open=Decimal("6450"), high=Decimal("6544"), low=Decimal("55.20"), close=Decimal("55.20"), volume=1171)

filtered_mes = filter_outlier_bars(mes_bars)
print(f"  原始: {len(mes_bars)} bars, 过滤后: {len(filtered_mes)} bars, 移除: {len(mes_bars) - len(filtered_mes)}")
assert len(mes_bars) - len(filtered_mes) == 2, f"应移除 2 根毛刺，实际移除 {len(mes_bars) - len(filtered_mes)}"
print("  ✅ 正确移除 2 根毛刺")

# ========== 测试 2: SNDK 股票长期趋势 (日线) ==========
print("\n=== SNDK 股票长期趋势 ===")
# 模拟 SNDK 从 68 涨到 267 的数据 (约 60 天)
sndk_bars = []
for i in range(60):
    close = Decimal("68") + Decimal(str(i * 3.3))  # 从 68 涨到 ~265
    sndk_bars.append(OHLCVBar(time=1000 + i * 86400, open=close - 1, high=close + 2, low=close - 2, close=close, volume=5000000))

filtered_sndk = filter_outlier_bars(sndk_bars)
print(f"  原始: {len(sndk_bars)} bars, 过滤后: {len(filtered_sndk)} bars, 移除: {len(sndk_bars) - len(filtered_sndk)}")
assert len(sndk_bars) - len(filtered_sndk) == 0, f"不应移除任何正常趋势数据，但移除了 {len(sndk_bars) - len(filtered_sndk)}"
print("  ✅ 正确保留所有正常趋势数据")

# ========== 测试 3: 股票数据中间有一根毛刺 ==========
print("\n=== 股票数据中间毛刺 ===")
stock_bars = []
for i in range(30):
    close = Decimal("100") + Decimal(str(i * 0.5))  # 正常: 100~114.5
    stock_bars.append(OHLCVBar(time=1000 + i * 86400, open=close - 1, high=close + 2, low=close - 2, close=close, volume=1000000))

# 第 15 根插入毛刺
stock_bars[15] = OHLCVBar(time=stock_bars[15].time, open=Decimal("107"), high=Decimal("108"), low=Decimal("20"), close=Decimal("20"), volume=100)

filtered_stock = filter_outlier_bars(stock_bars)
print(f"  原始: {len(stock_bars)} bars, 过滤后: {len(filtered_stock)} bars, 移除: {len(stock_bars) - len(filtered_stock)}")
assert len(stock_bars) - len(filtered_stock) == 1, f"应移除 1 根毛刺，实际移除 {len(stock_bars) - len(filtered_stock)}"
print("  ✅ 正确移除 1 根毛刺")

print("\n所有测试通过！ 🎉")
