# Release v0.6.50 - Top 10 QA/UX Improvements & New Features

**Release Date**: 2026-05-19

## Overview

This release addresses the Top 10 Admin Panel issues and adds 2 major new features: Agentic Intelligent Investment Research Workflow and Multi-Factor Dynamic Attribution Sandbox.

## Breaking Changes

None. All changes are backward compatible.

## New Features

### 1. Agentic Intelligent Investment Research Workflow

Natural language task orchestration for multi-step investment research.

**Architecture**:
```
User Query → QueryClassifier → WorkflowEngine → ToolRegistry → LLM → ReportGenerator
```

**Features**:
- 7 built-in tools: `get_quote`, `get_news`, `get_financial`, `get_kline`, `search_stocks`, `get_sector_stocks`, `get_macro_data`
- Intent parsing using QueryClassifier
- Markdown report generation
- Real-time progress tracking

**API Endpoints**:
```bash
# List available tools
GET /api/v1/agentic/tools

# Create and execute workflow
POST /api/v1/agentic/workflow
{
  "query": "分析茅台最新行情和新闻",
  "execute": true
}

# Get workflow status
GET /api/v1/agentic/workflow/{workflow_id}
```

### 2. Multi-Factor Dynamic Attribution Sandbox

Drag-and-drop factor combination for real-time attribution analysis.

**Features**:
- 22 predefined factors across 7 categories
- OLS regression with R², t-statistics, p-values
- Real-time calculation and visualization
- Factor contribution breakdown

**Factor Categories**:
| Category | Factors |
|----------|---------|
| Value | PE, PB, PS |
| Growth | ROE, ROA, REVENUE_GROWTH, PROFIT_GROWTH |
| Quality | GROSS_MARGIN, NET_MARGIN, DEBT_RATIO |
| Momentum | PRICE_MOMENTUM_1M, PRICE_MOMENTUM_3M, PRICE_MOMENTUM_6M |
| Technical | MA5, MA20, MACD, RSI, BOLL |
| Volatility | VOLATILITY_20D, TURNOVER_RATE |
| Sentiment | NEWS_SENTIMENT, ANALYST_RATING |

**API Endpoints**:
```bash
# List all factors
GET /api/v1/attribution/factors

# List categories
GET /api/v1/attribution/factors/categories

# Run attribution analysis
POST /api/v1/attribution/sandbox
{
  "symbols": ["sh600519"],
  "factors": ["PE", "ROE", "MACD"],
  "start_date": "2023-01-01",
  "end_date": "2024-01-01"
}
```

## Bug Fixes

### P0 Critical

| Issue | Fix | Impact |
|-------|-----|--------|
| Admin session memory storage | SQLite persistence + background cleanup | Sessions survive restarts |
| VACUUM blocking all APIs | Background thread + WebSocket progress | Non-blocking maintenance |
| IP spoofing bypass rate limit | Trusted proxy CIDR validation | Prevents rate limit bypass |
| WAL checkpoint not implemented | `PRAGMA wal_checkpoint(TRUNCATE)` API | Frontend button now works |
| WebSocket zombie connections | Heartbeat detection + connection limit (100) | Prevents resource leaks |

### P1 High Priority

| Issue | Fix | Impact |
|-------|-----|--------|
| alert() blocking JS thread | Toast notifications | Better UX |
| isSubmitting permanent lock | 30-second timeout protection | Auto-unlock |
| Tab switch losing input | v-if → v-show (keep-alive) | Preserves input state |
| dbStatus hardcoded fake data | Real data fetching + error state | Accurate status display |

### Mobile Navigation

| Issue | Fix | Impact |
|-------|-----|--------|
| Missing 3 sections on mobile | Added forex, research, walk-forward to more menu | Full feature parity |

## Files Changed

### Backend (17 files)

**New Files**:
- `backend/app/routers/agentic.py` - Agentic workflow API
- `backend/app/routers/attribution.py` - Attribution API
- `backend/app/services/agentic/tool_registry.py` - Tool registry
- `backend/app/services/agentic/workflow_engine.py` - Workflow engine
- `backend/app/services/attribution/factor_registry.py` - Factor registry (22 factors)
- `backend/app/services/attribution/attribution_engine.py` - Attribution engine
- `backend/app/services/background_tasks.py` - Background task manager
- `backend/app/utils/ip_validation.py` - IP validation utility
- `backend/tests/unit/test_utils/test_ip_validation.py` - IP validation tests (28 tests)

**Modified Files**:
- `backend/app/db/database.py` - Admin sessions table
- `backend/app/db/session_db.py` - Admin session CRUD
- `backend/app/main.py` - Router registration
- `backend/app/middleware/rate_limit.py` - Safe IP extraction
- `backend/app/routers/admin.py` - VACUUM background + WAL checkpoint
- `backend/app/services/ws_manager.py` - Connection limit
- `backend/requirements.txt` - Added scipy, numpy

### Frontend (6 files)

**New Files**:
- `frontend/src/components/AgenticWorkflow.vue` - Agentic workflow panel
- `frontend/src/components/attribution/FactorSandbox.vue` - Factor sandbox panel

**Modified Files**:
- `frontend/src/components/AdminDashboard.vue` - Toast + timeout + keep-alive
- `frontend/src/components/MobileBottomNav.vue` - Added 3 sections
- `frontend/src/components/StrategyCenter.vue` - Attribution tab
- `frontend/src/components/admin/DatabasePanel.vue` - Progress display

## Verification

```bash
# Agentic workflow
curl http://localhost:60100/api/v1/agentic/tools

# Attribution sandbox
curl http://localhost:60100/api/v1/attribution/factors

# Admin session persistence
sqlite3 database.db "SELECT * FROM admin_sessions"

# WAL checkpoint
curl -X POST http://localhost:60100/api/v1/admin/database/maintenance \
  -H "Content-Type: application/json" -d '{"action": "wal_checkpoint"}'

# IP validation tests
pytest backend/tests/unit/test_utils/test_ip_validation.py -v

# Mobile navigation
grep -c "forex" frontend/src/components/MobileBottomNav.vue  # Expected: 1
grep -c "research" frontend/src/components/MobileBottomNav.vue  # Expected: 1
grep -c "walk-forward" frontend/src/components/MobileBottomNav.vue  # Expected: 1
```

## Upgrade Notes

1. **Database**: New `admin_sessions` table created automatically
2. **Environment**: Set `TRUSTED_PROXIES` for IP validation (default: private networks)
3. **Dependencies**: Added scipy, numpy for attribution calculations
4. **Frontend**: Rebuild required for new components

## Known Issues

None identified in this release.

## Contributors

- Development Team - Implementation and testing
- QA Team - Issue identification

## Next Release

v0.6.51 will focus on:
- Event-driven scenario engine
- Visual node-based strategy builder
- Alternative data parser
