<template>
  <div
    class="quote-panel flex flex-col bg-[#0d1220] border-l border-gray-700/50 overflow-y-auto"
    :class="isMobile ? 'panel-mobile' : 'panel-desktop'"
    :style="isMobile ? {} : { width: panelWidth + 'px' }"
  >
    <!-- ═══ Module 1: 基础行情与估值 ═════════════════════════════════ -->
    <div class="px-3 py-2.5 border-b border-gray-700/40">

      <!-- 标的标题 -->
      <div class="flex items-center justify-between mb-2">
        <div>
          <div class="text-[13px] font-bold text-gray-100 leading-tight">{{ data.name || symbol }}</div>
          <div class="text-[10px] text-gray-500 font-mono mt-0.5">{{ symbol }}</div>
        </div>
        <div class="text-right">
          <div class="text-[18px] font-mono font-bold" :class="priceColorClass">
            {{ data.price != null ? data.price.toFixed(3) : '--' }}
          </div>
          <div class="text-[11px] font-mono mt-0.5" :class="priceColorClass">
            <span>{{ data.change >= 0 ? '+' : '' }}{{ data.change?.toFixed(3) ?? '--' }}</span>
            <span class="ml-1">({{ data.change_pct >= 0 ? '+' : '' }}{{ data.change_pct?.toFixed(2) ?? '--' }}%)</span>
          </div>
        </div>
      </div>

      <!-- 基础盘口 -->
      <div class="grid grid-cols-4 gap-x-2 gap-y-1 mb-2">
        <div v-for="item in basicFields" :key="item.key" class="flex justify-between items-center">
          <span class="text-[10px] text-gray-500">{{ item.label }}</span>
          <span class="text-[11px] font-mono text-gray-200">{{ item.formatter(data[item.key]) }}</span>
        </div>
      </div>

      <!-- 估值与振幅 -->
      <div class="border-t border-gray-700/30 pt-2 mt-1">
        <div class="text-[10px] text-gray-500 mb-1.5 uppercase tracking-wider">估值与振幅</div>
        <div class="grid grid-cols-2 gap-x-3 gap-y-1">
          <div v-for="item in valuationFields" :key="item.key" class="flex justify-between items-center">
            <span class="text-[10px] text-gray-500">{{ item.label }}</span>
            <span class="text-[11px] font-mono" :class="item.valueClass ? item.valueClass(data[item.key]) : 'text-gray-200'">
              {{ item.formatter ? item.formatter(data[item.key]) : (data[item.key] != null ? data[item.key] : '--') }}
            </span>
          </div>
        </div>
      </div>

      <!-- 周期收益率 -->
      <div class="border-t border-gray-700/30 pt-2 mt-2">
        <div class="text-[10px] text-gray-500 mb-1.5 uppercase tracking-wider">周期收益率</div>
        <div class="grid grid-cols-3 gap-1">
          <div v-for="item in returnFields" :key="item.key"
               class="flex flex-col items-center bg-black/20 rounded py-1 px-1">
            <span class="text-[9px] text-gray-500 mb-0.5">{{ item.label }}</span>
            <span class="text-[11px] font-mono font-medium" :class="returnColorClass(data[item.key])">
              {{ data[item.key] != null ? (data[item.key] >= 0 ? '+' : '') + data[item.key].toFixed(2) + '%' : '--' }}
            </span>
          </div>
        </div>
      </div>

      <!-- 52周高低 -->
      <div class="border-t border-gray-700/30 pt-2 mt-2">
        <div class="text-[10px] text-gray-500 mb-1.5 uppercase tracking-wider">52周区间</div>
        <div class="flex items-center gap-3">
          <div class="flex-1">
            <div class="text-[9px] text-gray-500">高</div>
            <div class="text-[12px] font-mono text-red-400">{{ data.high_52w?.toFixed(2) ?? '--' }}</div>
            <div class="text-[9px] text-gray-600">{{ data.high_52w_date ?? '' }}</div>
          </div>
          <!-- 可视化区间条 -->
          <div class="flex-1 flex flex-col items-center">
            <div class="relative w-full h-4 flex items-center">
              <div class="absolute inset-x-0 top-1/2 -translate-y-1/2 h-1 bg-gray-700 rounded"></div>
              <div
                class="absolute top-1/2 -translate-y-1/2 w-2 h-2 rounded-full border-2 border-white shadow"
                :style="{ left: pricePosition + '%', backgroundColor: priceColor }"
              ></div>
            </div>
          </div>
          <div class="flex-1 text-right">
            <div class="text-[9px] text-gray-500">低</div>
            <div class="text-[12px] font-mono text-green-400">{{ data.low_52w?.toFixed(2) ?? '--' }}</div>
            <div class="text-[9px] text-gray-600">{{ data.low_52w_date ?? '' }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══ Module 2: 市场情绪（仅指数） ═════════════════════════════ -->
    <div class="px-3 py-2.5 border-b border-gray-700/40">
      <div class="text-[10px] text-gray-500 mb-2 uppercase tracking-wider">涨跌统计</div>
      <template v-if="isIndex">
        <div v-if="data.advance_count != null" class="flex items-stretch gap-1 h-14">
          <!-- 跌 -->
          <div class="flex-1 flex flex-col justify-end rounded-sm overflow-hidden bg-green-500/20">
            <div class="text-center text-[9px] text-green-400 py-0.5">{{ data.decline_count }}家</div>
            <div class="bg-green-500 rounded-sm" :style="{ height: (data.decline_count / totalStocks * 100) + '%', minHeight: '2px' }"></div>
          </div>
          <!-- 平 -->
          <div v-if="data.unchanged_count > 0" class="flex-1 flex flex-col justify-end rounded-sm overflow-hidden bg-gray-600/20">
            <div class="text-center text-[9px] text-gray-400 py-0.5">{{ data.unchanged_count }}家</div>
            <div class="bg-gray-500 rounded-sm" :style="{ height: (data.unchanged_count / totalStocks * 100) + '%', minHeight: '2px' }"></div>
          </div>
          <!-- 涨 -->
          <div class="flex-1 flex flex-col justify-end rounded-sm overflow-hidden bg-red-500/20">
            <div class="text-center text-[9px] text-red-400 py-0.5">{{ data.advance_count }}家</div>
            <div class="bg-red-500 rounded-sm" :style="{ height: (data.advance_count / totalStocks * 100) + '%', minHeight: '2px' }"></div>
          </div>
        </div>
        <div v-if="data.advance_count != null" class="mt-1.5 flex justify-between text-[10px]">
          <span class="text-green-400">跌 {{ data.decline_count }}家</span>
          <span class="text-gray-500">平 {{ data.unchanged_count ?? 0 }}家</span>
          <span class="text-red-400">涨 {{ data.advance_count }}家</span>
        </div>
        <!-- 涨跌家比 -->
        <div v-if="data.advance_rate != null" class="mt-1 flex items-center gap-2">
          <div class="text-[10px] text-gray-500">上涨压力</div>
          <div class="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
            <div class="h-full bg-gradient-to-r from-green-500 to-red-500 rounded-full"
                 :style="{ width: (data.advance_rate * 100) + '%' }"></div>
          </div>
          <div class="text-[10px] font-mono" :class="data.advance_rate >= 0.5 ? 'text-red-400' : 'text-green-400'">
            {{ (data.advance_rate * 100).toFixed(0) }}%
          </div>
        </div>
      </template>
      <div v-else class="text-[11px] text-gray-500 text-center py-3">
        个股暂无涨跌统计
      </div>
    </div>

    <!-- ═══ Module 3: 资金流向 ═══════════════════════════════════════ -->
    <div class="px-3 py-2.5 border-b border-gray-700/40">
      <div class="text-[10px] text-gray-500 mb-2 uppercase tracking-wider">资金流向</div>

      <template v-if="data.fund_main_net != null">
        <!-- 主环路：环形图 -->
        <div class="flex items-center gap-3 mb-3">
          <div ref="fundDonutRef" style="width:72px;height:72px;"></div>
          <div class="flex-1">
            <div class="text-[11px] text-gray-300 mb-1">主力净流入</div>
            <div class="text-[15px] font-mono font-bold" :class="data.fund_main_net >= 0 ? 'text-red-400' : 'text-green-400'">
              {{ data.fund_main_net >= 0 ? '+' : '' }}{{ formatAmount(data.fund_main_net) }}
            </div>
            <div class="flex gap-2 mt-1">
              <span class="text-[10px] text-red-400">入 {{ formatAmount(data.fund_main_in) }}</span>
              <span class="text-[10px] text-green-400">出 {{ formatAmount(data.fund_main_out) }}</span>
            </div>
          </div>
        </div>
        <!-- 各级拆解 -->
        <div class="space-y-1.5">
          <div v-for="level in fundLevels" :key="level.key"
               class="flex items-center gap-2">
            <span class="text-[10px] text-gray-500 w-8 shrink-0">{{ level.label }}</span>
            <div class="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
              <div class="h-full rounded-full" :style="{ width: level.width + '%', backgroundColor: level.color }"></div>
            </div>
            <span class="text-[10px] font-mono w-14 text-right" :class="level.value >= 0 ? 'text-red-400' : 'text-green-400'">
              {{ level.value >= 0 ? '+' : '' }}{{ formatAmount(level.value) }}
            </span>
          </div>
        </div>
      </template>

      <template v-else>
        <!-- 暂无数据占位 -->
        <div class="flex flex-col items-center py-4">
          <div class="text-2xl mb-2 opacity-30">💧</div>
          <div class="text-[11px] text-gray-500 text-center">资金流向数据需券商数据接口</div>
          <div class="text-[10px] text-gray-600 mt-1">当前为模拟展示结构</div>
        </div>
      </template>
    </div>

    <!-- ═══ Module 4: 板块联动（个股） ════════════════════════════════ -->
    <div class="px-3 py-2.5 border-b border-gray-700/40">
      <div class="text-[10px] text-gray-500 mb-2 uppercase tracking-wider">板块联动</div>

      <template v-if="!isIndex && data.industry">
        <div class="flex items-center justify-between py-1 border-b border-gray-800">
          <span class="text-[11px] text-gray-300">{{ data.industry }}</span>
          <span class="text-[11px] font-mono" :class="(data.industry_change_pct ?? 0) >= 0 ? 'text-red-400' : 'text-green-400'">
            {{ (data.industry_change_pct ?? 0) >= 0 ? '+' : '' }}{{ (data.industry_change_pct ?? 0).toFixed(2) }}%
          </span>
        </div>
      </template>

      <template v-if="data.concepts && data.concepts.length">
        <div class="flex flex-wrap gap-1 mt-2">
          <span v-for="c in data.concepts" :key="c.name"
                class="px-1.5 py-0.5 text-[10px] rounded border"
                :class="(c.change_pct ?? 0) >= 0
                  ? 'border-red-500/30 text-red-400 bg-red-500/10'
                  : 'border-green-500/30 text-green-400 bg-green-500/10'">
            {{ c.name }}
            <span class="ml-0.5">{{ (c.change_pct ?? 0) >= 0 ? '+' : '' }}{{ (c.change_pct ?? 0).toFixed(2) }}%</span>
          </span>
        </div>
      </template>

      <div v-if="isIndex" class="text-[11px] text-gray-500 text-center py-2">
        指数暂无板块归属
      </div>
      <div v-else-if="!data.industry && (!data.concepts || !data.concepts.length)"
           class="text-[11px] text-gray-500 text-center py-2">
        暂无板块数据
      </div>
    </div>

    <!-- ═══ 数据时间戳 ═══════════════════════════════════════════════ -->
    <div class="px-3 py-2 mt-auto">
      <div class="text-[9px] text-gray-600 text-center">
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
  // 实时快照数据（来自API）
  realtimeData: { type: Object,  default: () => ({}) },
  // 十字光标历史快照（来自图表hover）
  snapshotData: { type: Object,  default: null },   // null=使用realtimeData
  isMobile:     { type: Boolean, default: false },
  panelWidth:   { type: Number,  default: 300 },
})

const data = computed(() => props.snapshotData || props.realtimeData)
const isCrosshair = computed(() => !!props.snapshotData)

// ── 颜色 ──────────────────────────────────────────────────────
const priceColor = computed(() => {
  const c = data.value.change_pct
  if (c == null) return '#9ca3af'
  return c >= 0 ? '#ef232a' : '#14b143'
})
const priceColorClass = computed(() => {
  const c = data.value.change_pct
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

// ── 基础字段 ────────────────────────────────────────────────────
const basicFields = [
  { key: 'open',   label: '开盘',  formatter: v => v != null ? v.toFixed(3) : '--' },
  { key: 'high',   label: '最高',  formatter: v => v != null ? v.toFixed(3) : '--' },
  { key: 'low',    label: '最低',  formatter: v => v != null ? v.toFixed(3) : '--' },
  { key: 'close',  label: '昨收',  formatter: v => v != null ? v.toFixed(3) : '--' },
  { key: 'volume', label: '成交量', formatter: v => v != null ? formatVol(v) : '--' },
  { key: 'amount', label: '成交额', formatter: v => v != null ? formatAmount(v) : '--' },
  { key: 'turnover_rate', label: '换手率', formatter: v => v != null ? v.toFixed(2) + '%' : '--' },
  { key: 'amplitude',     label: '振幅',   formatter: v => v != null ? v.toFixed(2) + '%' : '--' },
]

// ── 估值字段 ───────────────────────────────────────────────────
const valuationFields = [
  { key: 'pe_ttm', label: '市盈率TTM', formatter: v => v != null ? v.toFixed(2) : '--' },
  { key: 'pb',     label: '市净率',   formatter: v => v != null ? v.toFixed(2) : '--' },
]

// ── 周期收益字段 ───────────────────────────────────────────────
const returnFields = [
  { key: 'returns_5d',  label: '5日' },
  { key: 'returns_20d', label: '20日' },
  { key: 'returns_60d', label: '60日' },
]

function returnColorClass(v) {
  if (v == null) return 'text-gray-400'
  return v >= 0 ? 'text-red-400' : 'text-green-400'
}

// ── 资金流向各级 ────────────────────────────────────────────────
const fundLevels = computed(() => {
  const d = data.value
  const makeLevel = (keyIn, keyOut, label, color) => ({
    key: keyIn,
    label,
    color,
    value: d[keyIn] ?? 0,
    width: 50,   // 暂无真实数据，保持中性宽度
  })
  return [
    { key: 'fund_huge_in',   label: '超大', color: '#f87171', value: data.value.fund_huge_in ?? 0,
      width: 50 },
    { key: 'fund_big_in',    label: '大单', color: '#fb923c', value: data.value.fund_big_in ?? 0,
      width: 50 },
    { key: 'fund_medium_in', label: '中单', color: '#fbbf24', value: data.value.fund_medium_in ?? 0,
      width: 50 },
    { key: 'fund_small_in',  label: '小单', color: '#6ee7b7', value: data.value.fund_small_in ?? 0,
      width: 50 },
  ].filter(l => l.value != null)
})

// ── 格式化 ─────────────────────────────────────────────────────
function formatVol(v) {
  if (v == null) return '--'
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(2) + '万'
  return v.toFixed(0)
}
function formatAmount(v) {
  if (v == null) return '--'
  if (Math.abs(v) >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(2) + '万'
  return (v >= 0 ? '+' : '') + v.toFixed(0)
}

// ── 资金环形图（ECharts）───────────────────────────────────────
const fundDonutRef = ref(null)
let donutInstance = null

function renderDonut() {
  if (!fundDonutRef.value || !window.echarts) return
  const d = data.value
  if (d.fund_main_net == null) return

  if (!donutInstance) {
    donutInstance = window.echarts.init(fundDonutRef.value, null, { renderer: 'canvas' })
  }

  const net   = Math.abs(d.fund_main_net || 0)
  const inAmt  = d.fund_main_in  || 0
  const outAmt = d.fund_main_out || 0
  const total  = inAmt + outAmt || 1

  donutInstance.setOption({
    backgroundColor: 'transparent',
    tooltip: { show: false },
    series: [{
      type: 'pie',
      radius: ['55%', '80%'],
      center: ['50%', '50%'],
      avoidLabelOverlap: false,
      label: { show: false },
      data: [
        { value: inAmt,  name: '流入', itemStyle: { color: '#ef232a' } },
        { value: outAmt, name: '流出', itemStyle: { color: '#14b143' } },
      ],
    }],
  })
}

watch(() => data.value.fund_main_net, () => { nextTick(renderDonut) }, { immediate: true })
onMounted(() => { nextTick(renderDonut) })
onUnmounted(() => { donutInstance?.dispose(); donutInstance = null })
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
  border-top: 1px solid rgba(55, 65, 81, 0.4);
}

/* 滚动条样式 */
.quote-panel::-webkit-scrollbar { width: 4px; }
.quote-panel::-webkit-scrollbar-track { background: transparent; }
.quote-panel::-webkit-scrollbar-thumb { background: #374151; border-radius: 2px; }
</style>
