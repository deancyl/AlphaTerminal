<template>
  <div class="flex flex-col w-full h-full overflow-hidden">
    <!-- 顶部控制栏 -->
    <div class="shrink-0 flex items-center gap-2 px-3 py-1.5 border-b border-theme bg-terminal-panel/80">
      <span class="text-[10px] text-theme-muted">基准指数</span>
      <select
        v-model="benchmark"
        class="bg-theme-tertiary/30 border border-theme rounded-sm px-1.5 py-0.5 text-[10px] text-theme-primary"
      >
        <option value="000300">沪深300</option>
        <option value="000001">上证指数</option>
        <option value="399001">深证成指</option>
        <option value="399006">创业板指</option>
      </select>
      <button
        @click="loadPerformance"
        :disabled="loading"
        class="ml-auto px-3 py-0.5 rounded-sm text-[10px] font-medium transition-colors"
        :class="loading
          ? 'bg-gray-600/40 text-theme-muted cursor-not-allowed'
          : 'bg-[var(--color-info-bg)] text-[var(--color-info)] hover:bg-[var(--color-info-bg)] border border-[var(--color-info-border)]'"
      >{{ loading ? '⏳ 计算中...' : '🔄 刷新' }}</button>
    </div>

    <!-- 主内容区 -->
    <div v-if="metrics" class="flex-1 min-h-0 overflow-y-auto p-2 space-y-3">
      
      <!-- 核心指标行 -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-2">
        <div
          v-for="m in coreMetrics"
          :key="m.key"
          class="rounded-sm border border-theme bg-terminal-panel/60 px-3 py-2"
        >
          <div class="text-[10px] text-theme-muted truncate">{{ m.label }}</div>
          <div
            class="text-[14px] font-mono font-bold"
            :class="m.colorClass || 'text-theme-primary'"
          >{{ m.value }}</div>
          <div v-if="m.desc" class="text-[10px] text-theme-muted mt-0.5">{{ m.desc }}</div>
        </div>
      </div>

      <!-- 风险指标行 -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-2">
        <div
          v-for="m in riskMetrics"
          :key="m.key"
          class="rounded-sm border border-theme bg-terminal-panel/60 px-3 py-2"
        >
          <div class="text-[10px] text-theme-muted truncate">{{ m.label }}</div>
          <div
            class="text-[14px] font-mono font-bold"
            :class="m.colorClass || 'text-theme-primary'"
          >{{ m.value }}</div>
        </div>
      </div>

      <!-- 高级指标行 -->
      <div v-if="hasBenchmark" class="grid grid-cols-2 md:grid-cols-4 gap-2">
        <div
          v-for="m in advancedMetrics"
          :key="m.key"
          class="rounded-sm border border-theme bg-terminal-panel/60 px-3 py-2"
        >
          <div class="text-[10px] text-theme-muted truncate">{{ m.label }}</div>
          <div
            class="text-[14px] font-mono font-bold"
            :class="m.colorClass || 'text-theme-primary'"
          >{{ m.value }}</div>
        </div>
      </div>

      <!-- 指标说明 -->
      <div class="rounded-sm border border-theme bg-terminal-panel/40 px-3 py-2 space-y-1">
        <div class="text-[10px] text-theme-muted font-bold mb-1">📊 指标说明</div>
        <div class="text-[10px] text-theme-muted leading-relaxed">
          <span class="text-theme-primary">夏普比率</span>: 每单位总风险获得的超额收益，>1优秀，<0较差 |
          <span class="text-theme-primary">最大回撤</span>: 峰值到谷底的最大亏损幅度，越小越好 |
          <span class="text-theme-primary">胜率</span>: 正收益交易日占比
        </div>
        <div v-if="hasBenchmark" class="text-[10px] text-theme-muted leading-relaxed">
          <span class="text-theme-primary">Beta</span>: 组合相对于市场的波动敏感度，=1同步，>1高波动 |
          <span class="text-theme-primary">Alpha</span>: 超越基准的超额收益能力，>0跑赢市场 |
          <span class="text-theme-primary">特雷诺比率</span>: 每单位系统风险(Beta)的超额收益
        </div>
      </div>

      <!-- 统计周期 -->
      <div class="text-center">
        <span class="text-[10px] text-theme-muted">📅 {{ period }} | 共 {{ metrics.total_days }} 个交易日</span>
      </div>
    </div>

    <!-- 空状态 -->
    <div
      v-else-if="!loading"
      class="flex-1 flex flex-col items-center justify-center text-theme-muted text-[11px] gap-2"
    >
      <span class="text-xl">🎯</span>
      <span>{{ errorMsg || '点击"刷新"计算业绩评价指标' }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { apiFetch } from '../utils/api.js'
import { logger } from '../utils/logger.js'

const props = defineProps({
  portfolioId: { type: Number, required: true },
})

const benchmark = ref('000300')
const loading = ref(false)
const metrics = ref(null)
const period = ref('')
const errorMsg = ref('')

const hasBenchmark = computed(() => metrics.value?.beta !== null && metrics.value?.beta !== undefined)

// 核心指标
const coreMetrics = computed(() => {
  if (!metrics.value) return []
  const m = metrics.value
  return [
    { 
      key: 'sharpe', 
      label: '夏普比率', 
      value: m.sharpe_ratio > 0 ? `+${m.sharpe_ratio}` : m.sharpe_ratio,
      colorClass: m.sharpe_ratio >= 1 ? 'text-bullish' : m.sharpe_ratio < 0 ? 'text-bearish' : 'text-theme-muted',
      desc: '>1优秀'
    },
    { 
      key: 'return', 
      label: '年化收益', 
      value: `${m.annual_return >= 0 ? '+' : ''}${m.annual_return}%`,
      colorClass: m.annual_return >= 0 ? 'text-bullish' : 'text-bearish'
    },
    { 
      key: 'maxdd', 
      label: '最大回撤', 
      value: `-${m.max_drawdown}%`,
      colorClass: m.max_drawdown < 10 ? 'text-bullish' : m.max_drawdown < 20 ? 'text-[var(--color-warning)]' : 'text-bearish',
      desc: '越小越好'
    },
    { 
      key: 'winrate', 
      label: '胜率', 
      value: `${m.win_rate}%`,
      colorClass: m.win_rate >= 55 ? 'text-bullish' : m.win_rate >= 45 ? 'text-theme-primary' : 'text-bearish'
    },
  ]
})

// 风险指标
const riskMetrics = computed(() => {
  if (!metrics.value) return []
  const m = metrics.value
  return [
    { 
      key: 'volatility', 
      label: '年化波动率', 
      value: `${m.annual_volatility}%`,
      colorClass: m.annual_volatility < 15 ? 'text-bullish' : m.annual_volatility < 25 ? 'text-theme-primary' : 'text-bearish'
    },
    { 
      key: 'sortino', 
      label: '索提诺比率', 
      value: m.sortino_ratio > 0 ? `+${m.sortino_ratio}` : m.sortino_ratio,
      colorClass: m.sortino_ratio >= 1 ? 'text-bullish' : m.sortino_ratio < 0 ? 'text-bearish' : 'text-theme-muted'
    },
    { 
      key: 'calmar', 
      label: '卡玛比率', 
      value: m.calmar_ratio > 0 ? `+${m.calmar_ratio}` : m.calmar_ratio,
      colorClass: m.calmar_ratio >= 1 ? 'text-bullish' : m.calmar_ratio < 0 ? 'text-bearish' : 'text-theme-muted'
    },
    { 
      key: 'days', 
      label: '统计天数', 
      value: `${m.total_days}天`,
      colorClass: 'text-theme-primary'
    },
  ]
})

// 高级指标（需要基准数据）
const advancedMetrics = computed(() => {
  if (!metrics.value || !hasBenchmark.value) return []
  const m = metrics.value
  return [
    { 
      key: 'beta', 
      label: 'Beta', 
      value: m.beta,
      colorClass: m.beta > 1.2 ? 'text-bearish' : m.beta < 0.8 ? 'text-[var(--color-warning)]' : 'text-bullish'
    },
    { 
      key: 'alpha', 
      label: 'Alpha(年化%)', 
      value: `${m.alpha >= 0 ? '+' : ''}${m.alpha}%`,
      colorClass: m.alpha > 0 ? 'text-bullish' : m.alpha < 0 ? 'text-bearish' : 'text-theme-muted'
    },
    { 
      key: 'treynor', 
      label: '特雷诺比率', 
      value: m.treynor_ratio > 0 ? `+${m.treynor_ratio}` : m.treynor_ratio,
      colorClass: m.treynor_ratio >= 0.5 ? 'text-bullish' : m.treynor_ratio < 0 ? 'text-bearish' : 'text-theme-muted'
    },
    { 
      key: 'ir', 
      label: '信息比率', 
      value: m.information_ratio > 0 ? `+${m.information_ratio}` : m.information_ratio,
      colorClass: m.information_ratio >= 0.5 ? 'text-bullish' : m.information_ratio < 0 ? 'text-bearish' : 'text-theme-muted'
    },
  ]
})

async function loadPerformance() {
  if (loading.value) return
  loading.value = true
  errorMsg.value = ''
  try {
    const resp = await apiFetch(
      `/api/v1/portfolio/${props.portfolioId}/performance?benchmark=${benchmark.value}`
    )
    if (resp?.metrics) {
      metrics.value = resp.metrics
      period.value = resp.period || ''
    } else if (resp?.message) {
      errorMsg.value = resp.message
      metrics.value = null
    }
  } catch (e) {
    logger.error('[PerformancePanel] loadPerformance error:', e)
    errorMsg.value = '加载失败'
  } finally {
    loading.value = false
  }
}

watch(() => props.portfolioId, () => {
  metrics.value = null
  loadPerformance()
}, { immediate: true })
</script>