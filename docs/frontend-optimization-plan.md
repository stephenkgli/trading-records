# 前端优化方案

> 基于 Vercel React Best Practices、React Composition Patterns 最佳实践，结合项目现状进行全面审计。

---

## 目录

1. [现状总结](#1-现状总结)
2. [Bundle 体积优化 (CRITICAL)](#2-bundle-体积优化-critical)
3. [渲染性能优化 (HIGH)](#3-渲染性能优化-high)
4. [Re-render 优化 (MEDIUM)](#4-re-render-优化-medium)
5. [组件架构优化 (MEDIUM)](#5-组件架构优化-medium)
6. [数据获取与缓存优化 (MEDIUM)](#6-数据获取与缓存优化-medium)
7. [客户端存储优化 (LOW-MEDIUM)](#7-客户端存储优化-low-medium)
8. [JavaScript 性能微优化 (LOW)](#8-javascript-性能微优化-low)
9. [构建配置优化](#9-构建配置优化)
10. [优化优先级总览](#10-优化优先级总览)

---

## 1. 现状总结

### 做得好的地方

- 所有页面已使用 `React.lazy()` + `Suspense` 实现代码分割
- `TradeChartModal` 已通过 `lazy()` 按需加载
- TanStack Query 统一管理服务端状态，配置了合理的 `staleTime`（30s）和 `retry`（1）
- TypeScript strict mode 全开，类型安全有保障
- API 层三层架构（http → endpoints → hooks）分离清晰
- `useMemo` / `useCallback` 在关键路径上有使用
- `useRef` 模式避免 effect 依赖变更（如 `KLineChartView` 中的 `onChartReadyRef`）

### 需要改进的地方

以下按优先级从高到低排列。

---

## 2. Bundle 体积优化 (CRITICAL)

### 2.1 Vite 手动分包（manualChunks）

**问题：** 当前 `vite.config.ts` 没有配置任何分包策略，所有第三方依赖会被打入同一个 vendor chunk，导致：
- `recharts`（~300KB gzip 后约 80KB）、`klinecharts`（~200KB）、`@tanstack/react-table` 等大库全部首屏加载
- 用户只看 Dashboard 也要下载 KLine 图表库

**方案：**

```ts
// vite.config.ts
export default defineConfig({
  build: {
    outDir: "dist",
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          "vendor-query": ["@tanstack/react-query"],
          "vendor-table": ["@tanstack/react-table"],
          "vendor-recharts": ["recharts"],
          "vendor-klinecharts": ["klinecharts"],
          "vendor-date": ["date-fns"],
        },
      },
    },
  },
});
```

**收益：**
- recharts 和 klinecharts 独立分包，只在使用图表的页面按需加载
- React 核心库单独分包，变更业务代码时用户缓存不失效
- 用户首屏只需加载 react + router + query 核心包

### 2.2 recharts 按需导入

**问题：** `EquityCurve.tsx` 和 `SymbolBreakdown.tsx` 从 recharts 顶层 barrel file 导入：

```tsx
// 当前写法 — 可能引入整个 recharts 库
import { LineChart, Line, XAxis, ... } from "recharts";
```

**方案：** Vite 的 tree-shaking 对 recharts 的 ESM 导出已有较好支持，但建议验证构建产物。如果 bundle 分析显示 recharts 体积过大，可改用直接路径导入：

```tsx
import { LineChart } from "recharts/es6/chart/LineChart";
import { Line } from "recharts/es6/cartesian/Line";
```

**验证步骤：** 先安装 `rollup-plugin-visualizer` 检查实际体积再决定是否需要改。

### 2.3 移除未使用的 zustand 依赖

**问题：** `package.json` 中安装了 `zustand ^5.0.0`，但整个前端代码中没有任何文件引用它。

**方案：**
```bash
cd frontend && npm uninstall zustand
```

### 2.4 基于用户意图预加载（Preload on Intent）

**问题：** `GroupsPage` 中点击行才触发 `TradeChartModal` 的 lazy load，用户会看到 "Loading chart..." 的延迟。

**方案：** 在鼠标 hover 表格行时预加载 chart 模块：

```tsx
// GroupsPage.tsx
const preloadChart = () => {
  void import("../components/TradeChartModal");
};

// 在 <tr> 上添加
<tr
  onMouseEnter={preloadChart}
  onClick={() => setSelectedGroupId(row.original.id)}
>
```

**依据：** vercel-react-best-practices `bundle-preload` 规则 — 在用户意图明确时（hover/focus）预加载重型模块，减少感知延迟。

---

## 3. 渲染性能优化 (HIGH)

### 3.1 提取 Stat 组件到文件级别

**问题：** `AnalyticsPage.tsx` 中 `Stat` 组件定义在同一文件底部，每次 AnalyticsPage 重新渲染时，`Stat` 函数引用都会变化（虽然 React 在大多数情况下仍能 diff 正确，但不利于后续 memo 优化）。

**方案：** 将 `Stat` 提取为独立的 memoized 组件：

```tsx
// 文件顶层或单独文件
const Stat = memo(function Stat({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  const colorClass =
    color === "green" ? "text-green-600"
    : color === "red" ? "text-red-600"
    : "text-gray-900";
  return (
    <div>
      <span className="text-gray-500 block">{label}</span>
      <span className={`text-lg font-semibold ${colorClass}`}>{value}</span>
    </div>
  );
});
```

**依据：** `rerender-memo` 规则 — 提取 expensive/frequently-rendered 子树为 memoized 组件。

### 3.2 提取静态 JSX 到文件级别

**问题：** 多处 loading skeleton 和空状态 JSX 在组件内部创建：

```tsx
// TradeChartModal.tsx 中
<div className="h-[320px] bg-gray-800 animate-pulse rounded" />
```

**方案：** 将静态 JSX 提升到模块级别避免每次渲染重建：

```tsx
const chartLoadingSkeleton = (
  <div className="flex flex-col gap-2">
    <div className="h-[320px] bg-gray-800 animate-pulse rounded" />
    <div className="h-[72px] bg-gray-800 animate-pulse rounded" />
  </div>
);

const emptyState = (
  <p className="text-sm text-gray-400 text-center py-8">No data available</p>
);
```

**依据：** `rendering-hoist-jsx` 规则 — 静态 JSX 不依赖 props/state 时应提升到文件级别。

### 3.3 SymbolBreakdown 动态高度计算优化

**问题：** `SymbolBreakdown` 的 `ResponsiveContainer` height 使用 `Math.max(200, chartData.length * 35)` 每次 render 都重新计算。

**方案：** 将高度计算纳入已有的 `useMemo`：

```tsx
const { chartData, chartHeight } = useMemo(() => {
  const items = data.map((d) => ({
    symbol: d.symbol,
    pnl: Number(d.net_pnl),
    trades: d.trade_count,
  }));
  return {
    chartData: items,
    chartHeight: Math.max(200, items.length * 35),
  };
}, [data]);
```

### 3.4 PnLCalendar 条件渲染安全性

**问题：** `PnLCalendar.tsx` 第 81 行使用 `&&` 做条件渲染：
```tsx
{hasData && (
  <span ...>
```

其中 `hasData` 是 boolean，不会出现 `0` 渲染问题，这里是安全的。但日历 cell 内的 `entry!.trade_count` 使用了非空断言，不够防御性。

**方案：** 改用显式三元判断 + 安全访问：

```tsx
{hasData ? (
  <span className={`text-[10px] font-medium ${pnl >= 0 ? "text-green-700" : "text-red-700"}`}>
    ${Math.abs(pnl).toFixed(0)}
  </span>
) : null}
```

**依据：** `rendering-conditional-render` 规则 — 始终使用显式三元判断替代 `&&`。

---

## 4. Re-render 优化 (MEDIUM)

### 4.1 消除 AssetClassFilter 初始化中的重复逻辑

**问题：** `AnalyticsPage` 和 `GroupsPage` 各自独立实现了一套完全相同的 AssetClass 持久化逻辑：
- `loadSavedSelection()` / `saveSelection()`
- `initializedRef` + `useEffect` 初始化模式
- `selectedAssetClasses` state 管理

两个页面各用不同的 `STORAGE_KEY`（`analytics_asset_class_filter` vs `groups_asset_class_filter`），但核心逻辑重复约 40 行。

**方案：** 提取为自定义 hook：

```tsx
// hooks/useAssetClassFilter.ts
function useAssetClassFilter(storageKey: string) {
  const [selectedAssetClasses, setSelectedAssetClasses] = useState<string[] | null>(null);
  const initializedRef = useRef(false);

  const { data: availableAssetClasses = [], isFetched } = useQuery({
    queryKey: ["availableAssetClasses"],
    queryFn: fetchAvailableAssetClasses,
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    if (!isFetched || initializedRef.current) return;
    initializedRef.current = true;
    // ... 初始化逻辑
  }, [availableAssetClasses, isFetched]);

  useEffect(() => {
    if (selectedAssetClasses === null) return;
    saveSelection(storageKey, selectedAssetClasses);
  }, [selectedAssetClasses, storageKey]);

  return {
    availableAssetClasses,
    selectedAssetClasses,
    setSelectedAssetClasses,
    assetClassesParam: selectedAssetClasses === null ? undefined : selectedAssetClasses,
    isInitialized: selectedAssetClasses !== null,
  };
}
```

**依据：** 组合模式中的 `state-decouple-implementation` 规则 — 将状态管理逻辑与 UI 解耦。

### 4.2 缩窄 Effect 依赖

**问题：** `AssetClassFilter.tsx` 中注册全局 mousedown 监听器的 effect 没有依赖问题，但缺少 `{ passive: true }` 选项：

```tsx
useEffect(() => {
  function handleClickOutside(e: MouseEvent) { ... }
  document.addEventListener("mousedown", handleClickOutside);
  return () => document.removeEventListener("mousedown", handleClickOutside);
}, []);
```

**方案：** 虽然 mousedown 事件通常没有默认行为需要阻止，但为一致性起见可以标记为 passive。更重要的是，`TradeChartModal.tsx` 中的 keydown 监听器应使用 event handler ref 模式：

```tsx
// 当前代码使用 ref 存储 selectedOverlayId 和 chart — 已是正确模式
// 但可以进一步简化，使用 useEventCallback 模式
```

**依据：** `advanced-event-handler-refs` 规则、`client-passive-event-listeners` 规则。

### 4.3 DashboardPage 条件查询优化

**问题：** `DashboardPage` 同时发起两个查询（performance + dailySummaries），但不论查询是否返回数据，组件都会渲染。当 `metrics` 为 undefined 时，`MetricsCards` 不渲染，但整个 page 仍会因为另一个 query 的状态变化而 re-render。

**方案：** 考虑将 MetricsCards 和 EquityCurve 各自管理自己的数据获取（组件内查询），避免父组件因不相关的 query 状态变化而 re-render：

```tsx
// MetricsCards 内部获取自己的数据
function MetricsCards() {
  const { data: metrics } = useQuery({
    queryKey: ["performance"],
    queryFn: () => fetchPerformance(),
  });
  if (!metrics) return <MetricsSkeleton />;
  return <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">...</div>;
}
```

这样 DashboardPage 变为纯布局组件，不持有任何数据查询状态。

**依据：** `rerender-derived-state` 规则 — 让数据尽可能靠近消费它的组件。

---

## 5. 组件架构优化 (MEDIUM)

### 5.1 避免 Boolean Props 膨胀 — DrawingToolbar

**问题：** `DrawingToolbar` 组件接收多个回调 props：

```tsx
interface Props {
  chart: Chart | null;
  disabled: boolean;
  selectedOverlayId: string | null;
  onDeleteSelected: () => void;
  onClearAll: () => void;
  onStyleChange: () => void;
}
```

虽然还没到"boolean props 膨胀"的程度，但 `disabled` 实质上是 `!chart` 的派生状态，不应作为 prop 传递。

**方案：** 让 DrawingToolbar 直接从 chart 推导 disabled 状态：

```tsx
// 移除 disabled prop，内部判断
function DrawingToolbar({ chart, ... }: Props) {
  const isDisabled = !chart;
  // ...
}
```

**依据：** `rerender-derived-state-no-effect` 规则 — 可以从现有 props 推导的值不应作为独立 prop 传递。

### 5.2 创建显式 Filter Variant（长期）

**问题：** `AssetClassFilter` 在 AnalyticsPage 和 GroupsPage 中的使用方式完全相同，未来如果不同页面需要不同的过滤行为（比如单选 vs 多选），当前组件的通用性不足。

**方案（长期）：** 如果过滤器复杂度增长，考虑使用 Compound Component 模式：

```tsx
<Filter.Root storageKey="analytics_asset_class_filter">
  <Filter.Trigger />
  <Filter.Dropdown>
    <Filter.SelectAll />
    <Filter.ClearAll />
    <Filter.Options />
  </Filter.Dropdown>
</Filter.Root>
```

**依据：** `architecture-compound-components` 规则和 `patterns-explicit-variants` 规则。当前阶段提取 hook（4.1）已足够，复合组件是进一步演进方向。

### 5.3 Layout 组件可以接受 children 而非依赖 Outlet

**现状：** `Layout.tsx` 使用 React Router 的 `<Outlet />` 模式，这是 React Router v6 的推荐方式，不需要改动。当前实现符合最佳实践。

---

## 6. 数据获取与缓存优化 (MEDIUM)

### 6.1 清理遗留的自定义 useQuery hook

**问题：** `api/hooks/index.ts` 中实现了一套自定义的 `useQuery` hook（基于 useState + useEffect），但实际页面中全部使用 TanStack Query 的 `useQuery`。这个自定义实现是遗留代码。

```tsx
// api/hooks/index.ts — 遗留的自定义 useQuery 实现
function useQuery<T>(fetcher: () => Promise<T>, deps: unknown[]): UseQueryResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  // ...
}
```

**方案：**
- 确认没有任何页面或组件导入 `api/hooks/index.ts` 中的 hooks
- 如果确认无引用，删除整个文件
- 如果有少量引用，迁移到 TanStack Query

**收益：** 减少维护负担，避免团队成员混淆使用哪套数据获取方案。

### 6.2 优化 TanStack Query Key 结构

**问题：** 当前 query key 使用扁平数组，当参数增多时不利于 `invalidateQueries` 的精确匹配：

```tsx
queryKey: ["performance", dateRange.from, dateRange.to, assetClassesParam]
```

**方案：** 采用结构化 query key：

```tsx
queryKey: ["performance", { from: dateRange.from, to: dateRange.to, assetClasses: assetClassesParam }]
```

这样可以通过 `queryClient.invalidateQueries({ queryKey: ["performance"] })` 一次性失效所有 performance 相关缓存，而不受参数变化影响。

### 6.3 GroupsPage 分页查询优化

**问题：** 每次翻页都完全重新加载，用户会看到 Loading 闪烁。

**方案：** 使用 TanStack Query 的 `placeholderData` (v5) 保留上一页数据，实现平滑翻页：

```tsx
import { keepPreviousData } from "@tanstack/react-query";

const { data, isLoading, isPlaceholderData } = useQuery({
  queryKey: ["groups", page, statusFilter, sortParam, orderParam, assetClassesParam],
  queryFn: () => fetchGroups(...),
  placeholderData: keepPreviousData,
});
```

配合 UI 提示当前显示的是 placeholder 数据：

```tsx
<div className={isPlaceholderData ? "opacity-60 transition-opacity" : ""}>
  {/* 表格内容 */}
</div>
```

---

## 7. 客户端存储优化 (LOW-MEDIUM)

### 7.1 localStorage Schema 版本化

**问题：** 当前 `AssetClassFilter` 和 `drawingStorage.ts` 使用的 localStorage key 没有版本前缀：

```tsx
const STORAGE_KEY = "analytics_asset_class_filter";
const STORAGE_KEY = "groups_asset_class_filter";
// drawingStorage.ts 中也是裸 key
```

如果 schema 变化（比如从 `string[]` 变为 `{ version: number, classes: string[] }`），旧数据会导致解析错误。

**方案：**

```tsx
const STORAGE_VERSION = "v1";
const STORAGE_KEY = `analytics_asset_class_filter:${STORAGE_VERSION}`;
```

**依据：** `client-localstorage-schema` 规则 — 为 localStorage key 添加版本前缀，schema 变更时自动忽略旧数据。

### 7.2 集中管理 localStorage 操作

**问题：** `loadSavedSelection` / `saveSelection` 在两个页面中重复定义，且 `drawingStorage.ts` 也有自己的 localStorage 操作。

**方案：** 创建统一的 storage utility：

```tsx
// utils/storage.ts
const SCHEMA_VERSION = "v1";

export function storageGet<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(`${key}:${SCHEMA_VERSION}`);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function storageSet<T>(key: string, value: T): void {
  try {
    localStorage.setItem(`${key}:${SCHEMA_VERSION}`, JSON.stringify(value));
  } catch {
    // 静默处理 quota 等错误
  }
}
```

---

## 8. JavaScript 性能微优化 (LOW)

### 8.1 PnLCalendar 使用 Map 查找

**现状：** `PnLCalendar.tsx` 中已正确使用 `Map` 做日期查找：

```tsx
const dataMap = new Map<string, CalendarEntry>();
data?.forEach((entry) => { dataMap.set(entry.date, entry); });
```

符合 `js-set-map-lookups` 规则，无需改动。

### 8.2 AssetClassFilter 使用 Set 查找

**现状：** 已使用 `useMemo` + `Set` 做成员检查：

```tsx
const activeSet = useMemo(() => new Set(selectedAssetClasses), [selectedAssetClasses]);
```

符合最佳实践，无需改动。

### 8.3 避免在 GroupsPage columns 中创建匿名函数

**问题：** `useMemo` 包裹的 columns 定义中，每个 `cell` 渲染函数都是新的匿名函数，但由于 columns 数组被 `useMemo(() => ..., [])` 缓存且依赖数组为空，实际上函数引用是稳定的。当前实现已经是合理的。

---

## 9. 构建配置优化

### 9.1 生产环境关闭 sourcemap

**问题：** 当前 `vite.config.ts` 中 `sourcemap: true` 会在生产构建中生成 source map 文件，增加构建产物体积，也可能暴露源码。

**方案：**

```ts
build: {
  outDir: "dist",
  sourcemap: process.env.NODE_ENV === "development",
},
```

或者使用 `"hidden"` 模式，只生成 sourcemap 但不在 bundle 中引用：

```ts
sourcemap: "hidden", // 可上传到 error tracking 服务但不暴露给用户
```

### 9.2 添加 Bundle 分析工具

**方案：** 安装 `rollup-plugin-visualizer` 用于可视化分析构建产物：

```bash
npm install -D rollup-plugin-visualizer
```

```ts
// vite.config.ts
import { visualizer } from "rollup-plugin-visualizer";

export default defineConfig({
  plugins: [
    react(),
    visualizer({ open: true, gzipSize: true }),
  ],
});
```

构建后会自动生成交互式 treemap，帮助识别体积瓶颈。

### 9.3 启用 gzip/brotli 压缩预构建

**方案：** 安装 `vite-plugin-compression`：

```bash
npm install -D vite-plugin-compression
```

```ts
import compression from "vite-plugin-compression";

export default defineConfig({
  plugins: [
    react(),
    compression({ algorithm: "gzip" }),
    compression({ algorithm: "brotliCompress", ext: ".br" }),
  ],
});
```

配合 Nginx/CDN 直接提供预压缩文件，无需运行时压缩。

---

## 10. 优化优先级总览

| 优先级 | 编号 | 优化项 | 预期收益 | 实施难度 |
|--------|------|--------|----------|----------|
| CRITICAL | 2.1 | Vite manualChunks 分包 | 首屏加载减少 30-50% | 低 |
| CRITICAL | 2.3 | 移除未使用的 zustand | 减少依赖体积 | 极低 |
| HIGH | 2.4 | 预加载 TradeChartModal | 感知延迟降低 50%+ | 低 |
| HIGH | 3.1 | 提取 memoized Stat 组件 | 减少 re-render 开销 | 低 |
| HIGH | 6.1 | 清理遗留自定义 hooks | 减少维护负担 | 低 |
| MEDIUM | 4.1 | 提取 useAssetClassFilter hook | 消除 ~80 行重复代码 | 中 |
| MEDIUM | 6.3 | 分页 placeholderData | 翻页体验平滑 | 低 |
| MEDIUM | 3.2 | 提升静态 JSX 到模块级 | 微量 GC 压力减少 | 低 |
| MEDIUM | 6.2 | 结构化 Query Key | 缓存失效更精确 | 低 |
| MEDIUM | 9.1 | 生产关闭 sourcemap | 构建产物减小 | 极低 |
| LOW-MEDIUM | 7.1 | localStorage 版本化 | 防止 schema 迁移问题 | 低 |
| LOW-MEDIUM | 7.2 | 集中 storage 工具函数 | 减少重复代码 | 低 |
| LOW | 9.2 | Bundle 分析工具 | 辅助后续优化决策 | 极低 |
| LOW | 9.3 | gzip/brotli 预压缩 | 传输体积进一步减少 | 低 |
| 长期 | 5.2 | Compound Component 模式 | 组件扩展性提升 | 高 |

### 建议实施顺序

**第一阶段（低成本高收益）：**
1. 移除 zustand（2.3）
2. Vite manualChunks 分包（2.1）
3. 生产关闭 sourcemap（9.1）
4. 预加载 TradeChartModal（2.4）
5. 安装 bundle 分析工具（9.2）验证效果

**第二阶段（代码质量提升）：**
6. 清理遗留自定义 hooks（6.1）
7. 提取 useAssetClassFilter hook（4.1）
8. 分页 placeholderData（6.3）
9. 结构化 Query Key（6.2）

**第三阶段（精细化优化）：**
10. 提取 memoized 组件 + 静态 JSX 提升（3.1, 3.2）
11. localStorage 版本化 + 集中管理（7.1, 7.2）
12. gzip/brotli 预压缩（9.3）

---

## 参考规则来源

- `vercel-react-best-practices/rules/bundle-*` — Bundle 体积优化
- `vercel-react-best-practices/rules/rerender-*` — Re-render 优化
- `vercel-react-best-practices/rules/rendering-*` — 渲染性能优化
- `vercel-react-best-practices/rules/js-*` — JavaScript 性能
- `vercel-react-best-practices/rules/client-*` — 客户端优化
- `vercel-react-best-practices/rules/advanced-*` — 高级模式
- `vercel-composition-patterns/rules/architecture-*` — 组件架构
- `vercel-composition-patterns/rules/state-*` — 状态管理模式
- `vercel-composition-patterns/rules/patterns-*` — 实现模式
