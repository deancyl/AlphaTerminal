# AlphaTerminal QuantDinger Integration - 20 Development Tasks

> Date: 2026-05-09
> Version: v0.6.12
> Status: Planning Phase
> Reference: QUANTDINGER_INTEGRATION_REPORT.md

---

## Overview

Based on the comprehensive analysis in QUANTDINGER_INTEGRATION_REPORT.md, we will implement 20 development tasks to integrate key features from QuantDinger and awesome-quant into AlphaTerminal. Each task includes development, testing, and a debug cycle.

---

## Task Structure

Each task follows this pattern:
1. **Development**: Implement the feature
2. **Testing**: Write and run tests
3. **Debug**: Set up debug logging, analyze logs, fix issues
4. **Verification**: Confirm feature works end-to-end

---

## 20 Development Tasks

### Task 1: Agent Token System - Core Infrastructure

**Priority**: P0 (Critical)
**Estimated Time**: 2 days
**Dependencies**: None

#### Development
- Create `backend/app/services/agent/token_service.py`
- Implement `AgentToken` data model with scopes (R/W/B/N/C/T)
- Implement token creation, verification, revocation
- Add SHA256 hashing for token storage
- Add expiration and rate limiting

#### Testing
- Unit tests for token creation/verification
- Integration tests for token lifecycle
- Security tests for token hashing

#### Debug Setup
```python
# Add to token_service.py
import logging
logger = logging.getLogger("agent.token")

def create_token(...):
    logger.info(f"[TokenService] Creating token: name={name}, scopes={scopes}")
    try:
        # ... implementation
        logger.info(f"[TokenService] Token created: prefix={token_prefix}, expires={expires_at}")
    except Exception as e:
        logger.error(f"[TokenService] Token creation failed: {e}", exc_info=True)
        raise
```

#### Success Criteria
- Token creation returns valid token string
- Token verification works correctly
- Expired tokens are rejected
- Rate limiting enforced

---

### Task 2: Agent Token Database Schema

**Priority**: P0 (Critical)
**Estimated Time**: 1 day
**Dependencies**: Task 1

#### Development
- Create `backend/app/db/agent_db.py`
- Define `agent_tokens` table schema
- Define `agent_audit_logs` table schema
- Implement CRUD operations
- Add indexes for performance

#### Testing
- Database migration tests
- CRUD operation tests
- Index performance tests

#### Debug Setup
```python
# Add to agent_db.py
logger = logging.getLogger("agent.db")

async def save_token(token: AgentToken):
    logger.debug(f"[AgentDB] Saving token: id={token.id}, prefix={token.token_prefix}")
    try:
        # ... implementation
        logger.debug(f"[AgentDB] Token saved successfully")
    except Exception as e:
        logger.error(f"[AgentDB] Failed to save token: {e}", exc_info=True)
        raise
```

#### Success Criteria
- Tables created successfully
- CRUD operations work
- Indexes improve query performance

---

### Task 3: Agent Authentication Middleware

**Priority**: P0 (Critical)
**Estimated Time**: 1 day
**Dependencies**: Task 1, Task 2

#### Development
- Create `backend/app/middleware/agent_auth.py`
- Implement Bearer token extraction
- Implement scope checking
- Add request context injection
- Add audit logging

#### Testing
- Middleware unit tests
- Scope enforcement tests
- Invalid token rejection tests

#### Debug Setup
```python
# Add to agent_auth.py
logger = logging.getLogger("agent.auth")

async def verify_agent_token(authorization: str = Header(...)):
    logger.debug(f"[AgentAuth] Verifying token: auth_header_prefix={authorization[:20] if authorization else None}")
    try:
        # ... implementation
        logger.debug(f"[AgentAuth] Token verified: scopes={token.scopes}")
    except HTTPException as e:
        logger.warning(f"[AgentAuth] Token verification failed: status={e.status_code}, detail={e.detail}")
        raise
```

#### Success Criteria
- Valid tokens accepted
- Invalid tokens rejected with 401
- Missing scopes rejected with 403
- Audit logs created

---

### Task 4: Agent API Router - Market Data Endpoints

**Priority**: P0 (Critical)
**Estimated Time**: 2 days
**Dependencies**: Task 3

#### Development
- Extend `backend/app/routers/agent.py`
- Implement `/api/agent/v1/health`
- Implement `/api/agent/v1/whoami`
- Implement `/api/agent/v1/markets`
- Implement `/api/agent/v1/markets/{market}/symbols`
- Implement `/api/agent/v1/klines`
- Implement `/api/agent/v1/price`

#### Testing
- Endpoint integration tests
- Scope enforcement tests
- Rate limiting tests

#### Debug Setup
```python
# Add to agent.py
logger = logging.getLogger("agent.router")

@router.get("/markets")
async def list_markets(token: dict = Depends(verify)):
    logger.info(f"[AgentAPI] list_markets called: token_prefix={token['token_prefix']}")
    try:
        markets = await get_available_markets(token)
        logger.debug(f"[AgentAPI] Returning {len(markets)} markets")
        return markets
    except Exception as e:
        logger.error(f"[AgentAPI] list_markets failed: {e}", exc_info=True)
        raise
```

#### Success Criteria
- All endpoints return valid responses
- Scope enforcement works
- Rate limiting applied

---

### Task 5: Agent API Router - Strategy Endpoints

**Priority**: P0 (Critical)
**Estimated Time**: 1 day
**Dependencies**: Task 4

#### Development
- Implement `/api/agent/v1/strategies` (list)
- Implement `/api/agent/v1/strategies/{id}` (get)
- Add strategy filtering by market
- Add pagination support

#### Testing
- Strategy listing tests
- Strategy detail retrieval tests
- Filtering and pagination tests

#### Debug Setup
```python
@router.get("/strategies")
async def list_strategies(token: dict = Depends(verify), market: str = None, limit: int = 20):
    logger.info(f"[AgentAPI] list_strategies: market={market}, limit={limit}")
    try:
        strategies = await get_strategies(token, market, limit)
        logger.debug(f"[AgentAPI] Returning {len(strategies)} strategies")
        return strategies
    except Exception as e:
        logger.error(f"[AgentAPI] list_strategies failed: {e}", exc_info=True)
        raise
```

#### Success Criteria
- Strategies listed correctly
- Filtering works
- Pagination implemented

---

### Task 6: Agent API Router - Backtest Endpoints

**Priority**: P0 (Critical)
**Estimated Time**: 2 days
**Dependencies**: Task 5

#### Development
- Implement `/api/agent/v1/backtests` (submit)
- Implement `/api/agent/v1/jobs/{id}` (status)
- Add job queue integration
- Add async task processing

#### Testing
- Backtest submission tests
- Job status polling tests
- Async processing tests

#### Debug Setup
```python
@router.post("/backtests")
async def submit_backtest(request: BacktestRequest, token: dict = Depends(verify)):
    logger.info(f"[AgentAPI] submit_backtest: strategy={request.strategy_id}, symbol={request.symbol}")
    try:
        job_id = await submit_backtest_job(request, token)
        logger.info(f"[AgentAPI] Backtest job created: job_id={job_id}")
        return {"job_id": job_id, "status": "pending"}
    except Exception as e:
        logger.error(f"[AgentAPI] submit_backtest failed: {e}", exc_info=True)
        raise
```

#### Success Criteria
- Backtest jobs submitted
- Job status tracked
- Results retrievable

---

### Task 7: MCP Server - Core Framework

**Priority**: P0 (Critical)
**Estimated Time**: 2 days
**Dependencies**: Task 4, Task 5, Task 6

#### Development
- Create `backend/mcp_server/` directory
- Install `mcp` package
- Create `server.py` with FastMCP
- Implement tool listing
- Implement tool calling
- Add environment variable configuration

#### Testing
- MCP server startup tests
- Tool listing tests
- Tool execution tests

#### Debug Setup
```python
# backend/mcp_server/src/server.py
import logging
logger = logging.getLogger("mcp.server")

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[dict]:
    logger.info(f"[MCPServer] Tool called: name={name}, args={arguments}")
    try:
        result = await execute_tool(name, arguments)
        logger.debug(f"[MCPServer] Tool result: {result}")
        return result
    except Exception as e:
        logger.error(f"[MCPServer] Tool execution failed: {e}", exc_info=True)
        raise
```

#### Success Criteria
- MCP server starts
- Tools listed correctly
- Tools execute successfully

---

### Task 8: MCP Server - Market Data Tools

**Priority**: P0 (Critical)
**Estimated Time**: 1 day
**Dependencies**: Task 7

#### Development
- Implement `get_market_data` tool
- Implement `search_symbols` tool
- Implement `get_price` tool
- Add error handling
- Add response formatting

#### Testing
- Tool execution tests
- Error handling tests
- Response format tests

#### Debug Setup
```python
async def get_market_data(market: str, symbol: str, timeframe: str = "1D") -> dict:
    logger.info(f"[MCPTool] get_market_data: market={market}, symbol={symbol}, tf={timeframe}")
    try:
        data = await fetch_klines(market, symbol, timeframe)
        logger.debug(f"[MCPTool] Fetched {len(data)} candles")
        return data
    except Exception as e:
        logger.error(f"[MCPTool] get_market_data failed: {e}", exc_info=True)
        raise
```

#### Success Criteria
- Tools return valid data
- Errors handled gracefully
- Response format correct

---

### Task 9: MCP Server - Strategy Tools

**Priority**: P1 (High)
**Estimated Time**: 1 day
**Dependencies**: Task 7

#### Development
- Implement `list_strategies` tool
- Implement `get_strategy` tool
- Implement `submit_backtest` tool
- Implement `get_job_status` tool

#### Testing
- Strategy tool tests
- Backtest submission tests
- Job status tests

#### Debug Setup
```python
async def list_strategies(market: str = None) -> list:
    logger.info(f"[MCPTool] list_strategies: market={market}")
    try:
        strategies = await fetch_strategies(market)
        logger.debug(f"[MCPTool] Returning {len(strategies)} strategies")
        return strategies
    except Exception as e:
        logger.error(f"[MCPTool] list_strategies failed: {e}", exc_info=True)
        raise
```

#### Success Criteria
- Strategies listed
- Backtest submitted
- Job status retrieved

---

### Task 10: Strategy Framework - IndicatorStrategy DSL Parser

**Priority**: P1 (High)
**Estimated Time**: 3 days
**Dependencies**: None

#### Development
- Create `backend/app/services/strategy/indicator_strategy.py`
- Implement DSL parser for `# @param`, `# @strategy` annotations
- Implement code execution sandbox
- Implement output validation
- Add security restrictions

#### Testing
- Parser unit tests
- Execution tests
- Security tests

#### Debug Setup
```python
# backend/app/services/strategy/indicator_strategy.py
logger = logging.getLogger("strategy.indicator")

def parse_strategy_code(code: str) -> StrategySpec:
    logger.info(f"[IndicatorStrategy] Parsing strategy code: length={len(code)}")
    try:
        spec = extract_annotations(code)
        logger.debug(f"[IndicatorStrategy] Parsed: name={spec.name}, params={spec.parameters}")
        return spec
    except Exception as e:
        logger.error(f"[IndicatorStrategy] Parse failed: {e}", exc_info=True)
        raise

def execute_strategy(code: str, df: pd.DataFrame) -> dict:
    logger.info(f"[IndicatorStrategy] Executing strategy: df_shape={df.shape}")
    try:
        result = safe_execute(code, df)
        logger.debug(f"[IndicatorStrategy] Execution result: keys={result.keys()}")
        return result
    except Exception as e:
        logger.error(f"[IndicatorStrategy] Execution failed: {e}", exc_info=True)
        raise
```

#### Success Criteria
- Annotations parsed correctly
- Code executed safely
- Output validated

---

### Task 11: Strategy Framework - ScriptStrategy Runtime

**Priority**: P1 (High)
**Estimated Time**: 3 days
**Dependencies**: Task 10

#### Development
- Create `backend/app/services/strategy/script_strategy.py`
- Implement `on_init`, `on_bar` event handlers
- Implement `StrategyContext` with position management
- Implement `buy`, `sell`, `close_position` methods
- Add order tracking

#### Testing
- Event handler tests
- Position management tests
- Order execution tests

#### Debug Setup
```python
# backend/app/services/strategy/script_strategy.py
logger = logging.getLogger("strategy.script")

class ScriptStrategy:
    def on_bar(self, ctx: StrategyContext, bar: pd.Series):
        logger.debug(f"[ScriptStrategy] on_bar: timestamp={bar.name}, close={bar['close']}")
        try:
            # Execute user code
            self._namespace['on_bar'](ctx, bar)
            logger.debug(f"[ScriptStrategy] Position after bar: {ctx.position}")
        except Exception as e:
            logger.error(f"[ScriptStrategy] on_bar failed: {e}", exc_info=True)
            raise
```

#### Success Criteria
- Event handlers called correctly
- Position managed correctly
- Orders tracked

---

### Task 12: Strategy Router - CRUD Operations

**Priority**: P1 (High)
**Estimated Time**: 2 days
**Dependencies**: Task 10, Task 11

#### Development
- Extend `backend/app/routers/strategy.py`
- Implement strategy creation endpoint
- Implement strategy update endpoint
- Implement strategy deletion endpoint
- Implement strategy versioning
- Add validation

#### Testing
- CRUD operation tests
- Versioning tests
- Validation tests

#### Debug Setup
```python
# backend/app/routers/strategy.py
logger = logging.getLogger("strategy.router")

@router.post("/")
async def create_strategy(strategy: StrategyCreate):
    logger.info(f"[StrategyAPI] Creating strategy: name={strategy.name}, type={strategy.type}")
    try:
        created = await save_strategy(strategy)
        logger.info(f"[StrategyAPI] Strategy created: id={created.id}")
        return created
    except Exception as e:
        logger.error(f"[StrategyAPI] Create failed: {e}", exc_info=True)
        raise
```

#### Success Criteria
- Strategies created
- Strategies updated
- Strategies deleted
- Versions tracked

---

### Task 13: Performance Analyzer - Core Metrics

**Priority**: P1 (High)
**Estimated Time**: 2 days
**Dependencies**: None

#### Development
- Extend `backend/app/services/performance_analyzer.py`
- Implement return calculations (total, annual, monthly)
- Implement risk metrics (Sharpe, Sortino, Calmar)
- Implement drawdown analysis
- Implement win rate and profit factor

#### Testing
- Return calculation tests
- Risk metric tests
- Drawdown tests

#### Debug Setup
```python
# backend/app/services/performance_analyzer.py
logger = logging.getLogger("performance.analyzer")

def calculate_metrics(returns: pd.Series) -> dict:
    logger.info(f"[PerfAnalyzer] Calculating metrics: returns_length={len(returns)}")
    try:
        metrics = {
            "total_return": calc_total_return(returns),
            "sharpe_ratio": calc_sharpe(returns),
            "max_drawdown": calc_max_drawdown(returns)
        }
        logger.debug(f"[PerfAnalyzer] Metrics calculated: {metrics}")
        return metrics
    except Exception as e:
        logger.error(f"[PerfAnalyzer] Calculation failed: {e}", exc_info=True)
        raise
```

#### Success Criteria
- All metrics calculated
- Values accurate
- Edge cases handled

---

### Task 14: Performance Router - API Endpoints

**Priority**: P1 (High)
**Estimated Time**: 1 day
**Dependencies**: Task 13

#### Development
- Extend `backend/app/routers/performance.py`
- Implement `/api/v1/performance/analyze` endpoint
- Implement `/api/v1/performance/compare` endpoint
- Add benchmark comparison
- Add report generation

#### Testing
- Analysis endpoint tests
- Comparison tests
- Report generation tests

#### Debug Setup
```python
# backend/app/routers/performance.py
logger = logging.getLogger("performance.router")

@router.post("/analyze")
async def analyze_performance(request: PerformanceRequest):
    logger.info(f"[PerfAPI] Analyzing: strategy={request.strategy_id}, period={request.period}")
    try:
        metrics = await analyze_strategy_performance(request)
        logger.debug(f"[PerfAPI] Analysis complete: sharpe={metrics['sharpe_ratio']}")
        return metrics
    except Exception as e:
        logger.error(f"[PerfAPI] Analysis failed: {e}", exc_info=True)
        raise
```

#### Success Criteria
- Analysis returns valid metrics
- Comparison works
- Reports generated

---

### Task 15: Walk-Forward Analysis - Core Engine

**Priority**: P2 (Medium)
**Estimated Time**: 3 days
**Dependencies**: Task 13

#### Development
- Create `backend/app/services/backtest/walk_forward.py`
- Implement rolling window split
- Implement in-sample optimization
- Implement out-of-sample testing
- Implement performance aggregation

#### Testing
- Window split tests
- Optimization tests
- Aggregation tests

#### Debug Setup
```python
# backend/app/services/backtest/walk_forward.py
logger = logging.getLogger("backtest.walkforward")

def run_walk_forward(strategy_code: str, data: pd.DataFrame, windows: int = 5) -> dict:
    logger.info(f"[WalkForward] Starting: windows={windows}, data_shape={data.shape}")
    try:
        results = []
        for i, (train, test) in enumerate(split_windows(data, windows)):
            logger.debug(f"[WalkForward] Window {i+1}/{windows}: train={len(train)}, test={len(test)}")
            params = optimize_params(strategy_code, train)
            perf = test_strategy(strategy_code, params, test)
            results.append(perf)
        
        aggregated = aggregate_results(results)
        logger.info(f"[WalkForward] Complete: avg_sharpe={aggregated['avg_sharpe']}")
        return aggregated
    except Exception as e:
        logger.error(f"[WalkForward] Failed: {e}", exc_info=True)
        raise
```

#### Success Criteria
- Windows split correctly
- Optimization runs
- Results aggregated

---

### Task 16: Walk-Forward Panel - Frontend UI

**Priority**: P2 (Medium)
**Estimated Time**: 2 days
**Dependencies**: Task 15

#### Development
- Create `frontend/src/components/WalkForwardPanel.vue`
- Implement parameter configuration form
- Implement progress indicator
- Implement results visualization
- Add chart components

#### Testing
- Component render tests
- Form validation tests
- Chart rendering tests

#### Debug Setup
```javascript
// frontend/src/components/WalkForwardPanel.vue
const runWalkForward = async () => {
  console.log('[WalkForwardPanel] Starting walk-forward analysis:', config.value)
  try {
    loading.value = true
    const result = await apiFetch('/api/v1/backtest/walk-forward', {
      method: 'POST',
      body: JSON.stringify(config.value)
    })
    console.log('[WalkForwardPanel] Analysis complete:', result)
    results.value = result
  } catch (error) {
    console.error('[WalkForwardPanel] Analysis failed:', error)
    showError(error.message)
  } finally {
    loading.value = false
  }
}
```

#### Success Criteria
- Form renders correctly
- Progress shown
- Results visualized

---

### Task 17: Strategy Lab - Frontend UI

**Priority**: P1 (High)
**Estimated Time**: 3 days
**Dependencies**: Task 12

#### Development
- Create `frontend/src/components/StrategyLab.vue`
- Implement code editor (Monaco Editor)
- Implement strategy templates
- Implement syntax highlighting
- Implement live preview

#### Testing
- Editor render tests
- Template loading tests
- Preview tests

#### Debug Setup
```javascript
// frontend/src/components/StrategyLab.vue
const saveStrategy = async () => {
  console.log('[StrategyLab] Saving strategy:', { name: strategyName.value, code: code.value })
  try {
    const saved = await apiFetch('/api/v1/strategy/', {
      method: 'POST',
      body: JSON.stringify({
        name: strategyName.value,
        code: code.value,
        type: 'indicator'
      })
    })
    console.log('[StrategyLab] Strategy saved:', saved)
    showSuccess('Strategy saved successfully')
  } catch (error) {
    console.error('[StrategyLab] Save failed:', error)
    showError(error.message)
  }
}
```

#### Success Criteria
- Editor works
- Templates loaded
- Preview shown

---

### Task 18: Data Source Integration - TuShare

**Priority**: P2 (Medium)
**Estimated Time**: 2 days
**Dependencies**: None

#### Development
- Create `backend/app/services/fetchers/tushare_fetcher.py`
- Implement TuShare API client
- Implement stock basic info fetching
- Implement daily data fetching
- Add caching layer

#### Testing
- API client tests
- Data fetching tests
- Caching tests

#### Debug Setup
```python
# backend/app/services/fetchers/tushare_fetcher.py
logger = logging.getLogger("fetcher.tushare")

class TushareFetcher:
    async def get_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        logger.info(f"[TushareFetcher] Fetching daily: code={ts_code}, {start_date} to {end_date}")
        try:
            data = self.pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            logger.debug(f"[TushareFetcher] Fetched {len(data)} rows")
            return data
        except Exception as e:
            logger.error(f"[TushareFetcher] Fetch failed: {e}", exc_info=True)
            raise
```

#### Success Criteria
- TuShare API connected
- Data fetched correctly
- Caching works

---

### Task 19: Audit Logging System

**Priority**: P1 (High)
**Estimated Time**: 2 days
**Dependencies**: Task 2

#### Development
- Create `backend/app/services/audit_service.py`
- Implement audit log creation
- Implement audit log querying
- Implement log rotation
- Add sensitive data masking

#### Testing
- Log creation tests
- Query tests
- Rotation tests

#### Debug Setup
```python
# backend/app/services/audit_service.py
logger = logging.getLogger("audit.service")

class AuditService:
    def log_action(self, agent_id: str, action: str, resource: str, details: dict = None):
        logger.info(f"[AuditService] Logging action: agent={agent_id}, action={action}, resource={resource}")
        try:
            log = AuditLog(
                agent_id=agent_id,
                action=action,
                resource=resource,
                details=mask_sensitive(details) if details else None,
                timestamp=datetime.now()
            )
            self.db.save(log)
            logger.debug(f"[AuditService] Audit log saved: id={log.id}")
        except Exception as e:
            logger.error(f"[AuditService] Logging failed: {e}", exc_info=True)
            # Don't raise - audit logging should not break operations
```

#### Success Criteria
- Logs created
- Logs queryable
- Sensitive data masked

---

### Task 20: Integration Testing & Documentation

**Priority**: P3 (Low)
**Estimated Time**: 2 days
**Dependencies**: All previous tasks

#### Development
- Create comprehensive integration tests
- Create API documentation
- Create user guides
- Create deployment guide
- Add monitoring dashboards

#### Testing
- End-to-end integration tests
- Performance tests
- Security tests

#### Debug Setup
```python
# tests/integration/test_agent_flow.py
logger = logging.getLogger("test.integration")

async def test_agent_full_flow():
    logger.info("[IntegrationTest] Starting agent full flow test")
    try:
        # Create token
        token = await create_agent_token("test_agent", ["R", "B"])
        logger.debug(f"[IntegrationTest] Token created: {token[:20]}...")
        
        # Use token to access API
        markets = await fetch_markets(token)
        logger.debug(f"[IntegrationTest] Markets fetched: {len(markets)}")
        
        # Submit backtest
        job_id = await submit_backtest(token, strategy_id=1)
        logger.debug(f"[IntegrationTest] Backtest submitted: {job_id}")
        
        # Wait for completion
        result = await wait_for_job(job_id)
        logger.info(f"[IntegrationTest] Backtest complete: sharpe={result['sharpe_ratio']}")
        
        assert result['sharpe_ratio'] > 0
    except Exception as e:
        logger.error(f"[IntegrationTest] Test failed: {e}", exc_info=True)
        raise
```

#### Success Criteria
- All integrations tested
- Documentation complete
- Monitoring in place

---

## Debug Cycle Process

For each task, follow this debug cycle:

### Step 1: Add Debug Logging
- Add INFO level logs for operation start/end
- Add DEBUG level logs for intermediate steps
- Add ERROR level logs for exceptions with stack traces

### Step 2: Run Tests
- Execute unit tests
- Execute integration tests
- Execute manual tests

### Step 3: Analyze Logs
- Check for errors
- Check for warnings
- Check for unexpected behavior
- Identify root causes

### Step 4: Fix Issues
- Fix identified bugs
- Optimize performance
- Improve error handling
- Update tests

### Step 5: Verify Fix
- Re-run tests
- Check logs again
- Confirm fix works
- Document changes

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Tasks Completed | 20/20 |
| Tests Passing | 100% |
| Code Coverage | ≥80% |
| API Response Time | <100ms |
| Error Rate | <1% |
| Documentation Complete | 100% |

---

## Timeline

- **Week 1-2**: Tasks 1-6 (Agent Token System)
- **Week 3-4**: Tasks 7-9 (MCP Server)
- **Week 5-7**: Tasks 10-12 (Strategy Framework)
- **Week 8-9**: Tasks 13-14 (Performance Analyzer)
- **Week 10-11**: Tasks 15-16 (Walk-Forward Analysis)
- **Week 12-13**: Tasks 17-18 (Frontend & Data)
- **Week 14**: Tasks 19-20 (Audit & Integration)

**Total Duration**: 14 weeks (3.5 months)

---

*Task Plan Created: 2026-05-09*
*Status: Ready for Execution*
