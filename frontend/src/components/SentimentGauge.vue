<template>
  <div class="flex flex-col gap-2 h-full overflow-visible">

    <!-- ── A股上涨家数折线图（全天走势，15秒轮询）───────────── -->
    <div class="bg-terminal-bg rounded-sm border border-theme p-2">
      <div class="flex items-center justify-between mb-1">
        <span class="text-[10px] text-terminal-dim">📈 全天走势</span>
        <span class="text-[10px] text-terminal-dim">{{ intradayUpdateTime }}</span>
      </div>
      <!-- ECharts 折线图：上涨家数全天走势 -->
      <div ref="intradayEl" class="w-full" :style="{ height: intradayHeight + 'px' }"></div>
    </div>

    <!-- ── A股涨跌分布直方图 ─────────────────────────────────── -->
    <div class="bg-terminal-bg rounded-sm border border-theme p-3">
      <!-- 标题栏：情绪 + 资讯面（移动端由外层panel提供标题，这里不重复） -->
      <div class="flex items-center justify-between mb-2">
        <div class="flex items-center gap-2">
          <!-- Phase 4: 资讯情绪徽标 -->
          <span
            v-if="newsSentiment.total_count > 0"
            class="text-[10px] px-1.5 py-0.5 rounded-sm border"
            :class="newsSentiment.bullish_count - newsSentiment.bearish_count > 0
              ? 'border-bullish/40 bg-bullish/10 text-bullish'
              : newsSentiment.bullish_count - newsSentiment.bearish_count < 0
                ? 'border-bearish/40 bg-bearish/10 text-bearish'
                : 'border-theme-secondary bg-theme-tertiary/10 text-theme-secondary'"
          >
            📰 资讯面: {{ newsSentiment.label }} ({{ newsSentiment.bullish_count }}:{{ newsSentiment.bearish_count }})
          </span>
          <span class="text-[10px] font-mono text-terminal-dim">{{ data.timestamp || '加载中...' }}</span>
        </div>
      </div>

      <!-- Phase 4: 大字汇总行 -->
      <div class="flex items-center justify-between mb-2 px-1 py-1.5 rounded-sm bg-terminal-panel/60 border border-theme/60">
        <span class="text-bullish font-bold text-sm">
          🚀 上涨: <span class="font-mono text-base">{{ data.advance || 0 }}</span> 家
        </span>
        <span class="text-[var(--color-warning)] font-bold text-sm">
          ➖ 平盘: <span class="font-mono text-base">{{ data.unchanged || 0 }}</span> 家
        </span>
        <span class="text-bearish font-bold text-sm">
          🟩 下跌: <span class="font-mono text-base">{{ data.decline || 0 }}</span> 家
        </span>
      </div>

      <!-- ECharts 柱状图 -->
      <div ref="chartEl" class="w-full" :style="{ height: chartHeight + 'px' }"></div>

      <!-- 涨跌标签行 -->
      <div class="flex justify-between mt-1 text-[10px] text-terminal-dim">
        <span>涨 {{ data.advance || 0 }} ({{ upPct }}%)</span>
        <span>平 {{ data.unchanged || 0 }}</span>
        <span>跌 {{ data.decline || 0 }} ({{ downPct }}%)</span>
      </div>

      <!-- 底部统计 -->
      <div class="flex justify-between mt-2 text-[10px] border-t border-theme pt-2">
        <span class="text-bullish">🔴 涨停 {{ data.limit_up || 0 }}</span>
        <span class="text-bearish">🟢 跌停 {{ data.limit_down || 0 }}</span>
        <span class="text-terminal-dim">全市场 {{ data.total || 0 }} 只</span>
      </div>
    </div>

    <!-- ── 简版行情列表（h-full 响应式填充，移除硬编码 max-height）────── -->
    <div class="overflow-y-auto flex-1 min-h-[250px]">
      <table class="w-full text-xs">
        <thead>
          <tr class="text-terminal-dim border-b border-theme">
            <th class="text-left py-1">指数</th>
            <th class="text-right py-1">最新价</th>
            <th class="text-right py-1">涨跌幅</th>
            <th class="text-right py-1">状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, key) in allItems" :key="key"
              class="border-b border-theme-secondary hover:bg-theme-hover cursor-pointer transition-colors"
              @click="$emit('symbol-click', { symbol: item.key, name: item.name })">
            <td class="py-1.5 text-theme-primary">{{ item.name }}</td>
            <td class="py-1.5 text-right font-mono">{{ formatPrice(item.index || item.price) }}</td>
            <td class="py-1.5 text-right font-mono"
                :class="(item.change_pct || 0) >= 0 ? 'text-bullish' : 'text-bearish'">
              {{ (item.change_pct || 0) >= 0 ? '+' : '' }}{{ (item.change_pct || 0).toFixed(2) }}%
            </td>
            <td class="py-1.5 text-right">
              <span class="px-1 py-0.5 rounded-sm text-[10px]"
                    :class="item.status === '交易中' ? 'bg-theme-tertiary/40 text-theme-accent' : 'bg-theme-tertiary/30 text-theme-secondary'">
                {{ item.status }}
              </span>
            </td>
          </tr>
          <tr v-if="!windItems.length">
            <td colspan="4" class="py-4 text-center text-terminal-dim text-xs">暂无数据</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { logger } from '../utils/logger.js'
import { on as busOn } from '../composables/useEventBus.js'
import { apiFetch } from '../utils/api.js'
import { formatPrice } from '../utils/formatters.js'

const props = defineProps({
  marketData: { type: Object, default: null },
  macroData:  { type: Array,  default: () => [] },
})
defineEmits(['symbol-click'])

const chartEl        = ref(null)
const chartHeight     = 150
const intradayEl      = ref(null)
const intradayHeight  = 120
let   chartInst       = null
let   intradayInst    = null
let   refreshTimer    = null
let   intradayTimer   = null
let   resizeObserver  = null
let   unsubNewsRefresh = null

// 上涨家数全天走势数据（每15秒轮询追加一个点，最多240个点=1小时）
const intradayData = ref([])   // [{time: '09:31', advance: 1234}, ...]
const intradayUpdateTime = ref('')

const UP   = '#ef232a'
const DOWN = '#14b143'

const data = ref({
  buckets: [], total: 0,
  advance: 0, decline: 0, unchanged: 0,
  limit_up: 0, limit_down: 0,
  up_ratio: 0.0, timestamp: '',
})

// Phase 4: 资讯情绪（来自 /market/sentiment/histogram 返回的 news_sentiment 字段）
const newsSentiment = ref({
  score: 0.0, label: '中性',
  bullish_count: 0, bearish_count: 0,
  total_count: 0, keywords: [], timestamp: '',
})

const windItems = computed(() => {
  // 修复: marketData 从 DashboardGrid 传来时就是 wind 对象本身（不是 {wind: {...}}）
  return props.marketData || {}
})
const macroItems = computed(() => props.macroData || [])
const allItems = computed(() => {
  const wind = Object.entries(windItems.value || {}).map(([key, value]) => ({ key, ...value }))
  const macro = macroItems.value.map((item, index) => ({ key: `macro_${index}`, ...item }))
  return [...wind, ...macro]
})

const upPct = computed(() => {
  const t = data.value.total || 1
  return ((data.value.advance / t) * 100).toFixed(2)
})

const downPct = computed(() => {
  const t = data.value.total || 1
  return ((data.value.decline / t) * 100).toFixed(2)
})

// ── ECharts 折线图：上涨家数全天走势 ─────────────────────────────
function buildIntradayOption(series) {
  if (!series || !series.length) return {}
  const times   = series.map(d => d.time)
  const advance = series.map(d => d.advance)
  const decline = series.map(d => d.decline)

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(26,30,46,0.96)',
      borderColor: '#4b5563',
      textStyle: { color: '#9ca3af', fontSize: 10 },
      formatter: (params) => {
        const p = params[0]
        return `<span style="color:#6b7280;font-size:9px">${p.name}</span><br/>`
          + params.map(s => `<span style="color:${s.color};font-size:10px">${s.seriesName}: <b>${s.value}</b>家</span>`).join('<br/>')
      },
    },
    legend: {
      data: ['上涨', '下跌'],
      top: 0, right: 4,
      textStyle: { color: '#9ca3af', fontSize: 8 },
      icon: 'roundRect',
      itemWidth: 12, itemHeight: 6,
    },
    grid: { top: 20, right: 8, bottom: 16, left: 40, containLabel: false },
    xAxis: {
      type: 'category',
      data: times,
      axisLabel: { color: '#4b5563', fontSize: 8, rotate: 0 },
      axisLine: { lineStyle: { color: '#2d3748' } },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLabel: {
        color: '#4b5563', fontSize: 8,
        formatter: v => v >= 1000 ? (v/1000).toFixed(0)+'k' : v,
      },
      splitLine: { lineStyle: { color: '#1f2937', type: 'dashed' } },
      axisLine: { show: false },
    },
    series: [
      {
        name: '上涨',
        type: 'line',
        data: advance,
        smooth: true,
        lineStyle: { color: '#ef232a', width: 1.5 },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(239,35,42,0.20)' },
              { offset: 1, color: 'rgba(239,35,42,0.01)' },
            ],
          },
        },
        symbol: 'none',
      },
      {
        name: '下跌',
        type: 'line',
        data: decline,
        smooth: true,
        lineStyle: { color: '#14b143', width: 1.5 },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(20,177,67,0.20)' },
              { offset: 1, color: 'rgba(20,177,67,0.01)' },
            ],
          },
        },
        symbol: 'none',
      },
    ],
  }
}

function initIntradayChart() {
  if (!intradayEl.value || !window.echarts) return
  intradayInst = window.echarts.init(intradayEl.value, null, { renderer: 'canvas' })
  intradayInst.setOption(buildIntradayOption(intradayData.value))
}

async function fetchIntraday() {
  try {
    // apiFetch 自动解包: 返回 d.data (标准格式) 或 d (旧格式)
    const d = await apiFetch('/api/v1/market/sentiment/intraday')
    if (!d) return
    // d 已经是解包后的对象，直接访问 intraday
    const intraday = d.intraday || []
    if (intraday.length > 0) {
      intradayData.value = intraday
      intradayUpdateTime.value = d.timestamp ? new Date(d.timestamp).toLocaleTimeString('zh-CN', { hour12: false }) : ''
      if (intradayInst) {
        intradayInst.setOption(buildIntradayOption(intradayData.value), true)
      }
    }
  } catch (e) {
    logger.warn('[SentimentGauge] intraday fetch failed:', e.message)
  }
}

// ── ECharts 直方图 ────────────────────────────────────────────────
function buildHistogramOption(buckets) {
  if (!buckets || !buckets.length) return {}
  const labels  = buckets.map(b => b.label)
  const counts  = buckets.map(b => b.count)
  const colors  = buckets.map(b => {
    // 直接使用后端返回的颜色（后端已按 A 股颜色约定赋值）
    // 后端约定：绿色=#14b143(跌)，红色=#ef232a(涨)，灰色=#4b5563(平盘)
    if (b.label === "平盘(0%)") return '#4b5563'
    return b.color || (b.label.includes("涨") ? UP : DOWN)
  })

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(26,30,46,0.96)',
      borderColor: '#4b5563',
      textStyle: { color: '#9ca3af', fontSize: 11 },
      formatter: (params) => {
        const p = params[0]
        return `<span style="color:#6b7280;font-size:10px">${p.name}</span><br/>`
          + `<span style="color:${p.color};font-size:12px;font-weight:bold">${p.value} 家</span>`
      },
    },
    grid: { top: 4, right: 4, bottom: 20, left: 4, containLabel: true },
    xAxis: {
      type: 'category',
      data: labels,
      axisLabel: {
        color: '#6b7280', fontSize: 8,
        interval: 0,
        rotate: 30,
        formatter: v => v.replace('%', '').replace('~', '~'),
      },
      axisLine: { lineStyle: { color: '#2d3748' } },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLabel: { color: '#6b7280', fontSize: 8,
        formatter: v => v >= 1000 ? (v/1000).toFixed(0)+'k' : v },
      splitLine: { lineStyle: { color: '#1f2937', type: 'dashed' } },
      axisLine: { show: false },
    },
    series: [{
      name: '家数',
      type: 'bar',
      data: counts.map((c, i) => ({ value: c, itemStyle: { color: colors[i], borderRadius: i === 5 ? [2,2,0,0] : (i < 5 ? [2,2,0,0] : [0,0,2,2]) } })),
      barMaxWidth: 28,
      label: { show: counts.map(c => c > 0), position: 'top', fontSize: 8, color: '#9ca3af',
        formatter: p => p.value > 0 ? p.value : '' },
    }],
  }
}

function initChart() {
  if (!chartEl.value || !window.echarts) return
  chartInst = window.echarts.init(chartEl.value, null, { renderer: 'canvas' })
  chartInst.setOption(buildHistogramOption(data.value.buckets))
}

async function fetchHistogram() {
  try {
    // apiFetch 自动解包: 返回 d.data (标准格式) 或 d (旧格式)
    const payload = await apiFetch('/api/v1/market/sentiment/histogram')
    if (!payload) return
    // Phase 4: 提取 news_sentiment 字段
    if (payload.news_sentiment) {
      newsSentiment.value = {
        score:         payload.news_sentiment.score         ?? 0.0,
        label:          payload.news_sentiment.label          ?? '中性',
        bullish_count:  payload.news_sentiment.bullish_count ?? 0,
        bearish_count:  payload.news_sentiment.bearish_count ?? 0,
        total_count:    payload.news_sentiment.total_count   ?? 0,
        keywords:       payload.news_sentiment.keywords      ?? [],
        timestamp:      payload.news_sentiment.timestamp     ?? '',
      }
    }
    data.value = payload
    if (chartInst) {
      chartInst.setOption(buildHistogramOption(payload.buckets), true)
    }
  } catch (e) {
    logger.warn('[SentimentGauge] fetch failed:', e.message)
  }
}

const debouncedUpdate = useDebounceFn(() => {
  if (chartInst) chartInst.setOption(buildHistogramOption(data.value.buckets), true)
}, 150)

watch(data, () => { debouncedUpdate() })

onMounted(async () => {
  await fetchHistogram()
  await new Promise(r => setTimeout(r, 0))
  initChart()
  initIntradayChart()

  // 折线图：每15秒轮询上涨家数走势
  await fetchIntraday()
  intradayTimer = setInterval(fetchIntraday, 15_000)

  resizeObserver = new ResizeObserver(() => {
    chartInst?.resize()
    intradayInst?.resize()
  })
  if (chartEl.value) resizeObserver.observe(chartEl.value)
  if (intradayEl.value) resizeObserver.observe(intradayEl.value)
  refreshTimer = setInterval(fetchHistogram, 3 * 60 * 1000)

  // Phase 4: 监听 NewsFeed 刷新事件，联动拉取最新情绪数据
  unsubNewsRefresh = busOn('news-refreshed', (payload) => {
    logger.log('[SentimentGauge] news-refreshed event, re-fetching...', payload)
    fetchHistogram()
  })
})

onUnmounted(() => {
  clearInterval(refreshTimer)
  clearInterval(intradayTimer)
  resizeObserver?.disconnect()
  unsubNewsRefresh?.()
  chartInst?.dispose()
  intradayInst?.dispose()
})
</script>
