# QuantDinger Integration Development Tasks

> Created: 2026-05-08
> Based on: QUANTDINGER_INTEGRATION_REPORT.md
> Target Version: v0.6.38
> Status: Planning Phase

---

## 📋 Executive Summary

This document defines the development tasks for integrating QuantDinger's core features into AlphaTerminal:

1. **AI Agent Gateway** - Token management and secure API access
2. **MCP Server** - Model Context Protocol for AI agent integration
3. **Strategy Framework** - IndicatorStrategy and ScriptStrategy DSL
4. **Frontend Entry Points** - Sidebar navigation and UI components

Each phase includes implementation details, followed by 5 debug cycles to ensure stability.

---

## 🎯 Phase 1: Frontend Entry Point Design

### Objective
Design and implement frontend navigation structure for new QuantDinger features.

### Current State Analysis
- **Sidebar Component**: `frontend/src/components/Sidebar.vue`
- **Current Navigation Items**: stock, portfolio, fund, bond, futures, macro, options, global-index, backtest, strategy, admin
- **Missing Items**: agent_tokens (already added), mcp_config, strategy_lab

### Task 1.1: Update Sidebar Navigation

**File**: `frontend/src/components/Sidebar.vue`

**Changes**:
```javascript
const mainNavItems = [
  { id: 'stock',     label: '股票行情',   icon: '📊' },
  { id: 'portfolio', label: '投资组合',   icon: '💰' },
  { id: 'fund',      label: '基金分析',   icon: '📈' },
  { id: 'bond',      label: '债券行情',   icon: '📉' },
  { id: 'futures',   label: '期货行情',   icon: '🛢️' },
  { id: 'macro',     label: '宏观经济',   icon: '🌍' },
  { id: 'options',   label: '期权分析',   icon: '⚡' },
  { id: 'global-index', label: '全球指数',  icon: '🌐' },
  { id: 'backtest',  label: '回测实验室', icon: '🔬' },
  
  // NEW: QuantDinger Integration
  { id: 'strategy-lab',  label: '策略实验室', icon: '🧪' },  // Strategy Framework
  { id: 'agent-tokens', label: 'Agent Token',  icon: '🔑' },  // Token Management
  { id: 'mcp-config', label: 'MCP 配置',  icon: '🔌' },       // MCP Server Config
]
```

### Task 1.2: Create Route Handlers

**File**: `frontend/src/App.vue`

Add view handling for new routes:
```vue
<!-- In template section -->
<StrategyLab v-if="currentView === 'strategy-lab'" />
<AgentTokenManager v-if="currentView === 'agent-tokens'" />
<MCPConfigDashboard v-if="currentView === 'mcp-config'" />
```

### Task 1.3: Create Component Stubs

Create placeholder components:
- `frontend/src/components/StrategyLab.vue`
- `frontend/src/components/AgentTokenManager.vue`
- `frontend/src/components/MCPConfigDashboard.vue`

### Deliverables
- [ ] Updated Sidebar.vue with new navigation items
- [ ] Route handlers in App.vue
- [ ] Component stub files created
- [ ] Navigation flow tested

---

## 🔐 Phase 2: Agent Token Management UI

### Objective
Implement UI for managing Agent Tokens (create, list, revoke, scope management).

### Backend Dependencies
Based on QUANTDINGER_INTEGRATION_REPORT.md Section 3.1.2, we need:
- Token CRUD API: `/api/agent/v1/admin/tokens`
- Token verification: `/api/agent/v1/whoami`

### Task 2.1: Create Token Data Model

**File**: `frontend/src/models/agentToken.js`

```javascript
export class AgentToken {
  constructor(data) {
    this.id = data.id
    this.name = data.name
    this.tokenPrefix = data.token_prefix  // First 20 chars for display
    this.scopes = data.scopes || []        // ['R', 'W', 'B', 'N', 'C', 'T']
    this.markets = data.markets || ['*']
    this.instruments = data.instruments || ['*']
    this.paperOnly = data.paper_only ?? true
    this.rateLimit = data.rate_limit || 120
    this.expiresAt = data.expires_at
    this.createdAt = data.created_at
    this.lastUsedAt = data.last_used_at
  }

  get isExpired() {
    return new Date(this.expiresAt) < new Date()
  }

  get scopeLabels() {
    const labels = {
      'R': '读取',
      'W': '写入',
      'B': '回测',
      'N': '通知',
      'C': '凭证',
      'T': '交易'
    }
    return this.scopes.map(s => labels[s] || s).join(', ')
  }
}
```

### Task 2.2: Create Token Manager Component

**File**: `frontend/src/components/AgentTokenManager.vue`

**Features**:
1. **Token List View**
   - Display all tokens in a table
   - Show: name, prefix, scopes, expiry, last used
   - Color coding: active (green), expired (red), expiring soon (yellow)

2. **Create Token Modal**
   - Form fields:
     - Token name (required)
     - Scopes selection (checkboxes: R, W, B, N, C, T)
     - Markets filter (multi-select)
     - Rate limit (number input)
     - Expiry duration (dropdown: 7d, 30d, 90d, 1y)
   - Generate and display token ONCE
   - Copy to clipboard button

3. **Token Actions**
   - Revoke token (with confirmation)
   - View token details
   - Copy token prefix

**Component Structure**:
```vue
<template>
  <div class="agent-token-manager p-6">
    <!-- Header -->
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-xl font-bold text-theme-primary">🔑 Agent Token 管理</h2>
      <button @click="showCreateModal = true" class="btn-primary">
        + 创建新 Token
      </button>
    </div>

    <!-- Token List -->
    <div class="token-list">
      <table class="w-full">
        <thead>
          <tr>
            <th>名称</th>
            <th>Token 前缀</th>
            <th>权限</th>
            <th>市场</th>
            <th>过期时间</th>
            <th>最后使用</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="token in tokens" :key="token.id">
            <td>{{ token.name }}</td>
            <td><code>{{ token.tokenPrefix }}...</code></td>
            <td>{{ token.scopeLabels }}</td>
            <td>{{ token.markets.join(', ') }}</td>
            <td :class="getTokenExpiryClass(token)">
              {{ formatDate(token.expiresAt) }}
            </td>
            <td>{{ token.lastUsedAt ? formatDate(token.lastUsedAt) : '从未' }}</td>
            <td>
              <button @click="revokeToken(token.id)" class="btn-danger btn-sm">
                撤销
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Create Modal -->
    <CreateTokenModal
      v-if="showCreateModal"
      @close="showCreateModal = false"
      @created="handleTokenCreated"
    />
  </div>
</template>
```

### Task 2.3: Create Token API Service

**File**: `frontend/src/services/agentTokenService.js`

```javascript
import { API_BASE_URL } from '../utils/api.js'

export class AgentTokenService {
  async listTokens() {
    const response = await fetch(`${API_BASE_URL}/api/agent/v1/admin/tokens`, {
      headers: this.getAuthHeaders()
    })
    if (!response.ok) throw new Error('Failed to fetch tokens')
    return response.json()
  }

  async createToken(data) {
    const response = await fetch(`${API_BASE_URL}/api/agent/v1/admin/tokens`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(data)
    })
    if (!response.ok) throw new Error('Failed to create token')
    return response.json()  // Returns { token: "at_xxx", ...metadata }
  }

  async revokeToken(tokenId) {
    const response = await fetch(
      `${API_BASE_URL}/api/agent/v1/admin/tokens/${tokenId}`,
      {
        method: 'DELETE',
        headers: this.getAuthHeaders()
      }
    )
    if (!response.ok) throw new Error('Failed to revoke token')
    return response.json()
  }

  getAuthHeaders() {
    // Use admin JWT token from localStorage
    const token = localStorage.getItem('admin_token')
    return {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    }
  }
}
```

### Deliverables
- [ ] AgentToken data model
- [ ] AgentTokenManager.vue component
- [ ] CreateTokenModal.vue component
- [ ] agentTokenService.js API client
- [ ] Token list display
- [ ] Token creation flow
- [ ] Token revocation flow

---

## 🧪 Phase 3: Strategy Lab UI

### Objective
Implement UI for creating and managing trading strategies using IndicatorStrategy DSL.

### Backend Dependencies
Based on QUANTDINGER_INTEGRATION_REPORT.md Section 3.4:
- Strategy CRUD: `/api/strategies/`
- Strategy execution: `/api/backtest/run`
- Strategy validation: `/api/strategies/validate`

### Task 3.1: Create Strategy Editor Component

**File**: `frontend/src/components/StrategyLab.vue`

**Features**:
1. **Strategy List Panel**
   - Display saved strategies
   - Filter by: market, type (indicator/script)
   - Search by name

2. **Strategy Editor**
   - Monaco Editor integration for Python code
   - Syntax highlighting
   - Auto-complete for strategy DSL
   - Live preview of indicators

3. **Strategy Metadata Form**
   - Name, description
   - Parameters (with @param annotations)
   - Risk settings (stop loss, take profit)
   - Trade direction (long/short/both)

4. **Strategy Testing**
   - Quick backtest button
   - Parameter sweep UI
   - Results visualization

**Component Structure**:
```vue
<template>
  <div class="strategy-lab flex h-full">
    <!-- Left: Strategy List -->
    <div class="w-64 border-r border-theme-secondary p-4">
      <div class="flex justify-between items-center mb-4">
        <h3 class="font-bold">策略列表</h3>
        <button @click="createNewStrategy" class="btn-primary btn-sm">
          + 新建
        </button>
      </div>
      <input
        v-model="searchQuery"
        placeholder="搜索策略..."
        class="input-sm w-full mb-3"
      />
      <div class="space-y-2">
        <div
          v-for="strategy in filteredStrategies"
          :key="strategy.id"
          @click="selectStrategy(strategy)"
          class="p-2 rounded cursor-pointer transition"
          :class="selectedStrategy?.id === strategy.id
            ? 'bg-theme-accent/20 border border-theme-accent'
            : 'hover:bg-theme-hover'"
        >
          <div class="font-medium text-sm">{{ strategy.name }}</div>
          <div class="text-xs text-theme-tertiary">{{ strategy.market }}</div>
        </div>
      </div>
    </div>

    <!-- Right: Editor + Preview -->
    <div class="flex-1 flex flex-col">
      <!-- Toolbar -->
      <div class="h-12 border-b border-theme-secondary flex items-center px-4 gap-3">
        <input
          v-model="selectedStrategy.name"
          class="input-sm flex-1"
          placeholder="策略名称"
        />
        <select v-model="selectedStrategy.market" class="input-sm">
          <option value="Crypto">加密货币</option>
          <option value="USStock">美股</option>
          <option value="AStock">A股</option>
          <option value="Forex">外汇</option>
        </select>
        <button @click="saveStrategy" class="btn-primary btn-sm">
          💾 保存
        </button>
        <button @click="runBacktest" class="btn-accent btn-sm">
          ▶️ 回测
        </button>
      </div>

      <!-- Code Editor -->
      <div class="flex-1 flex">
        <div class="flex-1">
          <MonacoEditor
            v-model="selectedStrategy.code"
            language="python"
            :options="editorOptions"
          />
        </div>

        <!-- Preview Panel -->
        <div class="w-80 border-l border-theme-secondary p-4 overflow-y-auto">
          <h4 class="font-bold mb-3">策略参数</h4>
          <div v-for="param in parsedParams" :key="param.name" class="mb-3">
            <label class="text-xs text-theme-tertiary">{{ param.name }}</label>
            <input
              v-model="param.value"
              :type="param.type === 'int' ? 'number' : 'text'"
              class="input-sm w-full"
            />
          </div>

          <h4 class="font-bold mb-3 mt-6">风险设置</h4>
          <div class="space-y-2">
            <label class="text-xs text-theme-tertiary">止损 %</label>
            <input v-model="selectedStrategy.stopLossPct" type="number" class="input-sm w-full" />
            <label class="text-xs text-theme-tertiary">止盈 %</label>
            <input v-model="selectedStrategy.takeProfitPct" type="number" class="input-sm w-full" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
```

### Task 3.2: Strategy Code Templates

**File**: `frontend/src/templates/strategyTemplates.js`

```javascript
export const STRATEGY_TEMPLATES = {
  ma_cross: `# @name 均线金叉策略
# @description 短期均线上穿长期均线时买入
# @param fast_period 快线周期 5
# @param slow_period 慢线周期 20
# @strategy stopLossPct 2
# @strategy takeProfitPct 6

import pandas as pd

fast_ma = df['close'].rolling(${fast_period}).mean()
slow_ma = df['close'].rolling(${slow_period}).mean()

df['buy'] = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))
df['sell'] = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))

output = {
    'indicators': {'fast_ma': fast_ma, 'slow_ma': slow_ma},
    'signals': {'buy': df['buy'], 'sell': df['sell']}
}
`,

  rsi_oversold: `# @name RSI 超卖策略
# @description RSI 低于超卖线时买入
# @param period RSI周期 14
# @param oversold 超卖阈值 30
# @param overbought 超买阈值 70
# @strategy stopLossPct 3
# @strategy takeProfitPct 8

import pandas as pd

delta = df['close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(${period}).mean()
loss = (-delta.where(delta < 0, 0)).rolling(${period}).mean()
rs = gain / loss
rsi = 100 - (100 / (1 + rs))

df['buy'] = rsi < ${oversold}
df['sell'] = rsi > ${overbought}

output = {
    'indicators': {'rsi': rsi},
    'signals': {'buy': df['buy'], 'sell': df['sell']}
}
`,

  bollinger_bands: `# @name 布林带回归策略
# @description 价格触及下轨买入，上轨卖出
# @param period 周期 20
# @param std_dev 标准差倍数 2
# @strategy stopLossPct 2
# @strategy takeProfitPct 5

import pandas as pd

mid = df['close'].rolling(${period}).mean()
std = df['close'].rolling(${period}).std()
upper = mid + ${std_dev} * std
lower = mid - ${std_dev} * std

df['buy'] = df['close'] <= lower
df['sell'] = df['close'] >= upper

output = {
    'indicators': {'mid': mid, 'upper': upper, 'lower': lower},
    'signals': {'buy': df['buy'], 'sell': df['sell']}
}
`
}
```

### Task 3.3: Strategy Parameter Parser

**File**: `frontend/src/utils/strategyParser.js`

```javascript
export class StrategyParser {
  static parseAnnotations(code) {
    const lines = code.split('\n')
    const metadata = {
      name: '',
      description: '',
      params: [],
      strategy: {}
    }

    for (const line of lines) {
      // Parse @name
      const nameMatch = line.match(/#\s*@name\s+(.+)/)
      if (nameMatch) metadata.name = nameMatch[1].trim()

      // Parse @description
      const descMatch = line.match(/#\s*@description\s+(.+)/)
      if (descMatch) metadata.description = descMatch[1].trim()

      // Parse @param
      const paramMatch = line.match(/#\s*@param\s+(\w+)\s+(.+?)\s+(\d+)/)
      if (paramMatch) {
        metadata.params.push({
          name: paramMatch[1],
          description: paramMatch[2],
          defaultValue: parseFloat(paramMatch[3]),
          type: Number.isInteger(parseFloat(paramMatch[3])) ? 'int' : 'float'
        })
      }

      // Parse @strategy
      const strategyMatch = line.match(/#\s*@strategy\s+(\w+)\s+(.+)/)
      if (strategyMatch) {
        metadata.strategy[strategyMatch[1]] = parseFloat(strategyMatch[2])
      }
    }

    return metadata
  }

  static injectParameters(code, params) {
    let result = code
    for (const [key, value] of Object.entries(params)) {
      const regex = new RegExp(`\\$\\{${key}\\}`, 'g')
      result = result.replace(regex, value)
    }
    return result
  }
}
```

### Deliverables
- [ ] StrategyLab.vue component
- [ ] Monaco Editor integration
- [ ] Strategy templates
- [ ] Parameter parser
- [ ] Strategy CRUD operations
- [ ] Quick backtest integration
- [ ] Parameter sweep UI

---

## 🔌 Phase 4: MCP Server Configuration Dashboard

### Objective
Provide UI for configuring and monitoring MCP Server settings.

### Task 4.1: Create MCP Config Dashboard

**File**: `frontend/src/components/MCPConfigDashboard.vue`

**Features**:
1. **Server Status**
   - Running state indicator
   - Uptime
   - Connected clients count
   - Last heartbeat

2. **Configuration Editor**
   - Base URL setting
   - Transport mode (stdio/sse/http)
   - Port configuration
   - Timeout settings

3. **Tool Registry**
   - List of exposed MCP tools
   - Tool descriptions
   - Scope requirements
   - Enable/disable toggles

4. **Connection Testing**
   - Test connection button
   - Ping/pong latency
   - Error logs

**Component Structure**:
```vue
<template>
  <div class="mcp-config-dashboard p-6">
    <!-- Header -->
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-xl font-bold text-theme-primary">🔌 MCP Server 配置</h2>
      <div class="flex items-center gap-3">
        <span
          class="px-3 py-1 rounded-full text-sm"
          :class="isRunning ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'"
        >
          {{ isRunning ? '● 运行中' : '○ 已停止' }}
        </span>
        <button @click="toggleServer" class="btn-primary">
          {{ isRunning ? '停止' : '启动' }}
        </button>
      </div>
    </div>

    <!-- Configuration Grid -->
    <div class="grid grid-cols-2 gap-6">
      <!-- Left: Config -->
      <div class="bg-terminal-panel rounded-lg p-4 border border-theme-secondary">
        <h3 class="font-bold mb-4">服务器配置</h3>
        <div class="space-y-4">
          <div>
            <label class="text-xs text-theme-tertiary">Base URL</label>
            <input
              v-model="config.baseUrl"
              class="input w-full"
              placeholder="http://localhost:8002"
            />
          </div>
          <div>
            <label class="text-xs text-theme-tertiary">传输模式</label>
            <select v-model="config.transport" class="input w-full">
              <option value="stdio">stdio</option>
              <option value="sse">SSE</option>
              <option value="http">HTTP</option>
            </select>
          </div>
          <div v-if="config.transport !== 'stdio'">
            <label class="text-xs text-theme-tertiary">端口</label>
            <input v-model="config.port" type="number" class="input w-full" />
          </div>
          <div>
            <label class="text-xs text-theme-tertiary">超时 (秒)</label>
            <input v-model="config.timeout" type="number" class="input w-full" />
          </div>
          <button @click="saveConfig" class="btn-primary w-full">
            💾 保存配置
          </button>
        </div>
      </div>

      <!-- Right: Tools -->
      <div class="bg-terminal-panel rounded-lg p-4 border border-theme-secondary">
        <h3 class="font-bold mb-4">已注册工具</h3>
        <div class="space-y-2 max-h-96 overflow-y-auto">
          <div
            v-for="tool in tools"
            :key="tool.name"
            class="p-3 rounded border border-theme-secondary"
          >
            <div class="flex justify-between items-start">
              <div>
                <div class="font-medium">{{ tool.name }}</div>
                <div class="text-xs text-theme-tertiary">{{ tool.description }}</div>
              </div>
              <span class="text-xs px-2 py-1 rounded bg-theme-accent/20">
                {{ tool.scope }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Connection Test -->
    <div class="mt-6 bg-terminal-panel rounded-lg p-4 border border-theme-secondary">
      <h3 class="font-bold mb-4">连接测试</h3>
      <div class="flex items-center gap-4">
        <button @click="testConnection" class="btn-accent">
          🏓 测试连接
        </button>
        <div v-if="testResult" class="flex-1">
          <span :class="testResult.success ? 'text-green-400' : 'text-red-400'">
            {{ testResult.success ? '✓' : '✗' }} {{ testResult.message }}
          </span>
          <span v-if="testResult.latency" class="text-theme-tertiary ml-3">
            延迟: {{ testResult.latency }}ms
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
```

### Deliverables
- [ ] MCPConfigDashboard.vue component
- [ ] Server status monitoring
- [ ] Configuration editor
- [ ] Tool registry display
- [ ] Connection testing

---

## 🐛 Debug Cycles (5 Iterations)

### Debug Cycle 1: Agent Token UI Testing

**Scope**: Test Agent Token Management functionality

**Test Cases**:
1. **Token Creation**
   - [ ] Create token with all scope combinations
   - [ ] Validate token format (starts with "at_")
   - [ ] Verify token is displayed only once
   - [ ] Test copy to clipboard

2. **Token Display**
   - [ ] List all tokens correctly
   - [ ] Show correct expiry status (active/expired/expiring)
   - [ ] Display scope labels correctly
   - [ ] Show last used timestamp

3. **Token Revocation**
   - [ ] Revoke token with confirmation
   - [ ] Verify token is removed from list
   - [ ] Test revoked token cannot be used

4. **Error Handling**
   - [ ] Handle API errors gracefully
   - [ ] Show validation errors
   - [ ] Handle network failures

**Debug Log Analysis**:
```bash
# Check backend logs
tail -f /tmp/backend.log | grep -i "agent.*token"

# Check frontend console
# Look for: API errors, validation errors, state updates
```

**Expected Fixes**:
- Token creation validation
- Expiry calculation bugs
- UI state management issues
- API error handling

---

### Debug Cycle 2: Strategy Lab Testing

**Scope**: Test Strategy Lab functionality

**Test Cases**:
1. **Strategy CRUD**
   - [ ] Create new strategy
   - [ ] Save strategy to backend
   - [ ] Load strategy from list
   - [ ] Update existing strategy
   - [ ] Delete strategy

2. **Code Editor**
   - [ ] Syntax highlighting works
   - [ ] Auto-complete for DSL
   - [ ] Parameter injection
   - [ ] Code validation

3. **Parameter Parsing**
   - [ ] Parse @name annotation
   - [ ] Parse @param annotations
   - [ ] Parse @strategy annotations
   - [ ] Handle malformed annotations

4. **Backtest Integration**
   - [ ] Quick backtest executes
   - [ ] Results display correctly
   - [ ] Parameter sweep works
   - [ ] Error handling

**Debug Log Analysis**:
```bash
# Check backend logs
tail -f /tmp/backend.log | grep -i "strategy\|backtest"

# Check for Python execution errors
tail -f /tmp/backend.log | grep -i "error\|exception"
```

**Expected Fixes**:
- Strategy code validation
- Parameter injection bugs
- Backtest execution errors
- UI rendering issues

---

### Debug Cycle 3: MCP Dashboard Testing

**Scope**: Test MCP Server configuration

**Test Cases**:
1. **Server Status**
   - [ ] Display correct running state
   - [ ] Show uptime correctly
   - [ ] Update status in real-time

2. **Configuration**
   - [ ] Save config to backend
   - [ ] Load config on mount
   - [ ] Validate config values

3. **Tool Registry**
   - [ ] List all tools
   - [ ] Show correct descriptions
   - [ ] Display scope requirements

4. **Connection Testing**
   - [ ] Test connection succeeds
   - [ ] Show latency correctly
   - [ ] Handle connection failures

**Debug Log Analysis**:
```bash
# Check MCP server logs
tail -f /tmp/backend.log | grep -i "mcp"

# Check for connection errors
tail -f /tmp/backend.log | grep -i "connection.*error"
```

**Expected Fixes**:
- Config persistence bugs
- Status update issues
- Connection test errors
- UI state bugs

---

### Debug Cycle 4: Integration Testing

**Scope**: Test cross-feature integration

**Test Cases**:
1. **Token + Strategy Integration**
   - [ ] Use agent token to submit strategy
   - [ ] Verify scope permissions
   - [ ] Test token expiry blocks access

2. **Strategy + MCP Integration**
   - [ ] MCP tools can fetch strategies
   - [ ] MCP tools can run backtests
   - [ ] Results returned correctly

3. **Navigation Flow**
   - [ ] Sidebar navigation works
   - [ ] View switching is smooth
   - [ ] State persists across views

4. **Performance**
   - [ ] Token list loads quickly
   - [ ] Strategy editor is responsive
   - [ ] MCP status updates timely

**Debug Log Analysis**:
```bash
# Full integration test
tail -f /tmp/backend.log | grep -i "agent\|strategy\|mcp"

# Performance profiling
# Check for slow queries, N+1 problems
```

**Expected Fixes**:
- Cross-feature state bugs
- Permission issues
- Navigation glitches
- Performance bottlenecks

---

### Debug Cycle 5: Final Validation

**Scope**: Final validation and optimization

**Test Cases**:
1. **End-to-End Flows**
   - [ ] Create token → Use in strategy → Run backtest
   - [ ] Create strategy → Configure MCP → Test via MCP
   - [ ] Full user journey without errors

2. **Edge Cases**
   - [ ] Empty states handled
   - [ ] Long lists paginate correctly
   - [ ] Large code files don't crash editor
   - [ ] Network failures recover

3. **Browser Compatibility**
   - [ ] Chrome
   - [ ] Firefox
   - [ ] Safari
   - [ ] Edge

4. **Mobile Responsiveness**
   - [ ] Sidebar collapses on mobile
   - [ ] Tables are scrollable
   - [ ] Modals fit screen

**Debug Log Analysis**:
```bash
# Final comprehensive log check
tail -f /tmp/backend.log

# Frontend console
# Check for: warnings, deprecations, memory leaks
```

**Expected Fixes**:
- Edge case handling
- Browser-specific bugs
- Mobile layout issues
- Memory leaks
- Performance optimizations

---

## 📊 Success Metrics

### Phase Completion Criteria

| Phase | Success Criteria |
|-------|------------------|
| Phase 1 | All navigation items visible and functional |
| Phase 2 | Token CRUD works end-to-end |
| Phase 3 | Strategy creation and backtest work |
| Phase 4 | MCP config saves and tests successfully |
| Debug 1-5 | All test cases pass, no critical bugs |

### Quality Gates

- **Code Coverage**: > 70% for new components
- **Performance**: Page load < 2s, API response < 500ms
- **Accessibility**: WCAG 2.1 AA compliance
- **Browser Support**: Chrome, Firefox, Safari, Edge (latest 2 versions)

---

## 🚀 Implementation Timeline

```
Week 1: Phase 1 (Frontend Entry Points)
Week 2-3: Phase 2 (Agent Token UI)
Week 4-5: Phase 3 (Strategy Lab)
Week 6: Phase 4 (MCP Dashboard)
Week 7: Debug Cycle 1-2
Week 8: Debug Cycle 3-4
Week 9: Debug Cycle 5 + Final Polish
```

**Total Duration**: ~9 weeks (2 months)

---

## 📝 Notes

1. **Backend API Development**: This document assumes backend APIs are being developed in parallel. Coordinate with backend team on API contracts.

2. **Monaco Editor**: Consider using `@monaco-editor/loader` for lazy loading to reduce initial bundle size.

3. **State Management**: For complex state (strategy editor, token list), consider using Pinia stores.

4. **Testing**: Write unit tests for parsers, services, and utility functions. Write E2E tests for critical user flows.

5. **Documentation**: Update API_GUIDE.md and user documentation after each phase.

---

*Document Version: 1.0*
*Last Updated: 2026-05-08*
*Author: Sisyphus Development Team*
