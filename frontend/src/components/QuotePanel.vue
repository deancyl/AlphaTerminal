<template>
  <div
    class="quote-panel flex flex-col bg-theme border-l border-theme overflow-y-auto"
    :class="isMobile ? 'panel-mobile' : 'panel-desktop'"
    :style="isMobile ? {} : { width: panelWidth + 'px' }"
  >
    <!-- ═══ Module 1: 基础行情与估值 ═════════════════════════════════ -->
    <div class="px-3 py-2.5 border-b border-theme">

      <!-- 标的标题 -->
      <div class="flex items-center justify-between mb-3">
        <div>
          <div class="text-[13px] font-bold text-theme-primary leading-tight">{{ panelName || symbol }}</div>
          <div class="text-[10px] text-theme-tertiary font-mono mt-0.5">{{ symbol }}</div>
        </div>
        <!-- 最新价（大字醒目） -->
        <div class="text-right">
          <div class="text-[28px] font-mono font-bold leading-none" :class="priceColorClass">
            {{ displayPrice }}
          </div>
          <div class="text-[12px] font-mono mt-1" :class="priceColorClass">
            <span>{{ displayChange }}</span>
            <span class="ml-1">({{ displayChangePct }})</span>
          </div>
        </div>
      </div>

      <!-- 基础盘口（加大行间距） -->
      <div class="space-y-2 mb-2">
        <div v-for="item in basicFields" :key="item.key" class="flex justify-between items-center">
          <span class="text-[11px] text-theme-tertiary">{{ item.label }}</span>
          <span class="text-[12px] font-mono font-medium text-theme-primary">{{ item.formatter(item.sourceFn ? item.sourceFn() : data[item.key]) }}</span>
        </div>
      </div>

      <!-- 周期收益率 -->
      <div class="border-t border-theme pt-2 mt-2">
        <div class="text-[10px] text-theme-tertiary mb-1.5 uppercase tracking-wider">周期收益率</div>
        <div class="grid grid-cols-3 gap-1">
          <div v-for="item in returnFields" :key="item.key"
               class="flex flex-col items-center bg-theme-secondary rounded py-1 px-1">
            <span class="text-[9px] text-theme-tertiary mb-0.5">{{ item.label }}</span>
            <span class="text-[11px] font-mono font-medium" :class="returnColorClass(data[item.key])">
              {{ data[item.key] != null ? (data[item.key] >= 0 ? '+' : '') + data[item.key].toFixed(2) + '%' : '--' }}
            </span>
          </div>
        </div>
      </div>

      <!-- 52周高低 -->
      <div class="border-t border-theme pt-2 mt-2">
        <div class="text-[10px] text-theme-tertiary mb-1.5 uppercase tracking-wider">52周区间</div>
        <div class="flex items-center gap-3">
          <div class="flex-1">
            <div class="text-[9px] text-theme-tertiary">高</div>
            <div class="text-[12px] font-mono text-bullish">{{ data.high_52w?.toFixed(2) ?? '--' }}</div>
            <div class="text-[9px] text-theme-muted">{{ data.high_52w_date ?? '' }}</div>
          </div>
          <!-- 可视化区间条 -->
          <div class="flex-1 flex flex-col items-center">
            <div class="relative w-full h-4 flex items-center">
              <div class="absolute inset-x-0 top-1/2 -translate-y-1/2 h-1 bg-theme-secondary rounded"></div>
              <div
                class="absolute top-1/2 -translate-y-1/2 w-2 h-2 rounded-full border-2 border-white shadow"
                :style="{ left: pricePosition + '%', backgroundColor: priceColor }"
              ></div>
            </div>
          </div>
          <div class="flex-1 text-right">
            <div class="text-[9px] text-theme-tertiary">低</div>
            <div class="text-[12px] font-mono text-bearish">{{ data.low_52w?.toFixed(2) ?? '--' }}</div>
            <div class="text-[9px] text-theme-muted">{{ data.low_52w_date ?? '' }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══ Module 2: 市场情绪（仅指数） ═════════════════════════════ -->
    <div class="px-3 py-2.5 border-b border-theme">
      <div class="text-[10px] text-theme-tertiary mb-2 uppercase tracking-wider">涨跌统计</div>
      <template v-if="isIndex">
        <div v-if="data.advance_count != null" class="flex items-stretch gap-1 h-14">
          <!-- 跌 -->
          <div class="flex-1 flex flex-col justify-end rounded-sm overflow-hidden bg-bearish/20">
            <div class="text-center text-[9px] text-bearish py-0.5">{{ data.decline_count }}家</div>
            <div class="bg-bearish rounded-sm" :style="{ height: (data.decline_count / totalStocks * 100) + '%', minHeight: '2px' }"></div>
          </div>
          <!-- 平 -->
          <div v-if="data.unchanged_count > 0" class="flex-1 flex flex-col justify-end rounded-sm overflow-hidden bg-theme-secondary">
            <div class="text-center text-[9px] text-theme-secondary py-0.5">{{ data.unchanged_count }}家</div>
            <div class="bg-theme-tertiary rounded-sm" :style="{ height: (data.unchanged_count / totalStocks * 100) + '%', minHeight: '2px' }"></div>
          </div>
          <!-- 涨 -->
          <div class="flex-1 flex flex-col justify-end rounded-sm overflow-hidden bg-bullish/20">
            <div class="text-center text-[9px] text-bullish py-0.5">{{ data.advance_count }}家</div>
            <div class="bg-bullish rounded-sm" :style="{ height: (data.advance_count / totalStocks * 100) + '%', minHeight: '2px' }"></div>
          </div>
        </div>
        <div v-if="data.advance_count != null" class="mt-1.5 flex justify-between text-[10px]">
          <span class="text-bearish">跌 {{ data.decline_count }}家</span>
          <span class="text-theme-secondary">平 {{ data.unchanged_count ?? 0 }}家</span>
          <span class="text-bullish">涨 {{ data.advance_count }}家</span>
        </div>
        <!-- 涨跌家比 -->
        <div v-if="data.advance_rate != null" class="mt-1 flex items-center gap-2">
          <div class="text-[10px] text-theme-tertiary">上涨压力</div>
          <div class="flex-1 h-1.5 bg-theme-secondary rounded-full overflow-hidden">
            <div class="h-full bg-gradient-to-r from-bearish to-bullish rounded-full"
                 :style="{ width: (data.advance_rate * 100) + '%' }"></div>
          </div>
          <div class="text-[10px] font-mono" :class="data.advance_rate >= 0.5 ? 'text-bullish' : 'text-bearish'">
            {{ (data.advance_rate * 100).toFixed(0) }}%
          </div>
        </div>
      </template>
      <div v-else class="text-[11px] text-theme-tertiary text-center py-3">
        个股暂无涨跌统计
      </div>
    </div>

    <!-- ═══ Module 3: 资金流向 ═══════════════════════════════════════ -->
    <div class="px-3 py-2.5 border-b border-theme">
      <div class="flex items-center justify-between mb-2">
        <div class="text-[10px] text-theme-tertiary uppercase tracking-wider">资金流向</div>
        <div v-if="fundDonutData.isMock" class="text-[9px] text-theme-muted italic">模拟数据</div>
      </div>

      <!-- 主环路：环形图 -->
      <div class="flex items-center gap-3 mb-3">
        <div ref="fundDonutRef" style="width:72px;height:72px;"></div>
        <div class="flex-1">
          <div class="text-[11px] text-theme-primary mb-1">主力净流入</div>
          <div class="text-[15px] font-mono font-bold" :class="fundDonutData.net >= 0 ? 'text-bullish' : 'text-bearish'">
            {{ fundDonutData.net >= 0 ? '+' : '' }}{{ formatAmount(fundDonutData.net) }}
          </div>
          <div class="flex gap-2 mt-1">
            <span class="text-[10px] text-bullish">入 {{ formatAmount(fundDonutData.inAmt) }}</span>
            <span class="text-[10px] text-bearish">出 {{ formatAmount(fundDonutData.outAmt) }}</span>
          </div>
        </div>
      </div>

      <!-- 各级拆解条 -->
      <div class="space-y-2">
        <div v-for="level in fundLevels" :key="level.label"
             class="flex items-center gap-2">
          <span class="text-[10px] text-theme-tertiary w-8 shrink-0">{{ level.label }}</span>
          <div class="flex-1 h-1.5 bg-theme-secondary rounded-full overflow-hidden">
            <div class="h-full rounded-full" :style="{ width: level.width + '%', backgroundColor: level.color }"></div>
          </div>
          <div class="flex flex-col items-end">
            <span class="text-[10px] font-mono" :class="level.inAmt >= 0 ? 'text-bullish' : 'text-bearish'">
              {{ level.inAmt >= 0 ? '+' : '' }}{{ formatAmount(level.inAmt) }}
            </span>
            <span class="text-[9px] font-mono" :class="level.outAmt >= 0 ? 'text-bullish' : 'text-bearish'">
              {{ level.outAmt >= 0 ? '+' : '' }}{{ formatAmount(level.outAmt) }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══ Module 4: 板块联动（个股） ════════════════════════════════ -->
    <div class="px-3 py-2.5 border-b border-theme">
      <div class="text-[10px] text-theme-tertiary mb-2 uppercase tracking-wider">板块联动</div>

      <template v-if="!isIndex && data.industry">
        <div class="flex items-center justify-between py-1 border-b border-theme-secondary">
          <span class="text-[11px] text-theme-primary">{{ data.industry }}</span>
          <span class="text-[11px] font-mono" :class="(data.industry_change_pct ?? 0) >= 0 ? 'text-bullish' : 'text-bearish'">
            {{ (data.industry_change_pct ?? 0) >= 0 ? '+' : '' }}{{ (data.industry_change_pct ?? 0).toFixed(2) }}%
          </span>
        </div>
      </template>

      <template v-if="data.concepts && data.concepts.length">
        <div class="flex flex-wrap gap-1 mt-2">
          <span v-for="c in data.concepts" :key="c.name"
                class="px-1.5 py-0.5 text-[10px] rounded border"
                :class="(c.change_pct ?? 0) >= 0
                  ? 'border-bullish/30 text-bullish bg-bullish/10'
                  : 'border-bearish/30 text-bearish bg-bearish/10'">
            {{ c.name }}
            <span class="ml-0.5">{{ (c.change_pct ?? 0) >= 0 ? '+' : '' }}{{ (c.change_pct ?? 0).toFixed(2) }}%</span>
          </span>
        </div>
      </template>

      <div v-if="isIndex" class="text-[11px] text-theme-tertiary text-center py-2">
        指数暂无板块归属
      </div>
      <div v-else-if="!data.industry && (!data.concepts || !data.concepts.length)"
           class="text-[11px] text-theme-tertiary text-center py-2">
        暂无板块数据
      </div>
    </div>

    <!-- ═══ 数据时间戳 ═══════════════════════════════════════════════ -->
    <div class="px-3 py-2 mt-auto">
      <div class="text-[9px] text-theme-muted text-center">
        {{ isCrosshair ? '📌 历史快照' : '🔴 实时' }} · {{ data.timestamp || '' }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'

const props = defineProps({
  symbol:       { type: String,  default: '' },
  name:         { type: String,  default: '' },
  // 十字光标历史快照（来自图表hover）
  snapshotData: { type: Object,  default: null },
  // 来自 quote_detail API 的聚合数据
  realtimeData: { type: Object,  default: () => ({}) },
  // 最新一根K线数据（来自图表渲染数据，最可靠）
  latestCandle: { type: Object,  default: null },
  isMobile:     { type: Boolean, default: false },
  panelWidth:   { type: Number,  default: 300 },
})

// snapshotData 优先，否则用 realtimeData + latestCandle 合并
const data = computed(() => props.snapshotData || props.realtimeData)
const isCrosshair = computed(() => !!props.snapshotData)

// 名称：优先用 realtimeData.name，其次 props.name
const panelName = computed(() => data.value.name || props.name || props.symbol)

// ── 图表K线数据（最可靠的价格来源）─────────────────────────────
// latestCandle 格式: { open, high, low, close, volume, change_pct, ... }
const cdl = computed(() => props.latestCandle)

// 最新价格（优先取K线数据，否则取API数据）
const displayPrice = computed(() => {
  if (cdl.value?.close != null) return cdl.value.close.toFixed(3)
  if (data.value.price != null && data.value.price > 0) return data.value.price.toFixed(3)
  return '--'
})

const displayChange = computed(() => {
  if (cdl.value?.change != null) {
    const c = cdl.value.change
    return (c >= 0 ? '+' : '') + c.toFixed(3)
  }
  if (data.value.change != null && data.value.change !== 0) {
    const c = data.value.change
    return (c >= 0 ? '+' : '') + c.toFixed(3)
  }
  return '--'
})

const displayChangePct = computed(() => {
  if (cdl.value?.change_pct != null) {
    const c = cdl.value.change_pct
    return (c >= 0 ? '+' : '') + c.toFixed(2) + '%'
  }
  if (data.value.change_pct != null && data.value.change_pct !== 0) {
    const c = data.value.change_pct
    return (c >= 0 ? '+' : '') + c.toFixed(2) + '%'
  }
  return '--'
})

// change_pct 用于颜色判定
const _changePct = computed(() => {
  if (cdl.value?.change_pct != null) return cdl.value.change_pct
  if (data.value.change_pct != null) return data.value.change_pct
  return null
})

// ── 颜色 ──────────────────────────────────────────────────────
const priceColor = computed(() => {
  const c = _changePct.value
  if (c == null) return '#9ca3af'
  return c >= 0 ? '#ef232a' : '#14b143'
})
const priceColorClass = computed(() => {
  const c = _changePct.value
  if (c == null) return 'text-gray-400'
  return c >= 0 ? 'text-red-400' : 'text-green-400'
})
// ── 52周位置 ───────────────────────────────────────────────────
const pricePosition = computed(() => {
  const { price, high_52w, low_52w } = data.value
  if (price == null || high_52w == null || low_52w == null) return 50
  if (high_52w === low_52w) return 50
  return Math.min(100, Math.max(0, ((price - low_52w) / (high_52w - low_52w)) * 100))
})

// ── 判断是否为指数 ──────────────────────────────────────────────
const INDEX_SET = new Set(['sh000001','sz000001','sh000300','sz399001','sz399006','sz000300'])
const isIndex = computed(() => INDEX_SET.has(props.symbol) || (data.value.market === 'AShare' && !data.value.pe_ttm))

// ── 涨跌家数 ───────────────────────────────────────────────────
const totalStocks = computed(() => {
  const { advance_count, decline_count, unchanged_count } = data.value
  if (advance_count == null) return 1
  return (advance_count || 0) + (decline_count || 0) + (unchanged_count || 0) || 1
})

// ── 基础字段（优先取最新K线数据，降级到API数据）─────────────────
function candleVal(key) { return cdl.value?.[key] ?? data.value?.[key] }
function candleOr(key, fallback) {
  const v = candleVal(key)
  return v != null && v !== 0 ? v : fallback
}

const basicFields = [
  { key: 'open',   label: '开盘',   sourceFn: () => candleOr('open',   null), formatter: v => v != null ? v.toFixed(3) : '--' },
  { key: 'high',   label: '最高',   sourceFn: () => candleOr('high',   null), formatter: v => v != null ? v.toFixed(3) : '--' },
  { key: 'low',    label: '最低',   sourceFn: () => candleOr('low',    null), formatter: v => v != null ? v.toFixed(3) : '--' },
  { key: 'volume', label: '成交量', sourceFn: () => candleOr('volume', null), formatter: v => (v == null || v === 0) ? '--' : formatVol(v) },
  { key: 'amount', label: '成交额', sourceFn: () => candleOr('amount', null), formatter: v => (v == null || v === 0) ? '--' : formatAmount(v) },
  { key: 'turnover_rate', label: '换手率', sourceFn: () => data.value.turnover_rate ?? null,
    formatter: v => (v == null || v === 0) ? '--' : v.toFixed(2) + '%' },
  { key: 'amplitude',     label: '振幅',   sourceFn: () => data.value.amplitude ?? null,
    formatter: v => (v == null || v === 0) ? '--' : v.toFixed(2) + '%' },
  { key: 'pe_ttm', label: '市盈率TTM', sourceFn: () => data.value.pe_ttm ?? null,
    formatter: v => (v == null || v === 0) ? '--' : v.toFixed(2) },
]

// ── 估值字段 ───────────────────────────────────────────────────
const valuationFields = [
  { key: 'pe_ttm', label: '市盈率TTM', formatter: v => (v == null || v === 0) ? '--' : v.toFixed(2) },
  { key: 'pb',     label: '市净率',   formatter: v => (v == null || v === 0) ? '--' : v.toFixed(2) },
]

// ── 周期收益字段（后端未返回这些字段，始终显示 --）───────────────────
const returnFields = [
  { key: 'returns_5d',  label: '5日' },
  { key: 'returns_20d', label: '20日' },
  { key: 'returns_60d', label: '60日' },
]

function returnColorClass(v) {
  if (v == null) return 'text-gray-400'
  return v >= 0 ? 'text-red-400' : 'text-green-400'
}

// ── 资金流向（mock数据填充UI占位）──────────────────────────────
const fundFlowMock = {
  main_net:   12.8e8,   // 主力净流入 +12.8亿
  main_in:    35.2e8,
  main_out:   22.4e8,
  huge_in:    8.6e8, huge_out:  4.1e8,
  big_in:     15.3e8, big_out:   10.2e8,
  medium_in:  11.3e8, medium_out: 8.1e8,
  small_in:   8.2e8, small_out:  6.5e8,
}

const fundLevels = computed(() => {
  const d = data.value
  const hasReal = d.fund_main_net != null
  const mock = hasReal ? false : true

  const net   = hasReal ? (d.fund_main_net ?? 0)  : fundFlowMock.main_net
  const netIn  = hasReal ? (d.fund_main_in ?? 0)  : fundFlowMock.main_in
  const netOut = hasReal ? (d.fund_main_out ?? 0) : fundFlowMock.main_out
  const total  = Math.abs(netIn) + Math.abs(netOut) || 1

  const toPct = v => Math.min(100, Math.max(0, Math.abs(v) / total * 100))

  return [
    { label: '超大单', color: '#f87171',
      inAmt: hasReal ? d.fund_huge_in : fundFlowMock.huge_in,
      outAmt: hasReal ? d.fund_huge_out : fundFlowMock.huge_out,
      width: toPct(hasReal ? d.fund_huge_in : fundFlowMock.huge_in) },
    { label: '大单',   color: '#fb923c',
      inAmt: hasReal ? d.fund_big_in : fundFlowMock.big_in,
      outAmt: hasReal ? d.fund_big_out : fundFlowMock.big_out,
      width: toPct(hasReal ? d.fund_big_in : fundFlowMock.big_in) },
    { label: '中单',   color: '#fbbf24',
      inAmt: hasReal ? d.fund_medium_in : fundFlowMock.medium_in,
      outAmt: hasReal ? d.fund_medium_out : fundFlowMock.medium_out,
      width: toPct(hasReal ? d.fund_medium_in : fundFlowMock.medium_in) },
    { label: '小单',   color: '#6ee7b7',
      inAmt: hasReal ? d.fund_small_in : fundFlowMock.small_in,
      outAmt: hasReal ? d.fund_small_out : fundFlowMock.small_out,
      width: toPct(hasReal ? d.fund_small_in : fundFlowMock.small_in) },
  ]
})

// 资金环形图数据（始终有值）
const fundDonutData = computed(() => {
  const d = data.value
  const hasReal = d.fund_main_net != null
  return {
    net:   hasReal ? d.fund_main_net  : fundFlowMock.main_net,
    inAmt: hasReal ? d.fund_main_in   : fundFlowMock.main_in,
    outAmt:hasReal ? d.fund_main_out  : fundFlowMock.main_out,
    isMock: d.fund_main_net == null,
  }
})

// ── 格式化 ─────────────────────────────────────────────────────
function formatVol(v) {
  if (v == null) return '--'
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿股'
  if (v >= 1e4) return (v / 1e4).toFixed(2) + '万股'
  return v.toFixed(0) + '股'
}
function formatAmount(v) {
  if (v == null) return '--'
  if (Math.abs(v) >= 1e8) return (v / 1e8).toFixed(2) + '亿元'
  if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(2) + '万元'
  return (v >= 0 ? '+' : '') + v.toFixed(0) + '元'
}

// ── 资金环形图（ECharts）───────────────────────────────────────
const fundDonutRef = ref(null)
let donutInstance = null

function renderDonut() {
  if (!fundDonutRef.value || !window.echarts) return
  const fd = fundDonutData.value
  if (!fd) return

  if (!donutInstance) {
    donutInstance = window.echarts.init(fundDonutRef.value, null, { renderer: 'canvas' })
  }

  donutInstance.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      show: true,
      trigger: 'item',
      backgroundColor: 'rgba(26,30,46,0.95)',
      borderColor: '#4b5563',
      textStyle: { color: '#9ca3af', fontSize: 10 },
      formatter: '{b}: {c} ({d}%)',
    },
    series: [{
      type: 'pie',
      radius: ['50%', '78%'],
      center: ['50%', '50%'],
      avoidLabelOverlap: false,
      label: { show: false },
      data: [
        { value: fd.inAmt,  name: '流入', itemStyle: { color: '#ef232a' } },
        { value: fd.outAmt, name: '流出', itemStyle: { color: '#14b143' } },
      ],
    }],
  })
}

watch(() => fundDonutData.value, () => { nextTick(renderDonut) }, { deep: true, immediate: true })

let _donutRO = null
onMounted(() => {
  nextTick(renderDonut)
  if (fundDonutRef.value) {
    _donutRO = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect
      if (width > 0 && height > 0) {
        console.debug(`[ECharts] 📐 resize QuotePanel donut @ ${width.toFixed(0)}×${height.toFixed(0)}`)
        donutInstance?.resize()
      }
    })
    _donutRO.observe(fundDonutRef.value)
  }
})
onUnmounted(() => {
  _donutRO?.disconnect()
  if (donutInstance) {
    console.debug('[ECharts] 🗑️  disposed instance for: QuotePanel donut')
    donutInstance.dispose()
    donutInstance = null
  }
})
</script>

<style scoped>
.panel-desktop {
  height: 100%;
  min-width: 280px;
  max-width: 360px;
  flex-shrink: 0;
}
.panel-mobile {
  width: 100%;
  max-height: 50vh;
  border-left: none;
  border-top: 1px solid var(--border-primary);
}

/* 滚动条样式 */
.quote-panel::-webkit-scrollbar { width: 4px; }
.quote-panel::-webkit-scrollbar-track { background: transparent; }
.quote-panel::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 2px; }
</style>
