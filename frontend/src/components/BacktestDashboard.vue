<template>
  <div class="flex flex-col w-full h-full overflow-hidden">

    <!-- 顶部控制栏 -->
    <div class="shrink-0 border-b border-theme bg-terminal-panel/90 px-3 py-2">
      <div class="flex items-center gap-3 flex-wrap">

        <!-- 标的 -->
        <div class="flex items-center gap-1">
          <span class="text-[9px] text-theme-muted">标的</span>
          <input
            v-model="symbol"
            class="bg-theme-tertiary/30 border border-theme rounded px-2 py-0.5 text-[10px] text-theme-primary w-20 focus:outline-none focus:border-cyan-400/60"
            placeholder="sh600519"
          />
        </div>

        <!-- 快速窗口 -->
        <div class="flex items-center gap-1">
          <span class="text-[9px] text-theme-muted">窗口</span>
          <select
            v-model="windowPreset"
            class="bg-theme-tertiary/30 border border-theme rounded px-1 py-0.5 text-[10px] text-theme-primary focus:outline-none"
          >
            <option value="1m">近1月</option>
            <option value="3m">近3月</option>
            <option value="6m">近6月</option>
            <option value="1y" selected>近1年</option>
            <option value="2y">近2年</option>
            <option value="5y">近5年</option>
          </select>
        </div>

        <!-- 策略参数 -->
        <div class="flex items-center gap-1">
          <span class="text-[9px] text-theme-muted">快线</span>
          <input
            v-model.number="fastMa"
            type="number"
            min="2" max="60"
            class="bg-theme-tertiary/30 border border-theme rounded px-1 py-0.5 text-[10px] text-theme-primary w-10 focus:outline-none text-center"
          />
        </div>
        <div class="flex items-center gap-1">
          <span class="text-[9px] text-theme-muted">慢线</span>
          <input
            v-model.number="slowMa"
            type="number"
            min="5" max="250"
            class="bg-theme-tertiary/30 border border-theme rounded px-1 py-0.5 text-[10px] text-theme-primary w-10 focus:outline-none text-center"
          />
        </div>

        <!-- 执行按钮 -->
        <button
          @click="runBacktest"
          :disabled="running"
          class="px-3 py-0.5 rounded text-[10px] font-medium transition-colors"
          :class="running
            ? 'bg-gray-600/40 text-theme-muted cursor-not-allowed'
            : 'bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 border border-blue-500/40'"
        >
          {{ running ? '⏳ 回测中...' : '▶ 执行回测' }}
        </button>

        <!-- 状态 -->
        <span v-if="statusMsg" class="text-[9px] text-theme-muted">{{ statusMsg }}</span>
      </div>
    </div>

    <!-- 主图区：K线 + 买卖信号 + 资金曲线 -->
    <div class="flex-1 min-h-0 relative" ref="chartWrapRef">
      <BacktestChart
        v-if="histData.length > 0"
        :key="chartKey"
        :hist="histData"
        :trades="backtestResult?.trades || []"
        :symbol="symbol"
        class="w-full h-full"
      />
      <div
        v-else-if="!running"
        class="absolute inset-0 flex flex-col items-center justify-center text-theme-muted text-[11px] gap-2"
      >
        <span class="text-xl">📊</span>
        <span>配置参数后点击"执行回测"</span>
      </div>
      <div
        v-if="running"
        class="absolute inset-0 z-10 flex flex-col items-center justify-center"
        style="background: rgba(15,23,42,0.7); backdrop-filter: blur(2px);"
      >
        <div class="text-blue-400 text-xs font-mono">⏳ 回测引擎运行中...</div>
      </div>
    </div>

    <!-- 底部指标 + 交易记录 -->
    <div v-if="backtestResult" class="shrink-0 border-t border-theme bg-terminal-panel/80">

      <!-- 核心指标行 -->
      <div class="flex items-center gap-3 px-3 py-1.5 overflow-x-auto text-[9px]">
        <div class="shrink-0 flex items-center gap-1">
          <span class="text-theme-muted">收益率</span>
          <span
            class="font-mono font-bold"
            :class="backtestResult.total_return_pct >= 0 ? 'text-bullish' : 'text-bearish'"
          >{{ backtestResult.total_return_pct >= 0 ? '+' : '' }}{{ backtestResult.total_return_pct?.toFixed(2) }}%</span>
        </div>
        <div class="shrink-0 flex items-center gap-1">
          <span class="text-theme-muted">年化</span>
          <span
            class="font-mono"
            :class="backtestResult.annualized_return_pct >= 0 ? 'text-bullish' : 'text-bearish'"
          >{{ backtestResult.annualized_return_pct >= 0 ? '+' : '' }}{{ backtestResult.annualized_return_pct?.toFixed(2) }}%</span>
        </div>
        <div class="shrink-0 flex items-center gap-1">
          <span class="text-theme-muted">最大回撤</span>
          <span class="font-mono text-bearish">{{ backtestResult.max_drawdown_pct?.toFixed(2) }}%</span>
        </div>
        <div class="shrink-0 flex items-center gap-1">
          <span class="text-theme-muted">胜率</span>
          <span class="font-mono text-theme-primary">{{ backtestResult.win_rate?.toFixed(1) }}%</span>
        </div>
        <div class="shrink-0 flex items-center gap-1">
          <span class="text-theme-muted">交易次数</span>
          <span class="font-mono text-theme-primary">{{ backtestResult.trades_count }}</span>
        </div>
        <div class="shrink-0 flex items-center gap-1">
          <span class="text-theme-muted">夏普</span>
          <span class="font-mono" :class="(backtestResult.sharpe_ratio || 0) >= 1 ? 'text-bullish' : 'text-theme-muted'">
            {{ backtestResult.sharpe_ratio?.toFixed(2) || '—' }}
          </span>
        </div>
        <div class="shrink-0 flex items-center gap-1">
          <span class="text-theme-muted">盈亏比</span>
          <span class="font-mono text-theme-primary">{{ profitFactor }}</span>
        </div>

        <!-- 切换交易记录展开 -->
        <button
          class="ml-auto shrink-0 text-[9px] text-theme-muted hover:text-cyan-400 transition-colors"
          @click="showTrades = !showTrades"
        >
          {{ showTrades ? '▲ 收起' : '▼ 交易记录' }} ({{ backtestResult.trades?.length }})
        </button>
      </div>

      <!-- 交易记录表格（可展开） -->
      <div v-if="showTrades && backtestResult.trades?.length" class="border-t border-theme/30 max-h-36 overflow-y-auto">
        <table class="w-full text-[9px]">
          <thead class="sticky top-0 bg-terminal-panel">
            <tr class="text-theme-muted border-b border-theme/20">
              <th class="px-2 py-0.5 text-left">方向</th>
              <th class="px-2 py-0.5 text-right">买入日期</th>
              <th class="px-2 py-0.5 text-right">买价</th>
              <th class="px-2 py-0.5 text-right">卖出日期</th>
              <th class="px-2 py-0.5 text-right">卖价</th>
              <th class="px-2 py-0.5 text-right">数量</th>
              <th class="px-2 py-0.5 text-right">盈亏额</th>
              <th class="px-2 py-0.5 text-right">盈亏%</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(t, i) in backtestResult.trades"
              :key="i"
              class="border-b border-theme/10 hover:bg-theme-tertiary/20"
            >
              <td class="px-2 py-0.5">
                <span
                  class="font-mono font-bold"
                  :class="t.pnl >= 0 ? 'text-bullish' : 'text-bearish'"
                >{{ t.pnl >= 0 ? '多' : '空' }}</span>
              </td>
              <td class="px-2 py-0.5 text-right text-theme-secondary font-mono">{{ t.entry_date }}</td>
              <td class="px-2 py-0.5 text-right text-theme-primary font-mono">{{ t.entry_price?.toFixed(2) }}</td>
              <td class="px-2 py-0.5 text-right text-theme-secondary font-mono">{{ t.exit_date || '持仓中' }}</td>
              <td class="px-2 py-0.5 text-right text-theme-primary font-mono">{{ t.exit_price?.toFixed(2) || '—' }}</td>
              <td class="px-2 py-0.5 text-right text-theme-primary font-mono">{{ t.shares }}</td>
              <td
                class="px-2 py-0.5 text-right font-mono font-bold"
                :class="(t.pnl || 0) >= 0 ? 'text-bullish' : 'text-bearish'"
              >{{ (t.pnl || 0) >= 0 ? '+' : '' }}{{ t.pnl?.toFixed(2) }}</td>
              <td
                class="px-2 py-0.5 text-right font-mono"
                :class="(t.pnl_pct || 0) >= 0 ? 'text-bullish' : 'text-bearish'"
              >{{ (t.pnl_pct || 0) >= 0 ? '+' : '' }}{{ t.pnl_pct?.toFixed(2) }}%</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, shallowRef } from 'vue'
import { apiFetch } from '../utils/api.js'
import BacktestChart from './BacktestChart.vue'

// ── 参数状态 ────────────────────────────────────────────────────
const symbol     = ref('sh600519')
const fastMa     = ref(5)
const slowMa     = ref(20)
const windowPreset = ref('1y')

const running      = ref(false)
const statusMsg    = ref('')
const backtestResult = ref(null)
const histData     = shallowRef([])
const chartKey     = ref(0)
const showTrades   = ref(false)
const chartWrapRef = ref(null)

const initialCapital = 100000

// ── 计算起止日期 ───────────────────────────────────────────────
function presetDates(preset) {
  const end = new Date()
  const start = new Date()
  switch (preset) {
    case '1m':  start.setMonth(end.getMonth() - 1);  break
    case '3m':  start.setMonth(end.getMonth() - 3);  break
    case '6m':  start.setMonth(end.getMonth() - 6);  break
    case '1y':  start.setFullYear(end.getFullYear() - 1); break
    case '2y':  start.setFullYear(end.getFullYear() - 2); break
    case '5y':  start.setFullYear(end.getFullYear() - 5); break
  }
  return {
    start_date: start.toISOString().slice(0, 10),
    end_date:   end.toISOString().slice(0, 10),
  }
}

// ── 核心：执行回测 ──────────────────────────────────────────────
async function runBacktest() {
  if (running.value) return
  running.value = true
  statusMsg.value = ''
  backtestResult.value = null
  histData.value = []

  try {
    const { start_date, end_date } = presetDates(windowPreset.value)
    const sym = symbol.value.trim() || 'sh600519'

    // 1. 拉取历史 K 线（给图表用）
    statusMsg.value = '📡 拉取历史数据...'
    const histResp = await apiFetch(
      `/api/v1/market/history/${sym}?period=daily&limit=5000&offset=0`
    )
    const rawHist = (histResp?.history || []).map(s => ({
      date:   s.date || s.time || '',
      time:   s.time || '',
      open:   Number(s.open)  || 0,
      high:   Number(s.high)  || 0,
      low:    Number(s.low)   || 0,
      close:  Number(s.close) || 0,
      volume: Number(s.volume) || 0,
    })).filter(s => s.date >= start_date && s.date <= end_date)

    if (!rawHist.length) {
      statusMsg.value = '⚠️ 该时段无历史数据'
      return
    }
    histData.value = rawHist

    // 2. 执行回测
    statusMsg.value = '⚙️ 运行回测引擎...'
    const btResp = await apiFetch('/api/v1/backtest/run', {
      method: 'POST',
      body: {
        symbol:         sym,
        period:         'daily',
        start_date,
        end_date,
        initial_capital: initialCapital,
        strategy_type:  'ma_crossover',
        params:         { fast_ma: fastMa.value, slow_ma: slowMa.value },
      },
    })

    const data = btResp?.data || btResp || {}
    backtestResult.value = data
    statusMsg.value = `✅ 完成 ${data.trades_count} 笔交易`
    chartKey.value++  // 触发图表重绘
  } catch (e) {
    statusMsg.value = `❌ ${e.message || '回测失败'}`
  } finally {
    running.value = false
  }
}

// ── 盈亏比 ──────────────────────────────────────────────────────
const profitFactor = computed(() => {
  const t = backtestResult.value?.trades || []
  if (!t.length) return '—'
  const wins = t.filter(x => (x.pnl || 0) > 0)
  const losses = t.filter(x => (x.pnl || 0) < 0)
  const avgWin = wins.length ? wins.reduce((s, x) => s + x.pnl, 0) / wins.length : 0
  const avgLoss = losses.length ? Math.abs(losses.reduce((s, x) => s + x.pnl, 0) / losses.length) : 0
  if (!avgLoss) return avgWin ? '∞' : '—'
  return (avgWin / avgLoss).toFixed(2)
})
</script>
