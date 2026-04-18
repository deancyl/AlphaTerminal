<template>
  <div class="flex w-full h-full overflow-hidden">

    <!-- ═══════════════ 左侧边栏 ═══════════════ -->
    <aside class="w-56 shrink-0 flex flex-col border-r border-theme bg-terminal-panel overflow-y-auto">

      <!-- 策略参数 -->
      <div class="px-3 py-2.5 border-b border-theme">
        <div class="text-[10px] text-theme-accent font-bold mb-2">⚙️ 策略参数</div>

        <div class="space-y-1.5">
          <!-- 策略选择 -->
          <div class="flex items-center justify-between">
            <span class="text-[9px] text-theme-muted w-8">策略</span>
            <select v-model="strategyType"
              class="bg-slate-900 border border-slate-600 rounded px-1.5 py-0.5 text-[10px] text-cyan-100 focus:outline-none">
              <option value="ma_crossover">双均线</option>
              <option value="rsi_oversold">RSI超卖</option>
              <option value="bollinger_bands">布林带</option>
            </select>
          </div>

          <!-- 双均线参数 -->
          <template v-if="strategyType === 'ma_crossover'">
            <div class="flex items-center justify-between">
              <span class="text-[9px] text-theme-muted w-8">快线</span>
              <input v-model.number="fastMa" type="number" min="2" max="60"
                class="bg-slate-900 border border-slate-600 rounded px-1.5 py-0.5 text-[10px] text-cyan-100 w-14 text-center focus:outline-none focus:border-cyan-400/60" />
            </div>
            <div class="text-[9px] text-theme-muted leading-tight">短期趋势（如 5 日），反应近期价格敏感变化</div>
            <div class="flex items-center justify-between">
              <span class="text-[9px] text-theme-muted w-8">慢线</span>
              <input v-model.number="slowMa" type="number" min="5" max="250"
                class="bg-slate-900 border border-slate-600 rounded px-1.5 py-0.5 text-[10px] text-cyan-100 w-14 text-center focus:outline-none focus:border-cyan-400/60" />
            </div>
            <div class="text-[9px] text-theme-muted leading-tight">长期趋势（如 20 日），代表中长线支撑与阻力</div>
          </template>

          <!-- RSI 参数 -->
          <template v-if="strategyType === 'rsi_oversold'">
            <div class="flex items-center justify-between">
              <span class="text-[9px] text-theme-muted w-8">周期</span>
              <input v-model.number="rsiPeriod" type="number" min="7" max="30"
                class="bg-slate-900 border border-slate-600 rounded px-1.5 py-0.5 text-[10px] text-cyan-100 w-14 text-center focus:outline-none focus:border-cyan-400/60" />
            </div>
            <div class="flex items-center justify-between">
              <span class="text-[9px] text-theme-muted w-8">买入</span>
              <input v-model.number="rsiBuy" type="number" min="10" max="50"
                class="bg-slate-900 border border-slate-600 rounded px-1.5 py-0.5 text-[10px] text-cyan-100 w-14 text-center focus:outline-none focus:border-cyan-400/60" />
            </div>
            <div class="text-[9px] text-theme-muted leading-tight">RSI &lt; 此值买入（默认30超卖）</div>
            <div class="flex items-center justify-between">
              <span class="text-[9px] text-theme-muted w-8">卖出</span>
              <input v-model.number="rsiSell" type="number" min="50" max="90"
                class="bg-slate-900 border border-slate-600 rounded px-1.5 py-0.5 text-[10px] text-cyan-100 w-14 text-center focus:outline-none focus:border-cyan-400/60" />
            </div>
            <div class="text-[9px] text-theme-muted leading-tight">RSI &gt; 此值卖出（默认70超买）</div>
          </template>

          <!-- 布林带参数 -->
          <template v-if="strategyType === 'bollinger_bands'">
            <div class="flex items-center justify-between">
              <span class="text-[9px] text-theme-muted w-8">周期</span>
              <input v-model.number="bbPeriod" type="number" min="10" max="60"
                class="bg-slate-900 border border-slate-600 rounded px-1.5 py-0.5 text-[10px] text-cyan-100 w-14 text-center focus:outline-none focus:border-cyan-400/60" />
            </div>
            <div class="flex items-center justify-between">
              <span class="text-[9px] text-theme-muted w-8">倍数</span>
              <input v-model.number="bbStd" type="number" min="1" max="4" step="0.5"
                class="bg-slate-900 border border-slate-600 rounded px-1.5 py-0.5 text-[10px] text-cyan-100 w-14 text-center focus:outline-none focus:border-cyan-400/60" />
            </div>
            <div class="text-[9px] text-theme-muted leading-tight">布林带标准差倍数（默认2倍）</div>
          </template>

          <!-- 窗口 -->
          <div class="flex items-center justify-between">
            <span class="text-[9px] text-theme-muted w-8">窗口</span>
            <select v-model="windowPreset"
              class="bg-slate-900 border border-slate-600 rounded px-1.5 py-0.5 text-[10px] text-cyan-100 focus:outline-none">
              <option value="1m">近1月</option>
              <option value="3m">近3月</option>
              <option value="6m">近6月</option>
              <option value="1y" selected>近1年</option>
              <option value="2y">近2年</option>
              <option value="5y">近5年</option>
            </select>
          </div>
          <!-- 初始资金 -->
          <div class="flex items-center justify-between">
            <span class="text-[9px] text-theme-muted w-8">资金</span>
            <span class="text-[10px] font-mono text-theme-secondary">{{ (initialCapital / 10000).toFixed(0) }}万</span>
          </div>

          <!-- 策略规则提示 -->
          <div class="mt-2 px-2 py-1.5 rounded bg-blue-500/10 border border-blue-500/20 text-[9px] leading-snug">
            💡 <span class="text-blue-300 font-medium">双均线策略规则：</span>
            <span class="text-blue-200/70">快线向上穿越慢线时<span class="text-green-400">金叉→全仓买入</span>；</span>
            <span class="text-blue-200/70">快线向下穿越慢线时<span class="text-red-400">死叉→全仓清仓</span>。</span>
          </div>
        </div>
      </div>

      <!-- 标的输入 -->
      <div class="px-3 py-2.5 border-b border-theme">
        <div class="text-[10px] text-theme-accent font-bold mb-2">🎯 标的</div>
        <div class="flex items-center gap-1.5">
          <input v-model="symbol"
            class="flex-1 bg-slate-900 border border-slate-600 rounded px-2 py-1 text-[10px] text-cyan-100 focus:outline-none focus:border-cyan-400"
            placeholder="输入代码 (例: sh600519)"
            @keyup.enter="runBacktest" />
          <!-- 格式校验通过图标 -->
          <span v-if="symbolValid"
            class="shrink-0 text-[12px] leading-none text-green-400 select-none" title="格式正确">✅</span>
          <span v-else-if="symbol.length > 0"
            class="shrink-0 text-[12px] leading-none text-red-400 select-none" title="格式有误">❌</span>
        </div>
        <!-- 自动补全名称（若匹配到 indexOptions） -->
        <div v-if="symbolMatchedName"
          class="mt-1 text-[9px] text-cyan-400 truncate">{{ symbolMatchedName }}</div>
        <div v-else-if="symbolValid"
          class="mt-1 text-[9px] text-theme-muted italic">回车直接执行回测</div>
      </div>

      <!-- 投资组合联动 -->
      <div class="px-3 py-2.5 border-b border-theme">
        <div class="text-[10px] text-theme-accent font-bold mb-2">📦 从投资组合导入</div>

        <!-- 有组合时：下拉 + 持仓标签 -->
        <template v-if="portfolioOptions.length > 0">
          <select v-model="selectedPortfolioId"
            @change="onPortfolioChange"
            class="w-full bg-slate-900 border border-slate-600 rounded px-2 py-1 text-[10px] text-cyan-100 mb-2 focus:outline-none">
            <option value="">— 选择组合 —</option>
            <option v-for="p in portfolioOptions" :key="p.id" :value="p.id">
              {{ p.name }}
            </option>
          </select>

          <!-- 持仓标签（点击即执行回测） -->
          <div v-if="positionTags.length" class="flex flex-wrap gap-1">
            <button
              v-for="pos in positionTags"
              :key="pos.symbol"
              @click="symbol = pos.symbol; runBacktest()"
              :disabled="running"
              class="px-1.5 py-0.5 text-[9px] rounded border transition-colors"
              :class="running
                ? 'border-theme-tertiary text-theme-muted cursor-not-allowed opacity-50'
                : 'border-cyan-500/40 text-cyan-400 hover:bg-cyan-500/20 cursor-pointer'"
            >
              {{ pos.name }}<span class="opacity-60 ml-0.5">{{ pos.symbol }}</span>
            </button>
          </div>
          <div v-else-if="selectedPortfolioId && positionTagsLoading"
            class="text-[9px] text-theme-muted italic">加载中...</div>
          <div v-else-if="selectedPortfolioId"
            class="text-[9px] text-theme-muted italic">该组合暂无持仓</div>
          <div v-else class="text-[9px] text-theme-muted italic">选择组合后可快速回测持仓</div>
        </template>

        <!-- 无组合时：空状态引导 -->
        <div v-if="portfolioOptions.length === 0"
          class="text-[9px] text-theme-muted leading-relaxed">
          暂无投资组合。请先在<span class="text-cyan-400">投资组合</span>面板中创建并添加持仓，即可在此一键导入回测。
        </div>
      </div>

      <!-- 执行按钮（底部撑满） -->
      <div class="mt-auto px-3 py-2.5 border-t border-theme">
        <button
          @click="runBacktest"
          :disabled="running"
          class="w-full py-1.5 rounded text-[11px] font-medium transition-colors"
          :class="running
            ? 'bg-gray-600/40 text-theme-muted cursor-not-allowed'
            : 'bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 border border-blue-500/40'"
        >
          {{ running ? '⏳ 回测中...' : '▶ 执行回测' }}
        </button>
        <!-- 状态行 -->
        <div v-if="statusMsg" class="mt-1.5 text-[9px] text-center"
          :class="statusMsg.startsWith('❌') ? 'text-red-400' : statusMsg.startsWith('⚠️') ? 'text-yellow-400' : 'text-theme-muted'">
          {{ statusMsg }}
        </div>
      </div>
    </aside>

    <!-- ═══════════════ 右侧主区 ═══════════════ -->
    <main class="flex-1 flex flex-col min-w-0 overflow-hidden">

      <!-- 图表区 -->
      <div class="flex-1 min-h-0 relative" ref="chartWrapRef">
        <BacktestChart
          v-if="histData.length > 0"
          :key="chartKey"
          :hist="histData"
          :trades="backtestResult?.trades || []"
          :symbol="symbol"
          class="w-full h-full"
        />
        <div v-else-if="!running"
          class="absolute inset-0 flex flex-col items-center justify-center text-theme-muted text-[11px] gap-2">
          <span class="text-xl">📊</span>
          <span>配置参数或选择持仓后点击"执行回测"</span>
        </div>
        <!-- Loading 遮罩 -->
        <div v-if="running"
          class="absolute inset-0 z-10 flex flex-col items-center justify-center"
          style="background: rgba(15,23,42,0.75); backdrop-filter: blur(2px);">
          <div class="text-blue-400 text-xs font-mono">⏳ 回测引擎运行中...</div>
        </div>
      </div>

      <!-- 底部指标 + 交易记录 -->
      <div v-if="backtestResult" class="shrink-0 border-t border-theme bg-terminal-panel/80 max-h-48 overflow-y-auto">

        <!-- 核心指标行 -->
        <div class="flex items-center gap-3 px-3 py-1.5 overflow-x-auto text-[9px]">
          <div class="shrink-0 flex items-center gap-1">
            <span class="text-theme-muted">收益率</span>
            <span class="font-mono font-bold" :class="(backtestResult.total_return_pct||0) >= 0 ? 'text-bullish' : 'text-bearish'">
              {{ (backtestResult.total_return_pct||0) >= 0 ? '+' : '' }}{{ (backtestResult.total_return_pct||0).toFixed(2) }}%
            </span>
          </div>
          <div class="shrink-0 flex items-center gap-1">
            <span class="text-theme-muted">年化</span>
            <span class="font-mono" :class="(backtestResult.annualized_return_pct||0) >= 0 ? 'text-bullish' : 'text-bearish'">
              {{ (backtestResult.annualized_return_pct||0) >= 0 ? '+' : '' }}{{ (backtestResult.annualized_return_pct||0).toFixed(2) }}%
            </span>
          </div>
          <div class="shrink-0 flex items-center gap-1">
            <span class="text-theme-muted">最大回撤</span>
            <span class="font-mono text-bearish">{{ (backtestResult.max_drawdown_pct||0).toFixed(2) }}%</span>
          </div>
          <div class="shrink-0 flex items-center gap-1">
            <span class="text-theme-muted">胜率</span>
            <span class="font-mono text-theme-primary">{{ (backtestResult.win_rate||0).toFixed(1) }}%</span>
          </div>
          <div class="shrink-0 flex items-center gap-1">
            <span class="text-theme-muted">交易</span>
            <span class="font-mono text-theme-primary">{{ backtestResult.trades_count||0 }}</span>
          </div>
          <div class="shrink-0 flex items-center gap-1">
            <span class="text-theme-muted">夏普</span>
            <span class="font-mono" :class="(backtestResult.sharpe_ratio||0) >= 1 ? 'text-bullish' : 'text-theme-muted'">
              {{ (backtestResult.sharpe_ratio||0).toFixed(2) || '—' }}
            </span>
          </div>
          <div class="shrink-0 flex items-center gap-1">
            <span class="text-theme-muted">盈亏比</span>
            <span class="font-mono text-theme-primary">{{ profitFactor }}</span>
          </div>
          <button
            class="ml-auto shrink-0 text-[9px] text-theme-muted hover:text-cyan-400 transition-colors"
            @click="showTrades = !showTrades">
            {{ showTrades ? '▲ 收起' : '▼ 交易' }} ({{ backtestResult.trades?.length||0 }})
          </button>
        </div>

        <!-- ═══ 策略体检报告 ═══ -->
        <div class="border-t border-theme/30 px-3 py-1.5">
          <div class="flex items-center gap-4 text-[9px]">
            <!-- 策略 vs 基准对比 -->
            <div class="flex items-center gap-1.5 shrink-0">
              <span class="text-theme-muted">策略</span>
              <span class="font-mono font-bold" :class="(backtestResult.total_return_pct||0) >= 0 ? 'text-bullish' : 'text-bearish'">
                {{ (backtestResult.total_return_pct||0) >= 0 ? '+' : '' }}{{ (backtestResult.total_return_pct||0).toFixed(2) }}%
              </span>
            </div>
            <div class="text-theme-muted shrink-0">|</div>
            <div class="flex items-center gap-1.5 shrink-0">
              <span class="text-theme-muted">基准</span>
              <span class="font-mono text-yellow-400">
                +{{ (backtestResult.benchmark_return_pct||0).toFixed(2) }}%
              </span>
            </div>
            <div class="text-theme-muted shrink-0">|</div>
            <div class="flex items-center gap-1 shrink-0">
              <span class="text-theme-muted">评级</span>
              <span :class="strategyGradeClass">{{ strategyGradeText }}</span>
            </div>
            <div class="flex items-center gap-1 shrink-0 text-cyan-300">
              {{ strategyVerdict }}
            </div>
          </div>
        </div>

        <!-- 交易记录表格 -->
        <div v-if="showTrades && backtestResult.trades?.length"
          class="border-t border-theme/30">
          <table class="w-full text-[9px]">
            <thead class="sticky top-0 bg-terminal-panel">
              <tr class="text-theme-muted border-b border-theme/20">
                <th class="px-2 py-0.5 text-left">方向</th>
                <th class="px-2 py-0.5 text-right">买日期</th>
                <th class="px-2 py-0.5 text-right">买价</th>
                <th class="px-2 py-0.5 text-right">卖日期</th>
                <th class="px-2 py-0.5 text-right">卖价</th>
                <th class="px-2 py-0.5 text-right">数量</th>
                <th class="px-2 py-0.5 text-right">盈亏额</th>
                <th class="px-2 py-0.5 text-right">盈亏%</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(t, i) in backtestResult.trades" :key="i"
                class="border-b border-theme/10 hover:bg-theme-tertiary/20">
                <td class="px-2 py-0.5">
                  <span class="font-mono font-bold" :class="(t.pnl||0) >= 0 ? 'text-bullish' : 'text-bearish'">
                    {{ (t.pnl||0) >= 0 ? '多' : '空' }}
                  </span>
                </td>
                <td class="px-2 py-0.5 text-right text-theme-secondary font-mono">{{ t.entry_date }}</td>
                <td class="px-2 py-0.5 text-right text-theme-primary font-mono">{{ (t.entry_price||0).toFixed(2) }}</td>
                <td class="px-2 py-0.5 text-right text-theme-secondary font-mono">{{ t.exit_date || '持仓中' }}</td>
                <td class="px-2 py-0.5 text-right text-theme-primary font-mono">{{ t.exit_price != null ? t.exit_price.toFixed(2) : '—' }}</td>
                <td class="px-2 py-0.5 text-right text-theme-primary font-mono">{{ t.shares }}</td>
                <td class="px-2 py-0.5 text-right font-mono font-bold"
                  :class="(t.pnl||0) >= 0 ? 'text-bullish' : 'text-bearish'">
                  {{ (t.pnl||0) >= 0 ? '+' : '' }}{{ (t.pnl||0).toFixed(2) }}
                </td>
                <td class="px-2 py-0.5 text-right font-mono"
                  :class="(t.pnl_pct||0) >= 0 ? 'text-bullish' : 'text-bearish'">
                  {{ (t.pnl_pct||0) >= 0 ? '+' : '' }}{{ (t.pnl_pct||0).toFixed(2) }}%
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { apiFetch } from '../utils/api.js'
import { usePortfolioStore } from '../composables/usePortfolioStore.js'
import BacktestChart from './BacktestChart.vue'

// ── 已知指数选项（用于标的自动补全，不依赖外部 store）────────────
const KNOWN_INDEXES = [
  { symbol: 'sh000001', name: '上证指数' },
  { symbol: 'sh000300', name: '沪深300' },
  { symbol: 'sz399001', name: '深证成指' },
  { symbol: 'sz399006', name: '创业板指' },
  { symbol: 'sh000688', name: '科创50' },
]

// ── 组合数据 ────────────────────────────────────────────────────
const portfolioStore = usePortfolioStore()
const portfolioOptions = computed(() =>
  (portfolioStore.portfolios.value || []).filter(p => !p.parent_id)
)
const selectedPortfolioId = ref('')
const positionTags = ref([])
const positionTagsLoading = ref(false)

onMounted(() => {
  portfolioStore.fetchPortfolios?.()
})

async function onPortfolioChange() {
  positionTags.value = []
  const pid = selectedPortfolioId.value
  if (!pid) return
  positionTagsLoading.value = true
  try {
    const d = await apiFetch(`/api/v1/portfolio/${pid}/positions`)
    const list = Array.isArray(d) ? d : (d?.data || [])
    positionTags.value = list.map(p => ({
      symbol: p.symbol || p.code || '',
      name: p.name || p.symbol || '',
    }))
  } catch (e) {
    positionTags.value = []
  } finally {
    positionTagsLoading.value = false
  }
}

// ── 回测参数 ────────────────────────────────────────────────────
const symbol        = ref('sh600519')
const strategyType  = ref('ma_crossover')
const fastMa        = ref(5)
const slowMa        = ref(20)
const rsiPeriod     = ref(14)
const rsiBuy        = ref(30)
const rsiSell       = ref(70)
const bbPeriod      = ref(20)
const bbStd         = ref(2)
const windowPreset  = ref('1y')
const initialCapital = 100000

// ── 标的格式校验（8位 = 市场前缀 + 6位代码）─────────────────────
const symbolValid = computed(() => /^(sh|sz)[0-9]{6}$/.test(symbol.value.trim()))
const symbolMatchedName = computed(() => {
  const norm = symbol.value.trim()
  const known = KNOWN_INDEXES.find(o => o.symbol === norm)
  return known?.name || null
})

const running        = ref(false)
const statusMsg     = ref('')
const backtestResult = ref(null)
const histData      = ref([])
const chartKey      = ref(0)
const showTrades    = ref(false)
const chartWrapRef  = ref(null)

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
  return { start_date: start.toISOString().slice(0, 10), end_date: end.toISOString().slice(0, 10) }
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

    statusMsg.value = '📡 拉取历史数据...'
    const histResp = await apiFetch(
      `/api/v1/market/history/${sym}?period=daily&limit=5000&offset=0`
    )
    const rawHist = (histResp?.history || []).map(s => ({
      date:   s.date || s.time || '',
      open:   Number(s.open)  || 0,
      high:   Number(s.high)  || 0,
      low:    Number(s.low)   || 0,
      close:  Number(s.close) || 0,
      volume: Number(s.volume)|| 0,
    })).filter(s => s.date >= start_date && s.date <= end_date)

    if (!rawHist.length) {
      statusMsg.value = '⚠️ 该时段无历史数据'
      return
    }
    histData.value = rawHist

    statusMsg.value = '⚙️ 运行回测引擎...'
    const btResp = await apiFetch('/api/v1/backtest/run', {
      method: 'POST',
      body: {
        symbol:         sym,
        period:         'daily',
        start_date,
        end_date,
        initial_capital: initialCapital,
        strategy_type:  strategyType.value,
        params: (() => {
          switch (strategyType.value) {
            case 'ma_crossover':    return { fast_ma: fastMa.value,  slow_ma: slowMa.value }
            case 'rsi_oversold':   return { rsi_period: rsiPeriod.value, rsi_buy: rsiBuy.value, rsi_sell: rsiSell.value }
            case 'bollinger_bands': return { bb_period: bbPeriod.value, bb_std: bbStd.value }
            default:                return {}
          }
        })(),
      },
    })

    // 兼容后端报错格式 {code, message, ...}
    if (btResp?.code !== 0 && btResp?.code !== undefined) {
      statusMsg.value = `❌ ${btResp?.message || '回测失败'}`
      return
    }

    const data = btResp?.data || btResp || {}
    backtestResult.value = data
    statusMsg.value = `✅ 完成 ${data.trades_count||0} 笔交易`
    chartKey.value++
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
  const wins   = t.filter(x => (x.pnl || 0) > 0)
  const losses = t.filter(x => (x.pnl || 0) < 0)
  const avgWin  = wins.length   ? wins.reduce((s, x) => s + x.pnl, 0) / wins.length : 0
  const avgLoss = losses.length ? Math.abs(losses.reduce((s, x) => s + x.pnl, 0) / losses.length) : 0
  if (!avgLoss) return avgWin ? '∞' : '—'
  return (avgWin / avgLoss).toFixed(2)
})

// ── 策略体检报告 ─────────────────────────────────────────────────
const strategyGradeText = computed(() => {
  const r = backtestResult.value
  if (!r) return '—'
  const ret = r.total_return_pct || 0
  const bm  = r.benchmark_return_pct || 0
  const sh  = r.sharpe_ratio || 0
  const dd  = r.max_drawdown_pct || 100
  const excess = ret - bm
  if (excess > 10 && sh >= 1.5) return '🏆 优秀'
  if (excess > 0  && sh >= 1.0) return '✅ 良好'
  if (excess > 0)               return '🆗 及格'
  return '⚠️ 需优化'
})

const strategyGradeClass = computed(() => {
  const g = strategyGradeText.value
  if (g.startsWith('🏆')) return 'font-bold text-yellow-300'
  if (g.startsWith('✅')) return 'font-bold text-green-400'
  if (g.startsWith('🆗')) return 'font-medium text-blue-400'
  return 'font-medium text-red-400'
})

const strategyVerdict = computed(() => {
  const ret = backtestResult.value?.total_return_pct || 0
  const bm  = backtestResult.value?.benchmark_return_pct || 0
  const excess = ret - bm
  if (excess > 5)  return `🌟 跑赢基准 ${excess.toFixed(1)}%，策略超额收益显著`
  if (excess > 0)  return `📈 跑赢基准 ${excess.toFixed(1)}%`
  if (excess > -5)  return `⚠️ 略输持股不动 ${Math.abs(excess).toFixed(1)}%，可适当调整参数`
  return `🔻 显著弱于持股不动 ${Math.abs(excess).toFixed(1)}%，建议换策略或扩大回测窗口`
})
</script>
