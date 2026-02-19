# K 线图交易标记功能方案

在 Groups 页面点击一笔交易，弹出该品种在对应时间段内的 K 线图表，并标注每次买入卖出点。

---

## 一、市面同类工具调研

| 工具 | K线图实现 | 交易标记方式 | 数据来源 | 特点 |
|------|----------|------------|---------|------|
| **TradesViz** | 内嵌 TradingView 图表 | 自动在 K 线上叠加买入/卖出箭头，支持 MAE/MFE 分析 | 自动对接多家 broker | 功能最完善，标杆参考 |
| **Tradervue** | TradingView 图表 | 入场/出场点标记为绿/红箭头 | 自动获取 | 老牌工具，稳定但 UI 较旧 |
| **TradeZella** | 内嵌 K 线图 | 标记交易区间（entry 到 exit 的矩形区域）+ 箭头 | 自动获取 | 视觉效果好，区间高亮直观 |
| **Edgewonk** | 简化版 K 线 | 在图表上标记开仓/平仓点 | 手动或导入 | 桌面端，分析功能强 |
| **Kinfo** | TradingView 嵌入式图表 | 买卖点叠加标记 | 直连 broker API | 自动化程度高 |

**共同模式**：点击某笔交易 -> 弹出该品种在交易时间段内的 K 线图 -> 图上用箭头/标记标注每次买入卖出点。

---

## 二、技术方案

### 架构总览

```
+-------------- Frontend ---------------+     +--------- Backend ----------+
|                                        |     |                            |
|  GroupsPage                            |     |  GET /groups/{id}/chart    |
|    +-- 行点击 -> 打开 Modal            |     |    +-- 查询 group legs     |
|        +-- TradeChartModal             |     |    +-- 获取关联 trades     |
|            +-- 调用后端获取数据         |---->|    +-- 获取 OHLCV 数据    |
|            +-- lightweight-charts      |     |    |   (缓存层)            |
|            +-- markers overlay         |     |    +-- 返回合并数据        |
|                                        |     |                            |
+----------------------------------------+     +----------------------------+
```

### 1. 前端图表库选型：TradingView Lightweight Charts

**推荐 `lightweight-charts` v5**（TradingView 官方开源库，Apache 2.0）。

| 库 | 包大小 | 金融图表专精 | 标记 API | React 支持 | 许可 |
|----|-------|------------|---------|-----------|------|
| **lightweight-charts** | ~45KB gzip | 原生 K 线 | `setMarkers()` 原生支持 | 官方 wrapper | Apache 2.0 |
| Recharts | ~140KB gzip | 通用图表 | 需自行实现 | 原生 React | MIT |
| Apache ECharts | ~300KB gzip | 有 K 线 | 通过 markPoint | 需 wrapper | Apache 2.0 |
| Highcharts Stock | ~200KB gzip | 专业级 | 完善 | 官方 wrapper | 商业许可 |

选择理由：

- 原生 `CandlestickSeries` + `setMarkers()` API，专为本场景设计。
- 包最小（45KB），与现有 Recharts 不冲突。
- TradingView 级别的图表交互体验（缩放、拖拽、十字光标）。
- 无商业许可限制。

### 2. 行情数据源选型

| 数据源 | 覆盖范围 | 免费额度 | 延迟 | 推荐程度 |
|--------|---------|---------|------|---------|
| **yfinance** (Python) | 美股、ETF、期货主力 | 无限制（非官方） | 15min 延迟 | 开发阶段首选 |
| **Twelve Data** | 全球股票/期货/外汇/加密 | 800次/天 | 实时可选 | 生产首选 |
| **Alpha Vantage** | 股票/期货/外汇 | 25次/天 | 15min | 备选 |
| **Polygon.io** | 美股/期权/外汇/加密 | 5次/min | 15min | 备选 |
| **IBKR API** | 与 broker 一致 | 随账户 | 实时 | 项目已接入 IBKR，天然可用 |

**推荐策略**：后端使用 `yfinance` 快速实现，设计好抽象层（`MarketDataProvider` Protocol），后续可替换为 Twelve Data 或 IBKR API。

### 3. 后端新增 API 设计

**端点**: `GET /api/v1/groups/{group_id}/chart`

请求参数：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `group_id` | UUID | (path) | Trade group ID |
| `interval` | str | 自动选择 | `"1m"` / `"5m"` / `"15m"` / `"1h"` / `"1d"` |
| `padding` | int | 20 | 交易区间前后扩展的 K 线根数 |

响应结构：

```json
{
  "symbol": "AAPL",
  "interval": "5m",
  "candles": [
    {
      "time": 1708300800,
      "open": 182.50,
      "high": 183.20,
      "low": 182.30,
      "close": 183.00,
      "volume": 12345
    }
  ],
  "markers": [
    {
      "time": 1708301100,
      "position": "belowBar",
      "color": "#22c55e",
      "shape": "arrowUp",
      "text": "ENTRY 100 @ 182.55",
      "role": "entry",
      "trade_id": "uuid-..."
    },
    {
      "time": 1708305600,
      "position": "aboveBar",
      "color": "#ef4444",
      "shape": "arrowDown",
      "text": "EXIT 100 @ 183.10",
      "role": "exit",
      "trade_id": "uuid-..."
    }
  ],
  "group": {
    "direction": "long",
    "realized_pnl": "55.00",
    "opened_at": "2024-02-19T10:00:00Z",
    "closed_at": "2024-02-19T11:20:00Z"
  }
}
```

**自动时间粒度选择逻辑**：

```python
def choose_interval(opened_at: datetime, closed_at: datetime | None) -> str:
    """根据交易持续时间自动选择合适的 K 线粒度。"""
    duration = (closed_at or datetime.now(UTC)) - opened_at
    if duration < timedelta(hours=2):
        return "1m"
    elif duration < timedelta(hours=8):
        return "5m"
    elif duration < timedelta(days=3):
        return "15m"
    elif duration < timedelta(days=30):
        return "1h"
    else:
        return "1d"
```

### 4. 后端实现要点

#### 行情数据抽象层

```python
# backend/services/market_data.py

class OHLCVBar(BaseModel):
    time: int          # Unix timestamp
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int

class MarketDataProvider(Protocol):
    """行情数据提供者协议，便于替换数据源。"""
    def fetch_ohlcv(
        self, symbol: str, interval: str,
        start: datetime, end: datetime,
    ) -> list[OHLCVBar]: ...

class YFinanceProvider:
    """开发阶段使用 yfinance，免费无限制。"""
    def fetch_ohlcv(self, symbol, interval, start, end):
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        df = ticker.history(interval=interval, start=start, end=end)
        return [OHLCVBar(...) for row in df.itertuples()]
```

#### 缓存策略

- 相同 `(symbol, interval, date_range)` 的数据在首次请求后缓存。
- 开发阶段使用 in-memory LRU (`functools.lru_cache` 或 `cachetools.TTLCache`)。
- 生产阶段可升级为 Redis 或 `diskcache`。
- 已关闭的 group（历史数据不变）可长期缓存；open group 的数据设置较短 TTL。

#### marker 生成逻辑

```python
def build_markers(
    legs: list[TradeGroupLeg], direction: str,
) -> list[dict]:
    """将 group legs 转换为 lightweight-charts marker 格式。"""
    markers = []
    for leg in sorted(legs, key=lambda l: l.trade.executed_at):
        trade = leg.trade
        is_buy = trade.side == "buy"

        # 做多: buy=绿下方, sell=红上方
        # 做空: sell=红下方（开仓）, buy=绿上方（平仓）
        if direction == "long":
            position = "belowBar" if is_buy else "aboveBar"
            shape = "arrowUp" if is_buy else "arrowDown"
            color = ROLE_COLORS[leg.role]
        else:  # short
            position = "aboveBar" if is_buy else "belowBar"
            shape = "arrowDown" if is_buy else "arrowUp"
            color = ROLE_COLORS_SHORT[leg.role]

        markers.append({
            "time": int(trade.executed_at.timestamp()),
            "position": position,
            "shape": shape,
            "color": color,
            "text": f"{leg.role.upper()} {trade.quantity} @ {trade.price}",
            "role": leg.role,
            "trade_id": str(trade.id),
        })
    return markers
```

### 5. 前端组件设计

新增文件：

```
frontend/src/components/
  +-- TradeChartModal.tsx        # 弹窗容器 (Modal + 加载状态 + header)
  +-- CandlestickChart.tsx       # lightweight-charts 封装

frontend/src/api/
  +-- endpoints/groups.ts        # 新增 fetchGroupChart()
  +-- types/groups.ts            # 新增 GroupChartData 等类型
```

#### CandlestickChart 组件

```tsx
import { createChart, CandlestickSeries, CrosshairMode } from "lightweight-charts";
import { useRef, useEffect } from "react";

interface Props {
  candles: CandleData[];
  markers: MarkerData[];
  width?: number;
  height?: number;
}

export default function CandlestickChart({
  candles, markers, width = 860, height = 400,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width,
      height,
      layout: { background: { color: "#ffffff" } },
      grid: {
        vertLines: { color: "#f0f0f0" },
        horzLines: { color: "#f0f0f0" },
      },
      timeScale: { timeVisible: true, secondsVisible: false },
      crosshair: { mode: CrosshairMode.Normal },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    candleSeries.setData(candles);
    candleSeries.setMarkers(markers);
    chart.timeScale().fitContent();

    return () => chart.remove();
  }, [candles, markers, width, height]);

  return <div ref={containerRef} />;
}
```

#### TradeChartModal 组件

```tsx
import { useQuery } from "@tanstack/react-query";
import { fetchGroupChart } from "../api/endpoints/groups";
import CandlestickChart from "./CandlestickChart";

interface Props {
  groupId: string;
  onClose: () => void;
}

export default function TradeChartModal({ groupId, onClose }: Props) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["groupChart", groupId],
    queryFn: () => fetchGroupChart(groupId),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-lg shadow-xl w-[920px] max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold">
              {data?.symbol ?? "Loading..."}
            </h2>
            {data?.group && (
              <>
                <span className={
                  data.group.direction === "long"
                    ? "text-green-600" : "text-red-600"
                }>
                  {data.group.direction.toUpperCase()}
                </span>
                <span className="text-sm text-gray-500">
                  P&L: {data.group.realized_pnl ?? "open"}
                </span>
              </>
            )}
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            x
          </button>
        </div>

        {/* Chart Body */}
        <div className="p-4">
          {isLoading && (
            <div className="flex items-center justify-center h-[400px] text-gray-400">
              Loading chart data...
            </div>
          )}
          {error && (
            <div className="flex items-center justify-center h-[400px] text-red-500">
              Failed to load chart data
            </div>
          )}
          {data && (
            <CandlestickChart candles={data.candles} markers={data.markers} />
          )}
        </div>
      </div>
    </div>
  );
}
```

#### GroupsPage 修改

```tsx
// 新增状态
const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);

// 表格行添加点击
<tr
  key={row.id}
  className="hover:bg-gray-50 cursor-pointer"
  onClick={() => setSelectedGroupId(row.original.id)}
>

// 页面底部渲染弹窗
{selectedGroupId && (
  <TradeChartModal
    groupId={selectedGroupId}
    onClose={() => setSelectedGroupId(null)}
  />
)}
```

### 6. 交易标记视觉设计

#### 做多方向 (direction: "long")

| 角色 (role) | 图标 | 颜色 | 位置 | 文本格式 |
|------------|------|------|------|---------|
| entry (首次建仓) | arrowUp | `#22c55e` 绿色 | K线下方 | `ENTRY 100 @ 182.55` |
| add (加仓) | arrowUp | `#86efac` 浅绿 | K线下方 | `ADD 50 @ 183.00` |
| trim (减仓) | arrowDown | `#fca5a5` 浅红 | K线上方 | `TRIM 30 @ 184.00` |
| exit (清仓) | arrowDown | `#ef4444` 红色 | K线上方 | `EXIT 120 @ 184.50` |

#### 做空方向 (direction: "short")

颜色含义反转：entry/add 用红色系箭头向下（做空开仓），exit/trim 用绿色系箭头向上（做空平仓）。

---

## 三、实现步骤（分阶段）

### Phase 1 -- 核心可用

1. 后端：新增 `MarketDataProvider` 协议 + `YFinanceProvider` 实现 (`backend/services/market_data.py`)
2. 后端：新增 `GET /api/v1/groups/{group_id}/chart` 端点 (`backend/api/groups.py`)
3. 后端：实现自动粒度选择 + marker 生成 + in-memory 缓存
4. 前端：安装 `lightweight-charts`
5. 前端：实现 `CandlestickChart` 组件
6. 前端：实现 `TradeChartModal` 弹窗
7. 前端：Groups 页面行点击触发弹窗
8. 测试：后端 API 单元测试 + 前端 build 验证

### Phase 2 -- 体验优化

9. 时间粒度选择器（允许用户在弹窗内切换 1m/5m/15m/1h/1d）
10. 交易区间背景高亮（entry 到 exit 之间的 K 线区域加浅色底）
11. 成交量子图（volume 柱状图显示在 K 线下方）
12. 图表工具栏（截图导出、全屏模式）
13. Modal 响应式宽度适配

### Phase 3 -- 数据增强

14. 接入 Twelve Data 或 IBKR API 替换 yfinance
15. Redis 缓存层替换 in-memory 缓存
16. 技术指标叠加（MA、VWAP 等可选指标）
17. MAE/MFE 分析（最大不利偏移 / 最大有利偏移可视化）
18. symbol 映射管理（期货换月、期权代码 -> ticker 映射表）

---

## 四、关键风险与应对

| 风险 | 影响 | 应对策略 |
|------|------|---------|
| yfinance 数据缺失（期货合约到期等） | 图表空白 | symbol 映射层（合约 -> 连续主力），缺失时前端显示提示 |
| 分钟级数据历史有限（通常只保留 30 天） | 历史交易无法显示分钟 K | 自动降级到更大粒度 + 提示用户 |
| 市场数据 API 限速 | 请求失败 | 缓存 + 请求队列 + 降级提示 |
| symbol 映射复杂（期货换月、期权代码） | 找不到行情数据 | 维护 symbol -> ticker 映射表，fallback 到 underlying 字段 |
| yfinance 非官方 API 稳定性不保证 | 服务中断 | Provider 抽象层便于快速切换数据源 |

---

## 五、依赖变更

### 前端

```bash
npm install lightweight-charts    # ~45KB gzip, Apache 2.0
```

与现有 `recharts` 互不冲突，各司其职（recharts 用于分析图表，lightweight-charts 用于 K 线图）。

### 后端

```bash
uv add yfinance                   # 开发阶段行情数据源
uv add cachetools                 # 可选：in-memory TTL 缓存
```

生产阶段可选追加：

```bash
uv add twelvedata                 # 生产级行情 API
uv add redis                      # Redis 缓存
```

---

## 六、文件变更清单

| 操作 | 路径 | 说明 |
|------|------|------|
| 新增 | `backend/services/market_data.py` | MarketDataProvider 协议 + YFinanceProvider + 缓存 |
| 修改 | `backend/api/groups.py` | 新增 `/groups/{id}/chart` 端点 |
| 新增 | `frontend/src/components/CandlestickChart.tsx` | lightweight-charts K 线图封装 |
| 新增 | `frontend/src/components/TradeChartModal.tsx` | 图表弹窗组件 |
| 修改 | `frontend/src/pages/GroupsPage.tsx` | 行点击事件 + 弹窗状态 |
| 修改 | `frontend/src/api/endpoints/groups.ts` | 新增 `fetchGroupChart()` |
| 修改 | `frontend/src/api/types/groups.ts` | 新增 `GroupChartData` 等类型 |
