<template>
  <div class="flex flex-col w-full h-full overflow-hidden">

    <!-- 顶部控制栏 -->
    <div class="shrink-0 flex items-center gap-2 px-3 py-1.5 border-b border-theme bg-terminal-panel/80">
      <span class="text-[10px] text-theme-muted">归因周期</span>
      <select
        v-model="includeChildren"
        class="bg-theme-tertiary/30 border border-theme rounded px-1.5 py-0.5 text-[10px] text-theme-primary"
      >
        <option :value="false">仅本账户</option>
        <option :value="true">包含子账户</option>
      </select>
      <button
        @click="loadAttribution"
        :disabled="loading"
        class="ml-auto px-3 py-0.5 rounded text-[10px] font-medium transition-colors"
        :class="loading
          ? 'bg-gray-600/40 text-theme-muted cursor-not-allowed'
          : 'bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 border border-blue-500/40'"
      >{{ loading ? '⏳ 加载中...' : '🔄 刷新' }}</button>
    </div>

    <!-- 主内容区 -->
    <div v-if="data" class="flex-1 min-h-0 flex flex-col gap-2 p-2 overflow-y-auto">

      <!-- 风险指标行 -->
      <div v-if="data.risk_metrics" class="grid grid-cols-4 gap-2 shrink-0">
        <div
          v-for="m in riskCards"
          :key="m.label"
          class="rounded border border-theme bg-terminal-panel/60 px-2 py-1"
        >
          <div class="text-[8px] text-theme-muted truncate">{{ m.label }}</div>
          <div
            class="text-[11px] font-mono font-bold"
            :class="m.colorClass || 'text-theme-primary'"
          >{{ m.value }}</div>
        </div>
      </div>

      <!-- 图表区：左侧饼图 + 右侧柱图 -->
      <div class="flex-1 min-h-0 flex gap-2">

        <!-- 资产配置饼图 -->
        <div class="flex-1 min-w-0 flex flex-col">
          <div class="text-[9px] text-theme-muted mb-1 shrink-0">🕯️ 底层资产配置</div>
          <div ref="pieEl" class="flex-1 min-h-0" style="min-height: 160px;"></div>
        </div>

        <!-- 绩效归因柱状图 -->
        <div class="flex-1 min-w-0 flex flex-col">
          <div class="text-[9px] text-theme-muted mb-1 shrink-0">📊 盈亏贡献 (红=盈利, 绿=亏损)</div>
          <div ref="barEl" class="flex-1 min-h-0" style="min-height: 160px;"></div>
        </div>
      </div>

      <!-- 归因明细表 -->
      <div class="shrink-0 text-[9px]">
        <div class="flex items-center gap-1 mb-1">
          <span class="text-theme-muted">📋 归因明细</span>
          <span class="text-theme-muted">({{ data.attribution?.length || 0 }} 类底层资产)</span>
        </div>
        <div class="overflow-x-auto border border-theme/30 rounded">
          <table class="w-full">
            <thead class="bg-terminal-panel sticky top-0">
              <tr class="text-theme-muted border-b border-theme/20">
                <th class="px-2 py-0.5 text-left">类别</th>
                <th class="px-2 py-0.5 text-right">市值</th>
                <th class="px-2 py-0.5 text-right">权重</th>
                <th class="px-2 py-0.5 text-right">累计盈亏</th>
                <th class="px-2 py-0.5 text-right">贡献度</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="a in data.attribution"
                :key="a.category"
                class="border-b border-theme/10 hover:bg-theme-tertiary/20"
              >
                <td class="px-2 py-0.5">
                  <span class="text-theme-primary font-medium">{{ a.sub_category }}</span>
                  <span class="ml-1 text-[8px] text-theme-muted">{{ a.category }}</span>
                </td>
                <td class="px-2 py-0.5 text-right font-mono text-theme-primary">
                  {{ fmtYuan(a.market_value) }}
                </td>
                <td class="px-2 py-0.5 text-right font-mono text-theme-secondary">
                  {{ a.weight?.toFixed(1) }}%
                </td>
                <td
                  class="px-2 py-0.5 text-right font-mono font-bold"
                  :class="(a.pnl || 0) >= 0 ? 'text-bullish' : 'text-bearish'"
                >
                  {{ (a.pnl || 0) >= 0 ? '+' : '' }}{{ fmtYuan(a.pnl) }}
                </td>
                <td
                  class="px-2 py-0.5 text-right font-mono"
                  :class="(a.pnl_contrib_pct || 0) >= 0 ? 'text-bullish' : 'text-bearish'"
                >
                  {{ (a.pnl_contrib_pct || 0) >= 0 ? '+' : '' }}{{ a.pnl_contrib_pct?.toFixed(1) }}%
                </td>
              </tr>
              <!-- 合计行 -->
              <tr class="bg-terminal-panel/60 font-bold border-t border-theme/40">
                <td class="px-2 py-0.5 text-theme-primary">合计</td>
                <td class="px-2 py-0.5 text-right font-mono text-theme-primary">
                  {{ fmtYuan(data.summary?.total_market_value) }}
                </td>
                <td class="px-2 py-0.5 text-right font-mono text-theme-secondary">100%</td>
                <td
                  class="px-2 py-0.5 text-right font-mono font-bold"
                  :class="(data.summary?.total_pnl || 0) >= 0 ? 'text-bullish' : 'text-bearish'"
                >
                  {{ (data.summary?.total_pnl || 0) >= 0 ? '+' : '' }}{{ fmtYuan(data.summary?.total_pnl) }}
                </td>
                <td class="px-2 py-0.5 text-right font-mono text-theme-primary">—</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div
      v-else-if="!loading"
      class="flex-1 flex flex-col items-center justify-center text-theme-muted text-[11px] gap-2"
    >
      <span class="text-xl">🎯</span>
      <span>点击"刷新"加载归因分析</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { apiFetch } from '../utils/api.js'

const props = defineProps({
  portfolioId: { type: Number, required: true },
})

const includeChildren = ref(false)
const loading = ref(false)
const data = ref(null)
const pieEl  = ref(null)
const barEl  = ref(null)
let pieChart = null
let barChart = null

// ── 风险指标卡片 ──────────────────────────────────────────────
const riskCards = computed(() => {
  const m = data.value?.risk_metrics
  if (!m) return []
  return [
    { label: '日VaR(95%)', value: `${fmtYuan(m.var_daily_95)} (${m.var_daily_95_pct}%)`, colorClass: 'text-amber-400' },
    { label: '年化波动率', value: `${m.annual_volatility}%`, colorClass: m.annual_volatility > 20 ? 'text-bearish' : 'text-theme-primary' },
    { label: '夏普比率',   value: m.sharpe_ratio > 0 ? `+${m.sharpe_ratio}` : m.sharpe_ratio, colorClass: m.sharpe_ratio >= 1 ? 'text-bullish' : m.sharpe_ratio < 0 ? 'text-bearish' : 'text-theme-muted' },
    { label: '年化收益',  value: `${m.annual_return_pct >= 0 ? '+' : ''}${m.annual_return_pct}%`, colorClass: m.annual_return_pct >= 0 ? 'text-bullish' : 'text-bearish' },
  ]
})

// ── 加载归因数据 ───────────────────────────────────────────────
async function loadAttribution() {
  if (loading.value) return
  loading.value = true
  try {
    const resp = await apiFetch(
      `/api/v1/portfolio/${props.portfolioId}/attribution?include_children=${includeChildren.value}`
    )
    data.value = resp?.data || resp || {}
    await nextTick()
    renderCharts()
  } catch (e) {
    console.error('[AttributionPanel] loadAttribution error:', e)
  } finally {
    loading.value = false
  }
}

// ── 工具函数 ──────────────────────────────────────────────────
function fmtYuan(v) {
  if (v == null) return '--'
  v = Math.abs(v)
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(2) + '万'
  return v.toFixed(2)
}

// ── ECharts 渲染 ──────────────────────────────────────────────
function renderCharts() {
  if (!data.value) return
  renderPie()
  renderBar()
}

function renderPie() {
  if (!pieEl.value || !data.value?.total_exposure?.length) return
  if (pieChart) { pieChart.dispose(); pieChart = null }

  const exposure = data.value.total_exposure
  const COLORS = ['#60a5fa', '#34d399', '#fbbf24', '#f87171', '#c084fc', '#38bdf8', '#4ade80', '#fb923c']

  pieChart = window.echarts.init(pieEl.value, 'dark')
  pieChart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: '#1e2130', borderColor: '#374151',
      textStyle: { color: '#d1d5db', fontSize: 10 },
      formatter: (p) => `${p.name}<br/>市值: ${fmtYuan(p.value)}<br/>权重: ${p.percent?.toFixed(1)}%`,
    },
    legend: {
      orient: 'vertical', right: 2, top: 'center',
      textStyle: { color: '#9ca3af', fontSize: 9 },
      itemWidth: 8, itemHeight: 8,
    },
    series: [{
      type: 'pie',
      radius: ['35%', '65%'],
      center: ['35%', '50%'],
      label: { show: false },
      data: exposure.map((e, i) => ({
        name:  e.name,
        value: e.value,
        itemStyle: { color: COLORS[i % COLORS.length] },
      })),
    }],
  })
}

function renderBar() {
  if (!barEl.value || !data.value?.attribution?.length) return
  if (barChart) { barChart.dispose(); barChart = null }

  const attr = data.value.attribution
  const COLORS = attr.map(a => (a.pnl || 0) >= 0 ? '#14b143' : '#ef232a')

  barChart = window.echarts.init(barEl.value, 'dark')
  barChart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: '#1e2130', borderColor: '#374151',
      textStyle: { color: '#d1d5db', fontSize: 10 },
      formatter: (items) => {
        const it = items[0]
        return `${it.name}<br/><b style="color:${it.color}">${it.value >= 0 ? '+' : ''}${fmtYuan(it.value)}</b>`
      },
    },
    grid: { top: 4, bottom: 20, left: 4, right: 4, containLabel: true },
    xAxis: {
      type: 'category',
      data: attr.map(a => a.sub_category),
      axisLabel: { color: '#6b7280', fontSize: 8, rotate: 20, interval: 0 },
      axisLine: { lineStyle: { color: '#374151' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        color: '#6b7280', fontSize: 8,
        formatter: (v) => Math.abs(v) >= 1e4 ? (v / 1e4).toFixed(0) + 'w' : v.toFixed(0),
      },
      splitLine: { lineStyle: { color: '#1f2937' } },
    },
    series: [{
      type: 'bar',
      data: attr.map(a => ({
        value: a.pnl || 0,
        itemStyle: { color: (a.pnl || 0) >= 0 ? '#14b143' : '#ef232a' },
      })),
      barMaxWidth: 32,
      label: {
        show: true,
        position: 'top',
        color: '#9ca3af',
        fontSize: 8,
        formatter: (p) => `${p.value >= 0 ? '+' : ''}${(p.value / 1e4).toFixed(1)}w`,
      },
    }],
  })
}

// ── 生命周期 ──────────────────────────────────────────────────
onMounted(() => {
  loadAttribution()
})

onBeforeUnmount(() => {
  pieChart?.dispose()
  barChart?.dispose()
  pieChart = barChart = null
})

watch([() => props.portfolioId, includeChildren], () => {
  loadAttribution()
})

defineExpose({ loadAttribution })
</script>
