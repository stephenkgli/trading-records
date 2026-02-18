# Trading Records Tools Research Report

## 1. Executive Summary

This report investigates existing tools, open-source projects, and commercial products for capturing and analyzing trading records from **Interactive Brokers (IBKR)** and **Tradovate**. It covers API options, architectural patterns, data storage approaches, and analytics platforms to inform the design of a custom trading records system.

---

## 2. IBKR API Landscape

Interactive Brokers offers multiple API interfaces, each suited to different use cases.

### 2.1 TWS API (Trader Workstation API)

| Aspect | Details |
|--------|---------|
| **Protocol** | Binary socket protocol (proprietary) |
| **Connection** | TCP socket to TWS or IB Gateway (ports 7496/7497 for TWS, 4001/4002 for Gateway) |
| **Languages** | Java, C++, C#/.NET, Python, ActiveX, DDE |
| **Authentication** | Requires running TWS or IB Gateway with logged-in session |
| **Latest Version** | API 10.43 (Feb 2026) |
| **License** | Non-commercial use only |

**Key Capabilities:**
- Real-time and historical market data
- Order placement, modification, and cancellation
- Account information, positions, P&L
- Contract details and option chains
- Execution reports and commission data

**Architecture Pattern:** Event-driven, callback-based. The client connects via TCP socket to a running TWS/Gateway instance. All data flows through this single connection with multiplexed request/response patterns using request IDs.

**Trade Record Retrieval:**
- `reqExecutions()` - Retrieves execution details with filters (time, symbol, side, etc.)
- `reqCompletedOrders()` - Gets completed order history
- `execDetails` callback - Receives individual execution reports
- `commissionReport` callback - Receives commission data per execution

### 2.2 Client Portal API (Web API 1.0 / CPAPI)

| Aspect | Details |
|--------|---------|
| **Protocol** | REST (HTTPS) + WebSocket |
| **Gateway** | Requires Client Portal Gateway (Java-based local server) |
| **Authentication** | Session-based via browser login to Gateway |
| **Base URL** | `https://localhost:5000/v1/api/` |
| **Data Format** | JSON |

**Key Endpoints:**
- `GET /portfolio/{accountId}/positions` - Current positions
- `GET /iserver/account/trades` - Recent trades
- `GET /pa/performance` - Portfolio performance analytics
- `GET /portfolio/{accountId}/summary` - Account summary
- `POST /iserver/account/orders` - Place orders
- WebSocket `/ws` - Real-time market data and order updates

**Architecture Pattern:** The Client Portal Gateway runs as a local Java process. Applications make REST calls to it. The Gateway handles the session with IBKR servers. WebSocket provides real-time streaming. This is simpler than TWS API but requires maintaining the Gateway process and re-authenticating periodically (sessions expire).

### 2.3 Flex Web Service (Flex Queries)

| Aspect | Details |
|--------|---------|
| **Protocol** | REST (HTTPS) |
| **Authentication** | Token-based (Flex Web Service Token) |
| **Data Format** | XML |
| **No Gateway Required** | Direct HTTPS calls to IBKR servers |

**Key Features:**
- Pre-configured report templates via Account Management portal
- Two-step process: (1) Request report generation, (2) Download completed report
- Covers: Trades, Transfers, Cash Transactions, Open Positions, etc.
- Historical data access (up to 365 days)
- Batch-friendly for automated daily downloads

**API Flow:**
```
1. POST https://gdcdyn.interactivebrokers.com/Universal/servlet/FlexStatement.SendRequest
   Params: t={token}&q={queryId}&v=3
   Returns: <FlexStatementResponse><ReferenceCode>...</ReferenceCode></FlexStatementResponse>

2. GET https://gdcdyn.interactivebrokers.com/Universal/servlet/FlexStatement.GetStatement
   Params: t={token}&q={referenceCode}&v=3
   Returns: XML report data
```

**Best for:** Automated daily/weekly trade record downloads without requiring TWS or Gateway to be running.

### 2.4 IBKR API Comparison Summary

| Feature | TWS API | Client Portal API | Flex Web Service |
|---------|---------|-------------------|-----------------|
| Real-time data | Yes | Yes (WebSocket) | No |
| Historical trades | Yes (limited) | Yes (recent) | Yes (up to 365 days) |
| Requires TWS/Gateway | Yes | Yes (CP Gateway) | No |
| Protocol | Binary Socket | REST + WebSocket | REST |
| Data format | Binary/Objects | JSON | XML |
| Authentication | TWS session | Browser login | Token |
| Headless operation | Via IB Gateway | Via IBeam | Native |
| Best for | Real-time trading | Web apps | Batch reporting |

---

## 3. Tradovate API

### 3.1 API Overview

| Aspect | Details |
|--------|---------|
| **Protocol** | REST (HTTPS) + WebSocket |
| **Base URL** | `https://live.tradovateapi.com/v1` (live), `https://demo.tradovateapi.com/v1` (demo) |
| **Authentication** | OAuth-style access tokens |
| **Data Format** | JSON |
| **Rate Limiting** | Token request frequency limits enforced |

### 3.2 Authentication

Tradovate uses an access token system:

```
POST /auth/accesstokenrequest
Body: {
  "name": "username",
  "password": "password",
  "appId": "app-name",
  "appVersion": "1.0",
  "deviceId": "unique-device-id",
  "cid": client_id,
  "sec": client_secret
}
Returns: { "accessToken": "...", "expirationTime": "..." }
```

- Tokens have a limited lifespan and must be refreshed
- Device ID is generated per installation
- API discourages frequent token requests
- Separate endpoints for live vs demo environments

### 3.3 Key REST Endpoints

| Category | Endpoint | Description |
|----------|----------|-------------|
| **Account** | `GET /account/list` | List all accounts |
| **Positions** | `GET /position/list` | Current positions |
| **Orders** | `POST /order/placeorder` | Place orders |
| **Orders** | `GET /order/list` | List orders |
| **Fills** | `GET /fill/list` | Order fill history |
| **Fills** | `GET /fill/ldeps` | Fill details with dependencies |
| **Contracts** | `GET /contract/find` | Find contract specs |
| **Cash Balances** | `GET /cashBalance/list` | Account cash balances |

### 3.4 WebSocket API

- Real-time market data streaming
- Order status updates
- Position change notifications
- Uses standard WebSocket protocol with JSON messages

### 3.5 Important Limitations

- **CME Licensing (2023+):** CME implemented expensive licensing requirements ($400+/month) for individual API users accessing market data, impacting real-time data feeds
- **Limited ecosystem:** Far fewer third-party libraries compared to IBKR
- **Documentation:** API docs are JavaScript-rendered (SPA), harder to programmatically parse

---

## 4. Open-Source Projects Analysis

### 4.1 IBKR Ecosystem

#### ib_insync / ib_async (Python)
- **Stars:** ~1,400 (ib_async, successor)
- **Status:** Actively maintained (latest: v2.1.0, Dec 2025)
- **Architecture:** asyncio-based event-driven framework
- **Key Design Patterns:**
  - Single `IB` class as the main interface
  - Automatic synchronization of IB components
  - Event subscription pattern (e.g., `ib.orderStatusEvent += handler`)
  - Internal implementation of IBKR binary protocol (no ibapi dependency)
  - Sync and async modes supported
  - Native pandas DataFrame conversion
- **Trade Record Features:**
  - `ib.trades()` - Get all trades
  - `ib.fills()` - Get execution fills
  - `ib.positions()` - Get positions
  - `ib.accountValues()` - Account data
  - Event-driven real-time updates

**Architecture Takeaway:** Clean Pythonic API wrapping complex socket protocol. Event-driven pattern is ideal for real-time data capture.

#### IBeam (Python)
- **Stars:** 775
- **Purpose:** Authentication automation for Client Portal API Gateway
- **Architecture:**
  - Uses Selenium + Chrome Driver for automated login
  - Pyvirtualdisplay for headless operation
  - Docker-first deployment model
  - Continuous session monitoring and re-authentication
  - Exposes Gateway at `localhost:5000`
- **Design Pattern:** Sidecar container pattern - runs alongside your application to handle authentication

#### IBind (Python)
- **Stars:** 374
- **Purpose:** REST + WebSocket client for Client Portal Web API
- **Architecture:**
  - `IbkrClient` class for REST operations
  - `IbkrWsClient` class for WebSocket streaming
  - Thread-safe queue-based data streams
  - OAuth 1.0a support for headless authentication
  - Built-in rate limiting and retry logic
  - Automated question/answer handling for API prompts
- **Design Pattern:** Dual-client architecture separating sync (REST) and async (WebSocket) concerns

#### IB Flex Reporter (C#)
- **Purpose:** Query Flex API and build reports
- **Architecture:** Downloads XML Flex reports, parses them, generates visualizations

#### IB_Flex (Python, archived)
- **Purpose:** Download and analyze Flex Query reports
- **Components:** XML downloader, data importer, Highcharts visualization

### 4.2 Tradovate Ecosystem

#### Tradovate-Python-Client
- **Stars:** Low (small project)
- **Status:** Last updated June 2023
- **Architecture:**
  - Individual script files per function (procedural style)
  - `config.py` for centralized credentials
  - Separate scripts: `GetAccessToken.py`, `PlaceMarketOrder.py`, `GetFillList.py`, etc.
  - Boolean "live" parameter to switch demo/live environments
- **Limitations:** Not a proper library; more of a collection of scripts. Non-standard Python patterns.

**Architecture Takeaway:** Tradovate's ecosystem is immature. Building a proper client library would be necessary.

### 4.3 General Trading Infrastructure

#### IB Gateway Docker (Various)
- Multiple projects containerizing IB Gateway for headless deployment
- Pattern: Docker + IBC (IB Controller) for automated startup and authentication
- Used as infrastructure layer beneath trading applications

---

## 5. Commercial Trading Journal Platforms

### 5.1 TradesViz

| Aspect | Details |
|--------|---------|
| **Users** | 100,000+ active traders |
| **Trades Processed** | 50M+ |
| **Pricing** | Free / $19/mo Pro / $29/mo Platinum |

**Key Features:**
- 600+ interactive statistics and visualizations
- AI-powered Q&A on trading data
- Auto-sync with 30+ brokers (including IBKR and Tradovate)
- CSV/XLSX import for 100+ brokers
- Interactive TradingView charts with trade overlays
- Custom dashboards with drag-and-drop widgets
- Options flow analysis and screener
- Monte Carlo risk simulation
- Trading simulator with 15,000+ tickers

**Architecture Insights:**
- Cloud-based SaaS platform
- Auto-sync implies server-side broker API integrations
- Supports both real-time sync and batch file import
- Heavy use of interactive charting (TradingView integration)
- AI features suggest server-side LLM integration
- Multi-account, multi-broker aggregation

**Data Import Methods:**
1. Auto-sync (direct broker API integration)
2. File upload (CSV, XLSX, XLS, TXT)
3. Google Drive sync
4. Manual entry

### 5.2 Tradervue

| Aspect | Details |
|--------|---------|
| **Users** | 207,623 |
| **Markets** | Stocks, Futures, Forex |
| **Integrations** | 80+ trading platforms |

**Key Features:**
- Automatic trade import from 80+ platforms (including IBKR)
- TradingView chart integration with trade overlays
- Exit performance analysis (actual vs theoretical best exit)
- Daily P&L candle graphs
- Tag and filter system
- Calendar view
- Customizable dashboard

**Architecture Insights:**
- Web-based platform
- File-based import (broker execution reports)
- Simpler than TradesViz but more focused
- Strong charting integration

### 5.3 Edgewonk

| Aspect | Details |
|--------|---------|
| **History** | 10+ years, 7M+ trades journaled |
| **Markets** | Forex, Futures, Stocks, Crypto, Options |
| **Pricing** | Premium (specific pricing not disclosed publicly) |

**Key Features:**
- AI-driven "Edge Finder" algorithm (weekly automated analysis)
- Imports 1,000+ trades in 12 seconds
- 200+ broker support
- Rule break detection and cost quantification
- Mindset/emotion tracking linked to trade data
- Exit analysis optimization

**Architecture Insights:**
- Cloud-based platform
- Proprietary AI/ML analysis engine
- Focus on behavioral analysis (not just raw statistics)
- Weekly batch analysis pattern

### 5.4 Platform Comparison

| Feature | TradesViz | Tradervue | Edgewonk |
|---------|-----------|-----------|----------|
| IBKR support | Auto-sync | File import | File import |
| Tradovate support | Auto-sync | Limited | File import |
| Statistics | 600+ | ~50 | ~100 |
| AI features | Yes (Q&A, summary) | No | Yes (Edge Finder) |
| Free tier | Yes (3K trades/mo) | Yes (basic) | No |
| Simulator | Yes | No | No |
| Options analysis | Yes | Basic | Basic |
| Self-hosted option | No | No | No |

---

## 6. Architecture Patterns and Best Practices

### 6.1 Data Acquisition Patterns

**Pattern 1: Real-time Event Streaming**
```
TWS/Gateway  -->  Socket/WebSocket Client  -->  Event Handler  -->  Database
                                                    |
                                            Trade Event Queue
```
- Used by: ib_async, IBind (WebSocket mode)
- Best for: Live trading monitoring, real-time P&L tracking
- Pros: Immediate data capture, no missed trades
- Cons: Requires always-running connection

**Pattern 2: Batch Report Download**
```
Scheduler (cron)  -->  Flex Query API  -->  XML Parser  -->  Database
                                                              |
                                                      Deduplication Layer
```
- Used by: IB_Flex, ibflexreporter
- Best for: Daily/weekly trade record archival
- Pros: No persistent connection needed, historical data access
- Cons: Not real-time, requires IBKR Flex token setup

**Pattern 3: File Import Pipeline**
```
Broker Export (CSV/XLSX)  -->  Parser/Normalizer  -->  Database
                                     |
                              Format Detection
                              Field Mapping
                              Data Validation
```
- Used by: All commercial platforms (TradesViz, Tradervue, Edgewonk)
- Best for: Universal broker support, user-driven import
- Pros: Works with any broker, no API dependency
- Cons: Manual process, potential parsing errors

**Pattern 4: Hybrid (Recommended)**
```
                    +-- Real-time Stream (WebSocket) --+
                    |                                   |
Broker APIs --------+-- Scheduled Batch (Flex/REST) ---+--> Unified Data Store
                    |                                   |
                    +-- Manual Import (CSV) ------------+
                              |
                      Normalization Layer
                      (unified trade schema)
```

### 6.2 Data Storage Patterns

**Observed in open-source projects:**
- **SQLite:** Simple, embedded, good for single-user desktop apps
- **PostgreSQL:** Preferred for web applications with complex queries
- **pandas DataFrames:** In-memory analysis, notebook workflows
- **CSV/Parquet:** File-based storage for data science workflows

**Recommended Schema Core:**
```
trades
  - id (uuid)
  - broker (enum: ibkr, tradovate)
  - account_id (string)
  - symbol (string)
  - asset_class (enum: stock, future, option, forex)
  - side (enum: buy, sell)
  - quantity (decimal)
  - price (decimal)
  - commission (decimal)
  - execution_time (timestamp)
  - order_id (string)
  - exchange (string)
  - currency (string)
  - raw_data (jsonb)  -- preserve original broker data

positions (derived)
  - aggregated from trades
  - entry/exit matching logic

daily_summary (materialized)
  - daily P&L, win rate, trade count
```

### 6.3 Authentication Patterns

| Broker | Pattern | Complexity |
|--------|---------|------------|
| IBKR TWS API | Running TWS/Gateway + session | High (needs GUI or headless setup) |
| IBKR Client Portal | Browser login + session cookie | Medium (IBeam automates this) |
| IBKR Flex Query | Static token | Low (set once in Account Mgmt) |
| Tradovate | OAuth access token + refresh | Medium (standard OAuth flow) |

**Best Practice:** Use Flex Query for historical IBKR data (simplest auth) and Tradovate REST API with stored tokens for Tradovate data. Use WebSocket connections only when real-time streaming is needed.

### 6.4 Frontend Architecture Patterns

**Observed across commercial platforms:**
- **Charting:** TradingView widget integration (TradesViz, Tradervue) or custom D3/Chart.js
- **Dashboards:** Drag-and-drop widget systems with customizable layouts
- **Calendar View:** Monthly P&L heatmap (universal feature across all platforms)
- **Tables:** Sortable, filterable trade tables with column customization
- **Analytics:** Statistical charts (win rate, P&L distribution, time-of-day analysis)

**Tech Stack Patterns:**
- React/Next.js for frontend (most common in modern platforms)
- Python backend for data processing and analysis
- REST API layer between frontend and backend
- WebSocket for real-time updates

---

## 7. Key Findings and Recommendations

### 7.1 For IBKR Integration

1. **Primary data source:** Use **Flex Web Service** for trade history - it's the most reliable, requires no running gateway, and provides comprehensive historical data in XML format
2. **Real-time supplement:** Use **Client Portal API** via IBind for real-time position/P&L monitoring when needed
3. **Avoid TWS API complexity** unless algorithmic trading features are required - it's overkill for trade record collection
4. **Leverage ib_async** if deeper TWS integration is needed - it's the best-maintained Python library (1.4K stars, active development)

### 7.2 For Tradovate Integration

1. **Build a proper REST client** - existing open-source options are immature
2. **Key endpoints:** `/fill/list` for trade fills, `/position/list` for positions, `/account/list` for account data
3. **Token management:** Implement proper token refresh logic (tokens expire, and Tradovate rate-limits token requests)
4. **Be aware of CME licensing costs** for real-time market data via API

### 7.3 Architecture Recommendations

1. **Use a unified trade schema** that normalizes data from both brokers
2. **Implement the Hybrid data acquisition pattern** (batch + real-time + manual import)
3. **Store raw broker data** alongside normalized data for debugging and reprocessing
4. **Start with Flex Query (IBKR) + REST API (Tradovate)** for initial implementation
5. **Add WebSocket streaming** as a Phase 2 enhancement for real-time monitoring
6. **Consider PostgreSQL** for the data store - handles complex analytical queries well and supports JSONB for raw data storage

### 7.4 Gap Analysis: Why Build Custom

None of the existing commercial platforms (TradesViz, Tradervue, Edgewonk) offer:
- Self-hosted deployment
- Full data ownership and control
- Custom analysis beyond their built-in statistics
- Direct API access to your trade data
- Integration with custom trading systems
- Automated strategy tagging based on custom rules

A custom solution fills this gap by providing full control over data pipeline, analysis, and presentation while using the best architectural patterns observed in existing tools.

---

## 8. Reference Links

### IBKR API Resources
- TWS API: https://interactivebrokers.github.io/
- ib_async (successor to ib_insync): https://github.com/ib-api-reloaded/ib_async
- IBeam (CP Gateway automation): https://github.com/Voyz/ibeam
- IBind (CP API client): https://github.com/Voyz/ibind
- IB Gateway Docker: https://github.com/UnusualAlpha/ib-gateway-docker
- IB Flex Reporter: https://github.com/dmkoster/ibflexreporter
- IBKR API topic on GitHub: https://github.com/topics/ibkr-api (35 repositories)

### Tradovate Resources
- Tradovate API Docs: https://api.tradovate.com/
- Tradovate Python Client: https://github.com/nomad4x/Tradovate-Python-Client
- Tradovate Community Forum: https://community.tradovate.com/c/api-developers/15

### Commercial Platforms
- TradesViz: https://www.tradesviz.com/
- Tradervue: https://www.tradervue.com/
- Edgewonk: https://edgewonk.com/

### Other Open-Source Trading Tools
- Trading Journal (Flask): https://github.com/awindsr/Trading-Journal
- IBKR MCP Server: https://github.com/code-rabi/interactive-brokers-mcp
