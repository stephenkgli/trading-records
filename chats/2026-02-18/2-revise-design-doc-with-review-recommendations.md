# Revise Design Document Based on Review Recommendations

Generated final design document `design-doc-final.md` incorporating all 18 review recommendations plus 6 additional improvements.

**Must-Fix (5 items):** Docker 127.0.0.1 port binding, import_log_id FK on trades, database index plan, UTC timezone contract, transaction-wrapped imports.

**Should-Fix (8 items):** API key auth, health endpoint + healthchecks, decoupled trade grouping, data validation layer, removed net_amount (dynamic computation), materialized view for daily_summaries, CORS config, frontend served from backend.

**Nice-to-Have (5 items):** APScheduler idempotency, backup strategy, structured logging, Flex polling circuit breaker, CSV dedup hash with row number.

**Additional:** NormalizedTrade Pydantic contract, trade grouping edge case spec, uv as dependency manager, testing strategy, Tradovate credential security note, schema migration strategy.
