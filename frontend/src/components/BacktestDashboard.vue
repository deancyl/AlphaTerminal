<template>
  <div class="backtest-dashboard">
    <div class="header">
      <h2>回测实验室</h2>
    </div>
    
    <!-- 策略选择 -->
    <div class="section">
      <label>选择策略</label>
      <select v-model="selectedStrategy" @change="loadStrategy">
        <option v-for="s in strategies" :key="s.id" :value="s">
          {{ s.name }}
        </option>
      </select>
      <div class="strategy-desc" v-if="selectedStrategy">
        {{ selectedStrategy.description }}
      </div>
    </div>
    
    <!-- 参数配置 -->
    <div class="section" v-if="selectedStrategy">
      <label>参数配置</label>
      <div class="params-grid">
        <div v-for="(v, k) in selectedStrategy.params" :key="k" class="param-item">
          <span class="param-key">{{ k }}</span>
          <input 
            type="number" 
            v-model.number="runParams[k]" 
            class="param-input"
          />
        </div>
      </div>
    </div>
    
    <!-- 回测参数 -->
    <div class="section">
      <label>回测参数</label>
      <div class="config-grid">
        <div class="config-item">
          <span>股票代码</span>
          <input v-model="symbol" placeholder="sh600519" />
        </div>
        <div class="config-item">
          <span>初始资金</span>
          <input type="number" v-model.number="initialCapital" />
        </div>
        <div class="config-item">
          <span>开始日期</span>
          <input type="date" v-model="startDate" />
        </div>
        <div class="config-item">
          <span>结束日期</span>
          <input type="date" v-model="endDate" />
        </div>
      </div>
    </div>
    
    <!-- 运行按钮 -->
    <div class="actions">
      <button 
        @click="runBacktest" 
        :disabled="running"
        class="run-btn"
      >
        {{ running ? '运行中...' : '开始回测' }}
      </button>
    </div>
    
    <!-- 结果展示 -->
    <div v-if="result" class="result-section">
      <h3>回测结果</h3>
      
      <!-- 核心指标 -->
      <div class="metrics-grid">
        <div class="metric">
          <span class="label">总收益率</span>
          <span class="value" :class="result.total_return_pct >= 0 ? 'bull' : 'bear'">
            {{ result.total_return_pct?.toFixed(2) }}%
          </span>
        </div>
        <div class="metric">
          <span class="label">年化收益率</span>
          <span class="value" :class="result.total_return_pct >= 0 ? 'bull' : 'bear'">
            {{ result.total_return_pct ? (result.total_return_pct / 1).toFixed(2) : '--' }}%
          </span>
        </div>
        <div class="metric">
          <span class="label">夏普比率</span>
          <span class="value">{{ result.sharpe_ratio?.toFixed(2) || '--' }}</span>
        </div>
        <div class="metric">
          <span class="label">最大回撤</span>
          <span class="value bear">{{ result.max_drawdown && result.initial_capital ? (result.max_drawdown / result.initial_capital * 100).toFixed(2) : '--' }}%</span>
        </div>
      </div>
      
      <!-- 资金曲线 -->
      <div class="chart-container" ref="chartContainer">
        <!-- ECharts 图表容器 -->
      </div>
      
      <!-- 交易记录 -->
      <div class="trades-section" v-if="result.trades?.length">
        <h4>交易记录 ({{ result.trades.length }}笔)</h4>
        <div class="trades-table">
          <div class="trade-row header">
            <span>日期</span>
            <span>操作</span>
            <span>价格</span>
            <span>数量</span>
          </div>
          <div 
            v-for="(t, i) in result.trades.slice(0, 20)" 
            :key="i" 
            class="trade-row"
          >
            <span>{{ t.date }}</span>
            <span :class="t.action === 'buy' ? 'bull' : 'bear'">{{ t.action }}</span>
            <span>{{ t.price?.toFixed(2) }}</span>
            <span>{{ t.shares }}</span>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 错误信息 -->
    <div v-if="error" class="error">{{ error }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'
import { apiFetch } from '../utils/api.js'

const strategies = ref([])
const selectedStrategy = ref(null)
const runParams = ref({})
const symbol = ref('sh600519')
const initialCapital = ref(100000)
const startDate = ref('2024-01-01')
const endDate = ref('2025-12-31')
const running = ref(false)
const result = ref(null)
const error = ref(null)

async function loadStrategies() {
  try {
    // apiFetch returns data directly (not wrapped in {code, data})
    const json = await apiFetch('/api/v1/backtest/strategies')
    strategies.value = json.strategies || []
    if (strategies.value.length) {
      selectedStrategy.value = strategies.value[0]
      loadStrategy()
    }
  } catch (e) {
    error.value = e.message
  }
}

function loadStrategy() {
  if (selectedStrategy.value?.params) {
    runParams.value = { ...selectedStrategy.value.params }
  }
}

async function runBacktest() {
  if (!selectedStrategy.value) return
  
  running.value = true
  error.value = null
  result.value = null
  
  try {
    const json = await apiFetch('/api/v1/backtest/run', {
      method: 'POST',
      body: {
        symbol: symbol.value,
        period: 'daily',
        start_date: startDate.value,
        end_date: endDate.value,
        initial_capital: initialCapital.value,
        strategy_type: selectedStrategy.value.type,
        params: runParams.value
      }
    })
    
    // apiFetch returns data directly
    result.value = json
  } catch (e) {
    error.value = e.message
  } finally {
    running.value = false
  }
}

onMounted(() => {
  loadStrategies()
})
</script>

<style scoped>
.backtest-dashboard {
  padding: 16px;
  background: var(--bg-secondary, #1a1a2e);
  min-height: 100%;
}

.header h2 {
  margin: 0 0 16px;
  color: var(--text-primary, #fff);
  font-size: 18px;
}

.section {
  margin-bottom: 16px;
}

.section > label {
  display: block;
  color: var(--text-secondary, #888);
  font-size: 12px;
  margin-bottom: 8px;
}

.strategy-desc {
  font-size: 12px;
  color: var(--text-secondary, #666);
  margin-top: 4px;
}

select, input {
  width: 100%;
  padding: 8px 12px;
  background: var(--bg-primary, #16162a);
  border: 1px solid var(--border-color, #333);
  border-radius: 4px;
  color: var(--text-primary, #fff);
}

.params-grid, .config-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 8px;
}

.param-item, .config-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.param-key {
  font-size: 12px;
  color: var(--text-secondary, #888);
  min-width: 60px;
}

.param-input {
  flex: 1;
}

.actions {
  margin: 16px 0;
}

.run-btn {
  width: 100%;
  padding: 12px;
  background: var(--bullish, #26a69a);
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
}

.run-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.result-section h3, .result-section h4 {
  color: var(--text-primary, #fff);
  margin: 16px 0 8px;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.metric {
  background: var(--bg-primary, #16162a);
  padding: 12px;
  border-radius: 4px;
  text-align: center;
}

.metric .label {
  display: block;
  font-size: 11px;
  color: var(--text-secondary, #666);
  margin-bottom: 4px;
}

.metric .value {
  font-size: 18px;
  font-weight: 600;
  font-family: monospace;
}

.bull { color: var(--bullish, #26a69a); }
.bear { color: var(--bearish, #ef5350); }

.chart-container {
  height: 200px;
  background: var(--bg-primary, #16162a);
  border-radius: 4px;
  margin: 12px 0;
}

.trades-table {
  max-height: 300px;
  overflow-y: auto;
}

.trade-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 1fr;
  padding: 6px 8px;
  border-bottom: 1px solid var(--border-color, #333);
  font-size: 12px;
  font-family: monospace;
}

.trade-row.header {
  color: var(--text-secondary, #666);
  font-size: 11px;
}

.error {
  color: #ff6b6b;
  padding: 12px;
  background: rgba(255, 107, 107, 0.1);
  border-radius: 4px;
}
</style>