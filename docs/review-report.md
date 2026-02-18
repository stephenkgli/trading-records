# Trading Records System — Design Review Report

**Reviewer:** reviewer (design review agent)  
**Date:** 2026-02-18  
**Documents Reviewed:** `design-doc.md`, `research-report.md`

---

## 1. Overall Assessment

The design is **well-structured and pragmatic**. The three-layer architecture (Ingestion → Core → API + Frontend) is appropriate for a self-hosted single-user trading records system. The phased delivery plan is realistic, and the technology choices are defensible. The research report is thorough and the design clearly incorporates its findings.

**Verdict: Approve with recommendations.** No blocking issues found. The items below range from important improvements to minor suggestions.

---

## 2. Architecture Review

### 2.1 Strengths

- **Clean separation of concerns.** Ingestion, normalization, storage, API, and frontend are well-isolated. Each can be tested and replaced independently.
- **Batch-first, real-time later.** This is the correct priority for a trade journal system. Real-time adds significant operational complexity (persistent connections, reconnection logic) that is unnecessary for MVP.
- **Raw data preservation via JSONB.** Storing original broker payloads alongside normalized data is excellent. This enables reprocessing if the normalization logic changes and aids debugging.
- **Hybrid ingestion pattern.** Supporting API-based pull, scheduled pull, and manual CSV covers all practical scenarios.

### 2.2 Concerns

#### 2.2.1 Normalizer as Single Point of Coupling

The normalizer sits between all ingesters and the database. If the unified schema changes, every ingester's mapping must be updated. Consider:

- **Recommendation:** Define a formal `NormalizedTrade` Pydantic model as a contract. All ingesters produce this type, and the dedup engine only accepts this type. This makes schema changes explicit and caught by type checking.

#### 2.2.2 Missing Error Isolation Between Ingesters

The design does not specify what happens when one ingester fails mid-batch. If the IBKR Flex ingester crashes after inserting 50 of 200 trades, those 50 are committed but the import_log shows "failed."

- **Recommendation:** Wrap each import in a database transaction. Either the entire batch commits or none of it does. The dedup layer makes re-import safe, so atomic all-or-nothing semantics are the correct choice. Record partial failures in `import_logs.errors` JSONB with details on which records failed validation (before the transaction).

#### 2.2.3 Trade Grouping Tied to Insert Order

The FIFO trade grouping logic (Section 4.3) depends on processing trades in execution time order. But imports can arrive out of order (e.g., CSV import of older trades after newer ones are already grouped).

- **Recommendation:** Trade grouping should be a separate, re-runnable process. When new trades are inserted for a symbol, re-compute the grouping for that symbol from scratch (or from the earliest affected open group). Do not couple grouping to the import pipeline. Add a `POST /api/v1/groups/recompute?symbol=AAPL` endpoint.

---

## 3. Technology Stack Review

### 3.1 Appropriate Choices

| Choice | Assessment |
|--------|-----------|
| **Python 3.12+ / FastAPI** | Correct. Best IBKR library ecosystem, async-capable, auto-generated OpenAPI docs. |
| **PostgreSQL 16** | Correct. JSONB for raw data, window functions for P&L, mature tooling. |
| **SQLAlchemy 2.0 + Alembic** | Correct. Type-safe ORM with proper migration management. |
| **React + TypeScript** | Correct for the dashboard requirements. |
| **Docker Compose** | Correct for single-command self-hosted deployment. |

### 3.2 Points of Concern

#### 3.2.1 APScheduler (In-Process)

APScheduler running in the FastAPI process is convenient but fragile:

- If the backend process restarts during a Flex Query poll loop, the job state is lost.
- If two backend instances run (accidental duplicate `docker compose up`), jobs fire twice.
- No persistent job history or retry tracking.

**Recommendation:** This is acceptable for MVP, but document the limitation. For Phase 2, consider moving to a separate lightweight scheduler process or using PostgreSQL-backed job tracking (e.g., record last successful run timestamp in DB and check on startup). At minimum, add an idempotency check: if a Flex import already succeeded for today's date, skip the scheduled run.

#### 3.2.2 Frontend Build Separation

The docker-compose.yml defines the frontend as a separate service building from `./frontend`. For a single-user app, consider serving the built frontend static files from the FastAPI backend (via `StaticFiles` mount). This eliminates one container, simplifies deployment, and reduces resource usage.

**Recommendation:** Build frontend with Vite, copy dist output into backend image, serve via FastAPI `StaticFiles`. One container instead of two for the application layer.

#### 3.2.3 No Backend Dependency Management Tool Specified

The design mentions `pyproject.toml` with a comment "(uv/poetry)" but does not commit to one. This matters for reproducible builds.

**Recommendation:** Use **uv** — it is faster than poetry, supports lockfiles, and has strong Docker build caching support. Pin the decision in the design doc.

---

## 4. Data Schema Review

### 4.1 Strengths

- Composite natural key `(broker, broker_exec_id)` for dedup is correct and covers the major cases well.
- The CSV fallback (SHA-256 hash of trade fields) is a reasonable approach when no native execution ID exists.
- `trade_group_legs` junction table with `role` enum is a clean model for multi-leg round trips.
- `import_logs` table provides good auditability.

### 4.2 Concerns

#### 4.2.1 Missing Index Specifications

The ER diagram defines no indexes beyond PK/UK. The following queries will be frequent and need indexes:

```sql
-- Trade lookup by date range (most common query pattern)
CREATE INDEX idx_trades_executed_at ON trades (executed_at);

-- Filter by symbol within date range
CREATE INDEX idx_trades_symbol_executed_at ON trades (symbol, executed_at);

-- Filter by broker + account
CREATE INDEX idx_trades_broker_account ON trades (broker, account_id);

-- Trade group status lookup
CREATE INDEX idx_trade_groups_status ON trade_groups (status);

-- Group legs lookup by group
CREATE INDEX idx_trade_group_legs_group_id ON trade_group_legs (trade_group_id);
```

**Recommendation:** Add an index plan to the design doc. Include these in the initial Alembic migration.

#### 4.2.2 `net_amount` Computation

The schema defines `net_amount` as `price * qty - commission`. This formula is incorrect for sell-side trades and options where the sign conventions differ. For sells, the proceeds should be positive, and commission reduces net proceeds. For options, multiplier (e.g., 100) must be accounted for.

**Recommendation:** Either:
1. Remove `net_amount` from the schema and compute it in queries/views, or
2. Rename to `net_proceeds` and define the computation carefully per asset class, with the formula documented.

Option 1 is safer since computing on read avoids stale/inconsistent stored values.

#### 4.2.3 No `import_log_id` Foreign Key on Trades

The ER diagram shows `import_logs ||--o{ trades : "source of"` but the `trades` table has no `import_log_id` column. Without this, you cannot trace which import created a specific trade, and you cannot implement batch rollback.

**Recommendation:** Add `import_log_id (uuid FK, nullable)` to the `trades` table. Nullable for manually created trades.

#### 4.2.4 `daily_summaries` Materialized View vs Table

The design uses `daily_summaries` as a table but describes it as a "materialized view." These are different things in PostgreSQL:

- A materialized view is refreshed via `REFRESH MATERIALIZED VIEW` and cannot be directly inserted into.
- A table requires explicit insert/update logic.

**Recommendation:** Use a PostgreSQL **materialized view** with `REFRESH MATERIALIZED VIEW CONCURRENTLY` (requires a unique index). Refresh after each import. This avoids dual-write bugs and guarantees consistency with the trades table. Define:

```sql
CREATE MATERIALIZED VIEW daily_summaries AS
SELECT
  date_trunc('day', executed_at)::date AS date,
  account_id,
  SUM(net_amount) AS gross_pnl,
  -- ... aggregations ...
FROM trades
GROUP BY 1, 2;

CREATE UNIQUE INDEX ON daily_summaries (date, account_id);
```

#### 4.2.5 CSV Dedup Hash Collision Risk

SHA-256 hash of `(symbol, side, qty, price, executed_at)` will collide for legitimate duplicate executions: two fills at the same price and time for the same quantity (partial fill splits). This is rare but possible.

**Recommendation:** Add `sequence_number` or `row_number` from the CSV to the hash input. Alternatively, include the CSV filename and row number.

---

## 5. Security Review

### 5.1 Good Practices

- Secrets via environment variables (12-factor compliant).
- `.env` file not checked into git.
- Config endpoint returns redacted secrets.

### 5.2 Concerns

#### 5.2.1 No Application-Level Authentication

The design explicitly states "None for v1 (single-user, local)." This is acceptable **only if** the application is guaranteed to be network-isolated. However:

- Docker Compose exposes port 8000 on all interfaces by default (`0.0.0.0:8000`).
- If the host is on a home/office network, anyone on that network can access the trading data.
- The `/api/v1/config` PUT endpoint allows modifying broker credentials without any auth.

**Recommendation:** At minimum for v1:
1. Bind ports to `127.0.0.1` only in docker-compose.yml: `"127.0.0.1:8000:8000"` and `"127.0.0.1:3000:3000"`.
2. Add a simple API key or basic auth middleware — even a single shared secret from an env var. This is low-effort and prevents accidental exposure.

#### 5.2.2 Tradovate Credential Storage

The design stores Tradovate username/password in config. These are high-value credentials.

**Recommendation:** Document that users should use a dedicated API-only account if available, or at minimum a unique password. Consider adding at-rest encryption for the stored token (using a key derived from a local passphrase).

#### 5.2.3 No CORS Configuration Mentioned

If the frontend runs on port 3000 and the backend on port 8000, CORS must be configured. Missing CORS config will cause the frontend to fail silently.

**Recommendation:** Add explicit CORS configuration to the FastAPI app. For v1 single-host deployment, allow `localhost:3000` origin.

#### 5.2.4 Database Credentials in Docker Compose

The docker-compose.yml shows `${DB_USER}` and `${DB_PASSWORD}` but also exposes PostgreSQL on port 5432. If the host is network-accessible, the database is exposed.

**Recommendation:** Either remove the port mapping for `db` (backend connects via Docker network, not host port), or bind to `127.0.0.1:5432:5432`.

---

## 6. Reliability and Fault Tolerance Review

### 6.1 Strengths

- Deduplication means re-import is always safe — this is the single most important reliability feature.
- Import logs track success/failure state.
- Flex Query has CSV fallback when API is unavailable.

### 6.2 Concerns

#### 6.2.1 No Health Check Endpoints

Docker Compose should define health checks so dependent services wait for actual readiness (not just container start).

**Recommendation:** Add:
- Backend: `GET /health` endpoint that checks DB connectivity.
- Docker Compose: `healthcheck` on both `db` and `backend` services, with `depends_on.condition: service_healthy`.

#### 6.2.2 No Backup Strategy

Trading records are financial data with legal/tax implications. The design does not address backups.

**Recommendation:** Add a backup section:
- PostgreSQL `pg_dump` on a cron schedule to a local directory outside the Docker volume.
- Consider WAL archiving for point-in-time recovery.
- At minimum, document that users should back up the `pgdata` Docker volume.

#### 6.2.3 Flex Query Polling Has No Circuit Breaker

The Flex Query ingester polls up to 10 times at 10-second intervals. If the IBKR service is degraded (returning errors, not "not ready"), the ingester will retry all 10 times regardless.

**Recommendation:** Distinguish between "not ready" (expected, keep polling) and error responses (stop immediately, log error). Add exponential backoff for genuine errors.

#### 6.2.4 No Data Validation Layer

Broker data can have unexpected values (null prices, zero quantities, future timestamps). The design does not mention validation rules.

**Recommendation:** Add a validation step between normalization and dedup:
- Required fields check (symbol, price, quantity, executed_at)
- Range validation (price > 0, quantity != 0)
- Timestamp sanity (not in the future, not before account opening)
- Invalid records logged in `import_logs.errors`, not silently dropped.

---

## 7. Potential Risks and Additional Recommendations

### 7.1 FIFO Grouping Edge Cases

The FIFO round-trip logic is described at a high level. Several edge cases need specification:

1. **Short selling:** A SELL without a prior BUY should open a short group. The current description ("When a BUY executes, open a new group") implies long-only.
2. **Multiple accounts:** Grouping must be scoped by `account_id`, not just `symbol`.
3. **Options:** An option exercise/assignment closes a position but may not appear as a SELL trade. The grouping logic needs to handle this.
4. **Futures rollovers:** Closing one contract month and opening another is two separate symbols, but logically one continuous position.

**Recommendation:** Add a "Trade Grouping Specification" section that covers these edge cases explicitly. Start with simple long/short FIFO and document the cases deferred to later phases.

### 7.2 Missing Timezone Handling

Trading across IBKR (US Eastern for equities, various for futures) and Tradovate (CME/exchange time) introduces timezone complexity. The schema uses `timestamp` but does not specify timezone handling.

**Recommendation:** Store all timestamps as UTC (`timestamptz` in PostgreSQL). Normalize broker timestamps to UTC during ingestion. Display in user-local timezone in the frontend. Document the timezone contract explicitly.

### 7.3 Migration Path for Schema Changes

The design uses Alembic, which is correct. But as the schema evolves (especially the `trades` table and grouping logic), data migrations could be complex.

**Recommendation:** Add a `schema_version` to the config or a dedicated metadata table. Document that breaking schema changes require a re-import (since raw_data is preserved, this is always possible).

### 7.4 No Logging / Observability

The design mentions no application logging strategy.

**Recommendation:** Use Python `structlog` or standard `logging` with structured JSON output. Log at minimum:
- Import start/end with record counts
- Normalization errors
- Dedup skip counts
- API request latency (middleware)
- Scheduler job execution

### 7.5 Testing Strategy

The project structure shows test files but the design does not describe the testing approach.

**Recommendation:** Define:
- **Unit tests:** Normalizer mappings, dedup logic, grouping algorithm — these are pure logic and critical.
- **Integration tests:** Ingester with mock HTTP responses (use `respx` or `httpx` mocking).
- **API tests:** FastAPI `TestClient` with a test database.
- **Fixture data:** Include sample Flex XML and Tradovate JSON in `tests/fixtures/` for reproducible tests.

---

## 8. Summary of Recommendations

### Must-Fix (Before Implementation)

| # | Item | Section |
|---|------|---------|
| 1 | Bind Docker ports to `127.0.0.1` | 5.2.1 |
| 2 | Add `import_log_id` FK to trades table | 4.2.3 |
| 3 | Add index plan to schema | 4.2.1 |
| 4 | Specify timezone handling (UTC storage) | 7.2 |
| 5 | Wrap imports in database transactions | 2.2.2 |

### Should-Fix (During Phase 1)

| # | Item | Section |
|---|------|---------|
| 6 | Add basic auth middleware (API key) | 5.2.1 |
| 7 | Add `/health` endpoint and Docker healthchecks | 6.2.1 |
| 8 | Decouple trade grouping from import pipeline | 2.2.3 |
| 9 | Add data validation layer | 6.2.4 |
| 10 | Remove `net_amount` or define computation per asset class | 4.2.2 |
| 11 | Use materialized view for `daily_summaries` | 4.2.4 |
| 12 | Add CORS configuration | 5.2.3 |
| 13 | Serve frontend from backend (single container) | 3.2.2 |

### Nice-to-Have (Phase 2+)

| # | Item | Section |
|---|------|---------|
| 14 | PostgreSQL-backed scheduler | 3.2.1 |
| 15 | Backup strategy documentation | 6.2.2 |
| 16 | Structured logging | 7.4 |
| 17 | Flex Query polling circuit breaker | 6.2.3 |
| 18 | CSV dedup hash includes row number | 4.2.5 |

---

## 9. Conclusion

This is a solid design that makes appropriate tradeoffs for a single-user self-hosted system. The phased approach is realistic, the technology choices are well-justified by the research, and the architecture is clean without being over-engineered.

The most critical gaps are around security defaults (port binding, basic auth), data integrity (transactions, validation, timezone), and schema completeness (indexes, foreign keys, computed fields). All of these are straightforward to address before implementation begins.

The research report provides excellent context and the design clearly incorporates its recommendations. The decision to start with Flex Query + CSV import and defer real-time streaming is correct.
