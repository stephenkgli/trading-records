# Code Review Report

**Date:** 2026-02-21
**Scope:** Futures trading hours accuracy, K-line session filtering, chart marker correctness, timezone handling, and code quality.

---

## Executive Summary

This review examined the full data pipeline -- from market data providers through caching and API to frontend rendering -- focusing on whether futures trading hours are handled correctly and whether K-line charts display only regular-session data.

**Key conclusion:** The system has no trading session filtering. All OHLCV data from Databento (CME futures) and Tiingo (US stocks) is displayed as-is, including pre-market/after-hours bars for futures. This is a reasonable default for 24-hour CME Globex instruments, but the codebase has several related issues worth addressing.

**Findings by severity:**

| Severity | Count |
|----------|-------|
| Critical | 1 |
| Moderate | 5 |
| Low | 6 |

---

## Files Reviewed

| File | Purpose |
|------|---------|
| `backend/services/market_data.py` | OHLCV model, padded range calculation, marker snap logic |
| `backend/services/providers/databento_provider.py` | CME futures data via Databento |
| `backend/services/providers/tiingo_provider.py` | US stock data via Tiingo |
| `backend/services/providers/validation.py` | Bar validation and outlier filtering |
| `backend/api/groups.py` | Chart API endpoint |
| `backend/services/cache/ohlcv_cache.py` | OHLCV cache layer |
| `backend/schemas/chart.py` | Chart response schemas |
| `frontend/src/components/CandlestickChart.tsx` | Chart rendering |
| `frontend/src/components/TradeChartModal.tsx` | Chart modal |
| `frontend/src/pages/GroupsPage.tsx` | Groups list page |
| `frontend/src/pages/GroupDetailPage.tsx` | Group detail page |
| `frontend/src/api/client.ts` | Legacy API client |
| `frontend/src/api/endpoints/http.ts` | New API HTTP utilities |

---

## 1. Critical Findings

### 1.1 `getLocalOffsetSeconds()` hardcoded to return `0`

**File:** `frontend/src/components/CandlestickChart.tsx:25-27`

The function always returns `0`, despite comments describing the intent to apply a local timezone offset for the chart x-axis:

```typescript
function getLocalOffsetSeconds(): number {
  return 0;
}
```

Called in both `toChartCandles()` (line 30) and `toChartMarkers()` (line 47), it adds `0` to all timestamps. The chart displays UTC times instead of local times.

**Impact:** For a user in UTC+8, all bars and markers appear 8 hours earlier than local wall-clock time. CME RTH open at 08:30 CT shows as 14:30 on the chart, which is confusing without a UTC label.

**Recommendation:** Either implement the offset:

```typescript
function getLocalOffsetSeconds(): number {
  return -(new Date().getTimezoneOffset() * 60);
}
```

Or, if UTC display is intentional, update comments and remove the misleading offset plumbing. Using `lightweight-charts`' built-in `timeScale.tickMarkFormatter` is a cleaner approach for timezone-aware display.

---

## 2. Moderate Findings

### 2.1 No trading session filtering mechanism

**Files:** `databento_provider.py:89-148`, `groups.py:163-164`, `CandlestickChart.tsx`

The entire data pipeline (Databento -> cache -> API -> frontend) has no session-based filtering. There are no concepts of `session_start`, `session_end`, `rth`, or `market_open` anywhere in the codebase.

- `DabentoProvider.fetch_ohlcv()` passes the time range directly to the API with no session filtering.
- `compute_padded_range()` calculates the range purely from open/close times plus padding, ignoring session boundaries.
- The frontend renders all bars returned by the backend.

**CME trading sessions reference (ES/MES):**

| Session | Central Time (CT) | UTC |
|---------|-------------------|-----|
| Globex electronic | Sun 17:00 - Fri 16:00 | Sun 23:00 - Fri 22:00 |
| Daily maintenance | 16:00 - 17:00 | 21:00 - 22:00 |
| Regular Trading Hours (RTH) | 08:30 - 15:15 | 14:30 - 21:15 |

**Impact:** Charts show all-session data including overnight Globex bars. Users who want RTH-only charts have no option.

**Recommendation (long-term):** Add a `session` query parameter to the chart API (`rth` / `eth` / `all`) with a per-instrument session schedule configuration. Filter bars accordingly in the provider or cache layer.

### 2.2 Resample does not account for CME maintenance window gaps

**File:** `backend/services/providers/databento_provider.py:131-144`

```python
df = df.resample(rule).agg({
    "open": "first", "high": "max",
    "low": "min", "close": "last", "volume": "sum",
}).dropna()
```

When requesting 5m or 15m bars, 1m data is resampled using pandas `resample()`, which uses fixed calendar-time windows and is unaware of the CME maintenance window (21:00-22:00 UTC).

**Specifics:**
- Bars at the maintenance boundary (e.g., the 20:55 5m window) may contain only partial 1m data (missing the 21:00 bar), resulting in understated volume.
- `.dropna()` correctly removes fully-empty windows inside the maintenance period.
- Zero-volume filtering in `_to_bars()` provides additional cleanup.

**Impact:** Boundary bars have slightly low volume. OHLCV price values remain correct. No phantom bars are generated inside the maintenance window.

**Recommendation:** Prefer Databento's native `ohlcv-5m` schema (if available) to avoid client-side resample. Alternatively, segment the 1m data around gaps before resampling.

### 2.3 Cache completeness check confused by maintenance window

**File:** `backend/services/cache/ohlcv_cache.py:61-69`

```python
if last_bar_time + bar_duration * 2 < expected_end:
    return None  # partial coverage, re-fetch
```

The cache uses `2 * bar_duration` as the completeness threshold. For 5m bars, this is 10 minutes. The CME maintenance window is ~65 minutes, far exceeding this threshold.

If a request spans the maintenance window and the last cached bar is at 20:55 UTC while `expected_end` is 22:30 UTC, the cache is incorrectly judged as incomplete, triggering an unnecessary re-fetch.

**Impact:** No data errors. Wastes Databento API quota on redundant fetches for active groups that span the maintenance window.

**Recommendation:** Use an asset-class-aware gap threshold:

```python
gap_threshold = max(2 * bar_duration, timedelta(minutes=70)) if asset_class == "future" else 2 * bar_duration
```

### 2.4 Raw ISO timestamp strings displayed on Groups pages

**Files:** `frontend/src/pages/GroupsPage.tsx:128, 139`, `frontend/src/pages/GroupDetailPage.tsx:44-45`

The `formatDateTime()` helper returns raw ISO strings from the API without formatting:

```typescript
const formatDateTime = (value?: string | null) => {
  if (!value) return "-";
  const trimmed = value.trim();
  return trimmed || "-";
};
```

Users see strings like `"2025-01-15T14:30:00+00:00"` with no locale-aware formatting.

**Recommendation:**

```typescript
const formatDateTime = (value?: string | null) => {
  if (!value) return "-";
  const d = new Date(value);
  if (isNaN(d.getTime())) return value;
  return d.toLocaleString();
};
```

### 2.5 `_INTERVAL_DURATIONS` mapping duplicated in two backend modules

**Files:** `backend/services/market_data.py:110-116`, `backend/services/cache/ohlcv_cache.py:21-27`

The identical dictionary is defined independently in both files. Adding a new interval (e.g., `30m`) requires updating both.

**Recommendation:** Define once in `market_data.py` and import in `ohlcv_cache.py`.

---

## 3. Low / Informational Findings

### 3.1 Marker role-side consistency not validated

**File:** `backend/services/market_data.py:239-248`

`build_markers()` determines marker shape/position based on `trade.side` and group `direction`, but does not verify that the leg `role` is consistent. A grouper bug could produce a confusing visual (e.g., a green down-arrow below a bar for a long group exit).

**Recommendation:** Add a debug-level log when `role`, `side`, and `direction` are inconsistent.

### 3.2 Frontend API client has duplicated HTTP utilities

**Files:** `frontend/src/api/client.ts:1-34`, `frontend/src/api/endpoints/http.ts:1-39`

`client.ts` has its own copies of `getHeaders()`, `getUploadHeaders()`, and `handleResponse()` that are functionally identical to those in `endpoints/http.ts`. Additionally, inline types in `client.ts` overlap with `api/types/index.ts`.

**Recommendation:** Complete the migration to `endpoints/http.ts` and remove duplicates from `client.ts`.

### 3.3 `normalizeDateValue()` / `formatDateTime()` duplicated across pages

**Files:** `frontend/src/pages/GroupsPage.tsx:15-20`, `frontend/src/pages/GroupDetailPage.tsx:5-11`

**Recommendation:** Extract to a shared utility (e.g., `frontend/src/utils/date.ts`).

### 3.4 Marker colors use magic hex strings

**Files:** `backend/services/market_data.py:53-65`, `frontend/src/components/CandlestickChart.tsx:83-88`

Backend `ROLE_COLORS_LONG`/`ROLE_COLORS_SHORT` and frontend `upColor`/`downColor` happen to match but are defined independently with no shared contract.

**Recommendation:** Document the color scheme convention so changes on either side don't silently break visual consistency.

### 3.5 `position` and `shape` fields use plain `string` instead of literal types

**Files:** `frontend/src/api/types/groups.ts:46-54`, `backend/schemas/chart.py:17-18`

The frontend casts these values at runtime. The backend schema uses `str` without validation.

**Recommendation:** Use literal union types:

```typescript
position: "aboveBar" | "belowBar" | "inBar";
shape: "arrowUp" | "arrowDown" | "circle" | "square";
```

```python
position: Literal["aboveBar", "belowBar", "inBar"]
shape: Literal["arrowUp", "arrowDown", "circle", "square"]
```

### 3.6 `datetime.utcnow()` deprecated call in `compute_padded_range`

**File:** `backend/services/market_data.py:147`

```python
now = datetime.now(UTC) if end.tzinfo else datetime.utcnow()  # noqa: DTZ003
```

`datetime.utcnow()` is deprecated in Python 3.12. The fallback branch is unlikely to trigger in practice (all `end` values are timezone-aware), but should be cleaned up.

**Recommendation:** Replace with `datetime.now(UTC)` unconditionally.

---

## 4. Architecture Notes (No Issues Found)

### 4.1 Timezone pipeline is correct end-to-end

1. **Ingestion** (`backend/schemas/trade.py:30`): `executed_at: datetime` documented as UTC
2. **Storage** (`backend/models/trade.py:63-64`): `DateTime(timezone=True)`, always UTC
3. **Providers** normalize to UTC:
   - Tiingo (`tiingo_provider.py:89-91`): `astimezone(timezone.utc)`
   - Databento (`databento_provider.py:70-73`): `_normalize_timestamp()`
4. **Marker generation** (`market_data.py:252`): Converts to Unix timestamp from UTC datetime
5. **Frontend** receives Unix timestamps (chart data) or ISO strings (metadata)

### 4.2 `_snap_to_bar` correctly handles CME maintenance window

**File:** `backend/services/market_data.py:159-210`

The function detects K-line gaps (including the ~65-minute CME maintenance window) using a `2x normal_gap` heuristic, and snaps markers to the first bar after the gap rather than the last bar before it. Comments at lines 166-167 explicitly reference CME maintenance windows.

### 4.3 FIFO grouper and marker generation are consistent

The trade grouper correctly assigns roles (`entry`, `add`, `trim`, `exit`) via FIFO matching. `build_markers()` maps these to visual properties (color, position, shape) based on group direction. The color mapping is semantically correct:

- Long: entry/add = green, trim/exit = red
- Short: entry/add = red, trim/exit = green
- Arrow direction follows trade side: buy = `arrowUp`, sell = `arrowDown`

### 4.4 Zero-volume bar filtering works correctly

**File:** `backend/services/providers/databento_provider.py:155`

Bars with `volume == 0` (contract rolls, CME maintenance windows) are filtered out before validation, preventing unreliable price data from reaching the chart.

---

## 5. Summary Table

| # | Severity | Finding | File(s) | Action |
|---|----------|---------|---------|--------|
| 1.1 | **Critical** | `getLocalOffsetSeconds()` returns 0 -- chart shows UTC | `CandlestickChart.tsx:25-27` | Implement offset or clarify intent |
| 2.1 | Moderate | No trading session (RTH/ETH) filtering | Multiple | Add `session` parameter (long-term) |
| 2.2 | Moderate | Resample ignores maintenance window gaps | `databento_provider.py:131-144` | Use native 5m schema or segment resample |
| 2.3 | Moderate | Cache completeness threshold too tight for futures | `ohlcv_cache.py:61-69` | Use asset-class-aware threshold |
| 2.4 | Moderate | Raw ISO strings displayed for dates | `GroupsPage.tsx`, `GroupDetailPage.tsx` | Implement proper date formatting |
| 2.5 | Moderate | `_INTERVAL_DURATIONS` duplicated | `market_data.py`, `ohlcv_cache.py` | Consolidate to single source |
| 3.1 | Low | No role-side consistency validation in markers | `market_data.py:239-248` | Add defensive logging |
| 3.2 | Low | HTTP utilities duplicated in frontend | `client.ts`, `endpoints/http.ts` | Complete migration |
| 3.3 | Low | Date helpers duplicated across pages | `GroupsPage.tsx`, `GroupDetailPage.tsx` | Extract to shared utility |
| 3.4 | Low | Marker colors are unlinked magic strings | `market_data.py`, `CandlestickChart.tsx` | Document color convention |
| 3.5 | Low | `position`/`shape` typed as plain `string` | `types/groups.ts`, `chart.py` | Use literal union types |
| 3.6 | Low | `datetime.utcnow()` deprecated | `market_data.py:147` | Replace with `datetime.now(UTC)` |

---

## 6. Recommended Priority

### P1 -- Immediate

1. **Fix or clarify `getLocalOffsetSeconds()`** -- directly affects user experience on every chart view.

### P2 -- Near-term

2. **Implement proper date formatting** on Groups pages.
3. **Consolidate `_INTERVAL_DURATIONS`** -- quick win, reduces drift risk.
4. **Use asset-class-aware cache completeness threshold** -- reduces wasted API quota for futures.

### P3 -- Long-term

5. **Add RTH/ETH session filtering** to the chart API with per-instrument session schedules.
6. **Use native Databento 5m OHLCV schema** to avoid client-side resample boundary issues.
7. **Complete frontend `client.ts` migration** to eliminate HTTP/type duplication.
8. Address remaining low-severity items as part of routine maintenance.
