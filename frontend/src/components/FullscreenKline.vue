<template>
  <div
    class="fullscreen-kline flex flex-col bg-[#0a0e17]"
    :class="{ 'fixed inset-0 z-[200]': isFull }"
    @keydown.esc="isFull && emit('close')"
    tabindex="0"
  >
    <!-- ══ 顶部控制栏 ══════════════════════════════════════════════ -->
    <div class="shrink-0 flex items-center gap-2 px-3 py-2 border-b border-gray-700/60 bg-[#0d1220]">

      <!-- 指数选择 -->
      <div class="flex items-center gap-1">
        <button
          v-for="idx in indexOptions" :key="idx.symbol"
          class="px-2 py-0.5 text-[11px] rounded border transition"
          :class="symbol === idx.symbol
            ? 'bg-terminal-accent/20 border-terminal-accent/50 text-terminal-accent'
            : 'border-gray-700 text-gray-500 hover:border-gray-500 hover:text-gray-300'"
          @click="switchSymbol(idx.symbol, idx.name)"
        >{{ idx.name }}</button>
      </div>

      <div class="w-px h-4 bg-gray-700/50"></div>

      <!-- 周期选择 -->
      <div class="flex items-center gap-1">
        <button
          v-for="p in periods" :key="p.key"
          class="px-2 py-0.5 text-[11px] rounded border transition"
          :class="period === p.key
            ? 'bg-blue-500/20 border-blue-500/50 text-blue-400'
            : 'border-gray-700 text-gray-500 hover:border-gray-500 hover:text-gray-300'"
          @click="period = p.key"
        >{{ p.label }}</button>
      </div>

      <div class="w-px h-4 bg-gray-700/50"></div>

      <!-- 指标选择 -->
      <div class="flex items-center gap-1">
        <button
          v-for="ind in allIndicators" :key="ind.key"
          class="px-1.5 py-0.5 text-[10px] rounded border transition"
          :class="activeIndicators.includes(ind.key)
            ? 'bg-purple-500/20 border-purple-500/50 text-purple-400'
            : 'border-gray-700 text-gray-600 hover:border-gray-500 hover:text-gray-400'"
          @click="toggleIndicator(ind.key)"
        >{{ ind.label }}</button>
      </div>

      <!-- 最新价格 -->
      <div class="ml-3 flex items-center gap-2">
        <span class="text-[13px] font-mono font-bold" :class="latestChange >= 0 ? 'text-red-400' : 'text-green-400'">
          {{ latestPrice != null ? latestPrice.toFixed(2) : '--' }}
        </span>
        <span class="text-[11px] font-mono" :class="latestChange >= 0 ? 'text-red-400' : 'text-green-400'">
          {{ latestChange >= 0 ? '+' : '' }}{{ latestChange?.toFixed(2) ?? '--' }}%
        </span>
      </div>

      <!-- 关闭按钮 -->
      <div class="ml-auto flex items-center gap-2">
        <button
          class="px-3 py-0.5 text-[11px] rounded border border-gray-600 text-gray-500 hover:border-red-500/50 hover:text-red-400 transition"
          @click="emit('close')"
        >✕ 关闭</button>
      </div>
    </div>

    <!-- ══ 主图表区域 ══════════════════════════════════════════════ -->
    <div class="flex-1 min-h-0 relative flex">
      <!-- 左侧画线工具栏 -->
      <DrawingToolbar
        v-if="isFull"
        class="shrink-0 z-20"
        :activeTool="drawTool"
        :activeColor="drawColor"
        :magnetMode="magnetMode"
        :visible="drawVisible"
        :locked="drawLocked"
        @tool-change="t => drawTool = t"
        @color-change="c => drawColor = c"
        @magnet-toggle="magnetMode = !magnetMode"
        @visibility-toggle="drawVisible = !drawVisible"
        @lock-toggle="drawLocked = !drawLocked"
        @clear="drawingCanvasRef?.clearAll()"
      />

      <!-- ECharts 图表 -->
      <div class="flex-1 min-w-0 relative">
        <!-- 加载遮罩 -->
        <div v-if="isLoading" class="absolute inset-0 z-10 flex items-end justify-center pb-6 pointer-events-none">
          <div class="flex gap-1 items-end opacity-50">
            <div v-for="i in 24" :key="i" class="w-1 bg-terminal-accent rounded-t animate-pulse"
                 :style="{ height: `${20 + ((i * 37) % 70)}%` }"></div>
          </div>
        </div>

        <!-- 错误提示 -->
        <div v-if="chartError" class="absolute inset-0 z-20 flex flex-col items-center justify-center bg-[#0a0e17]/90">
          <div class="text-3xl mb-2">📊</div>
          <div class="text-terminal-dim text-xs">{{ chartError }}</div>
          <button class="mt-2 px-3 py-1 text-[10px] rounded border border-gray-600 text-gray-400 hover:border-terminal-accent/40" @click="fetchData">重试</button>
        </div>

        <!-- ECharts 实例 -->
        <div ref="chartRef" class="w-full h-full"></div>

        <!-- 画线 Canvas 覆盖层 -->
        <DrawingCanvas
          v-if="isFull && drawVisible"
          ref="drawingCanvasRef"
          class="absolute inset-0 z-10"
          :chartInstance="chartInstance"
          :activeTool="drawTool"
          :activeColor="drawColor"
          :magnetMode="magnetMode"
          :symbol="symbol"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import DrawingToolbar from './DrawingToolbar.vue'
import DrawingCanvas  from './DrawingCanvas.vue'

// ── Props / Emit ───────────────────────────────────────────────
const props = defineProps({
  symbol: { type: String, default: '000001' },
  name:   { type: String, default: '上证指数' },
  isFull: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'symbol-change'])

// ── DOM / 实例 ────────────────────────────────────────────────
const chartRef = ref(null)
let   chartInstance = null
let   resizeObserver = null

// ── 状态 ──────────────────────────────────────────────────────
const period           = ref('daily')
const activeIndicators = ref([])
const isLoading        = ref(false)
const chartError       = ref('')
const latestPrice      = ref(null)
const latestChange     = ref(0)

// 画线状态
const drawTool    = ref('')
const drawColor   = ref('#fbbf24')
const magnetMode  = ref(true)
const drawVisible = ref(true)
const drawLocked  = ref(false)
const drawingCanvasRef = ref(null)

const allIndicators = [
  { key: 'MACD', label: 'MACD' },
  { key: 'BOLL', label: 'BOLL' },
  { key: 'KDJ',  label: 'KDJ' },
  { key: 'WR',   label: 'W&R' },
]
const indexOptions = [
  { symbol: '000001', name: '上证' },
  { symbol: '000300', name: '沪深300' },
  { symbol: '399001', name: '深证' },
  { symbol: '399006', name: '创业板' },
]
const periods = [
  { key: 'minutely', label: '分时' },
  { key: 'daily',    label: '日K' },
  { key: 'weekly',   label: '周K' },
  { key: 'monthly',  label: '月K' },
]

// ── 配色 ──────────────────────────────────────────────────────
const UP   = '#ef232a'
const DOWN = '#14b143'

// ── 数据 ──────────────────────────────────────────────────────
function _sanitize(raw) {
  if (!Array.isArray(raw)) return []
  return raw.map(r => ({
    date:       r.date   || String(r.timestamp || ''),
    time:       r.time  || '',
    open:       Number(r.open)  || 0,
    close:      Number(r.close) || 0,
    high:       Number(r.high)  || 0,
    low:        Number(r.low)   || 0,
    volume:     Number(r.volume) || 0,
    price:      Number(r.price != null ? r.price : r.close) || 0,
    change_pct: Number(r.change_pct) || 0,
  }))
}

async function fetchData() {
  isLoading.value = true
  chartError.value = ''
  try {
    const url  = `/api/v1/market/history/${props.symbol}?period=${period.value}`
    const res  = await fetch(url + `&_t=${Date.now()}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    const type = data.chart_type || 'candlestick'
    const hist  = _sanitize(data.history || [])

    if (!hist.length) { chartError.value = '暂无历史数据'; return }

    const last = hist[hist.length - 1]
    latestPrice.value  = last.price  ?? last.close
    latestChange.value = last.change_pct ?? 0

    const isDesc = hist.length >= 2 && new Date(hist[0].date) > new Date(hist[hist.length - 1].date)
    const sorted = isDesc ? [...hist].reverse() : hist
    renderChart(sorted, type)
  } catch (e) {
    chartError.value = `加载失败: ${e.message}`
  } finally {
    isLoading.value = false
  }
}

// ── K线图 ─────────────────────────────────────────────────────
function buildKLineOpt(hist) {
  const times   = hist.map(h => h.time && h.time.length >= 16 ? h.time.slice(0,16) : (h.date||'').slice(0,10))
  const closes  = hist.map(h => h.close)
  const highs   = hist.map(h => h.high)
  const lows    = hist.map(h => h.low)

  const yMin = +(Math.min(...closes) * 0.997).toFixed(2)
  const yMax = +(Math.max(...closes) * 1.003).toFixed(2)
  const sub   = activeIndicators.value[0] || null

  const mainH = 60, volH = 20
  const mainTop = 2, volTop = mainTop + mainH + 1
  const subTop  = sub ? volTop + volH + 1 : 0
  const subH    = sub ? 17 : 0

  const grid = [
    { top: `${mainTop}%`, height: `${mainH}%`,  right: 8, left: 60, bottom: 0 },
    { top: `${volTop}%`,  height: `${volH}%`,   right: 8, left: 60, bottom: 0 },
  ]
  if (sub) grid.push({ top: `${subTop}%`, height: `${subH}%`, right: 8, left: 60, bottom: 0 })

  const series = [
    { name: 'K线', type: 'candlestick',
      data: hist.map(h => [h.open, h.close, h.low, h.high]),
      xAxisIndex: 0, yAxisIndex: 0,
      itemStyle: { color: UP, color0: DOWN, borderColor: UP, borderColor0: DOWN } },
    ...buildMASeries(closes, 0, 0),
    ...(activeIndicators.value.includes('BOLL') ? buildBOLLSeries(closes, 0, 0) : []),
    { name: '成交量', type: 'bar',
      data: hist.map(h => ({ value: h.volume, itemStyle: { color: h.close >= h.open ? UP+'33' : DOWN+'33' } })),
      xAxisIndex: 1, yAxisIndex: 1, barMaxWidth: 6 },
    ...(sub ? buildSubSeries(closes, highs, lows, sub, 2, 2) : []),
  ]

  const xAxisBase = { type: 'category', data: times, boundaryGap: true,
    axisLine: { lineStyle: { color: '#2d3748' } }, splitLine: { show: false } }
  const xAxis = [
    { ...xAxisBase, gridIndex: 0, axisLabel: { color: '#6b7280', fontSize: 9,
      interval: Math.max(0, Math.floor(times.length/6)-1) } },
    { ...xAxisBase, gridIndex: 1, axisLabel: { show: false } },
    ...(sub ? [{ ...xAxisBase, gridIndex: 2, axisLabel: { show: false } }] : []),
  ]

  const yAxis = [
    { type: 'value', scale: true, gridIndex: 0, position: 'left',
      min: yMin, max: yMax,
      axisLine: { show: false },
      axisLabel: { color: '#6b7280', fontSize: 9, formatter: v => v.toFixed(0) },
      splitLine: { lineStyle: { color: '#1f2937', type: 'dashed' } } },
    { type: 'value', scale: true, gridIndex: 1, position: 'left',
      axisLine: { show: false }, axisLabel: { show: false }, splitLine: { show: false } },
  ]
  if (sub) yAxis.push({ type: 'value', scale: true, gridIndex: 2, position: 'left',
    axisLine: { show: false },
    axisLabel: { color: '#6b7280', fontSize: 9 },
    splitLine: { lineStyle: { color: '#1f2937', type: 'dashed' } },
    max: sub === 'WR' ? 0 : 'auto', min: sub === 'WR' ? -100 : 'auto' })

  return {
    backgroundColor: 'transparent', grid, xAxis, yAxis, series,
    tooltip: { trigger: 'axis', type: 'cross',
      axisPointer: { type: 'cross', lineStyle: { color: '#9ca3af', width: 1, type: 'dashed' }, crossStyle: { color: '#9ca3af', width: 1 } },
      backgroundColor: 'rgba(26,30,46,0.96)', borderColor: '#4b5563',
      textStyle: { color: '#9ca3af', fontSize: 11 },
      formatter(params) {
        const kp = params.find(p => p.seriesName === 'K线')
        if (!kp) return ''
        const idx = kp.dataIndex, h = hist[idx]
        if (!h) return ''
        const o=h.open, c=h.close, l=h.low, hi=h.high
        const chg = h.change_pct, col = c>=o ? UP : DOWN
        return `<span style="color:#6b7280;font-size:10px">${kp.axisValue}</span><br/>`
          + `<span style="color:#9ca3af;font-size:10px">开</span> <span style="color:#e5e7eb;font-size:11px">${o.toFixed(2)}</span><br/>`
          + `<span style="color:#9ca3af;font-size:10px">高</span> <span style="color:#e5e7eb;font-size:11px">${hi.toFixed(2)}</span><br/>`
          + `<span style="color:#9ca3af;font-size:10px">低</span> <span style="color:#e5e7eb;font-size:11px">${l.toFixed(2)}</span><br/>`
          + `<span style="color:#9ca3af;font-size:10px">收</span> <span style="color:${col};font-size:11px">${c.toFixed(2)}</span> <span style="color:${chg>=0?UP:DOWN};font-size:10px">${chg>=0?'+':''}${chg.toFixed(2)}%</span><br/>`
          + `<span style="color:#9ca3af;font-size:10px">量</span> <span style="color:#9ca3af;font-size:11px">${(h.volume/1e8).toFixed(2)}亿</span>`
      } },
    dataZoom: [
      { type: 'inside', xAxisIndex: [...Array(xAxis.length).keys()], start: 80, end: 100 },
      { type: 'slider', xAxisIndex: [0], start: 90, end: 100, height: 12, bottom: 2,
        borderColor: '#2d3748', fillerColor: 'rgba(59,130,246,0.10)',
        handleStyle: { color: '#60a5fa' },
        textStyle: { color: '#6b7280', fontSize: 9 },
        dataBackground: { lineStyle: { color: '#374151' }, areaStyle: { color: 'rgba(59,130,246,0.06)' } } },
    ],
  }
}

// ── 分时图 ─────────────────────────────────────────────────────
function buildLineOpt(hist) {
  const times  = hist.map(h => h.time && h.time.length >= 16 ? h.time.slice(0,16) : (h.date||'').slice(0,10))
  const prices = hist.map(h => Number(h.price != null ? h.price : h.close))
  const vols   = hist.map(h => Number(h.volume))

  const rawMin = Math.min(...prices), rawMax = Math.max(...prices)
  const pad    = (rawMax - rawMin) * 0.01
  const yMin = +(rawMin - pad).toFixed(2), yMax = +(rawMax + pad).toFixed(2)

  const upCount = prices.filter((p,i) => i>0 && p>prices[i-1]).length
  const lineColor = upCount >= prices.length/2 ? UP : DOWN

  const mainH = 75, volH = 22, mainTop = 2, volTop = mainTop + mainH + 1

  let sum = 0
  const avg = prices.map((p, i) => { sum += p; return +(sum/(i+1)).toFixed(3) })

  return {
    backgroundColor: 'transparent',
    grid: [
      { top: `${mainTop}%`, height: `${mainH}%`, right: 8, left: 60, bottom: 0 },
      { top: `${volTop}%`,  height: `${volH}%`,  right: 8, left: 60, bottom: 0 },
    ],
    xAxis: [
      { type: 'category', data: times, boundaryGap: false, gridIndex: 0,
        axisLine: { lineStyle: { color: '#2d3748' } },
        axisLabel: { color: '#6b7280', fontSize: 9, interval: Math.max(0, Math.floor(times.length/6)-1) },
        splitLine: { show: false } },
      { type: 'category', data: times, boundaryGap: false, gridIndex: 1,
        axisLine: { lineStyle: { color: '#2d3748' } },
        axisLabel: { show: false }, splitLine: { show: false } },
    ],
    yAxis: [
      { type: 'value', scale: true, gridIndex: 0, position: 'left', min: yMin, max: yMax,
        axisLine: { show: false },
        axisLabel: { color: '#6b7280', fontSize: 9, formatter: v => v.toFixed(2) },
        splitLine: { lineStyle: { color: '#1f2937', type: 'dashed' } } },
      { type: 'value', scale: true, gridIndex: 1, position: 'left',
        axisLine: { show: false }, axisLabel: { show: false }, splitLine: { show: false } },
    ],
    series: [
      { name: '价格', type: 'line', data: prices, smooth: 0.3, symbol: 'none',
        lineStyle: { color: lineColor, width: 1.5 },
        areaStyle: { color: { type: 'linear', x:0,y:0,x2:0,y2:1,
          colorStops: [{ offset:0, color: lineColor+'28' }, { offset:1, color: lineColor+'00' }] } } },
      { name: '均价', type: 'line', data: avg, smooth: 0.3, symbol: 'none',
        lineStyle: { color: '#fbbf24', width: 1, type: 'dashed' } },
      { name: '成交量', type: 'bar',
        data: vols.map(v => ({ value: v, itemStyle: { color: lineColor+'33' } })),
        xAxisIndex: 1, yAxisIndex: 1, barMaxWidth: 4 },
    ],
    tooltip: { trigger: 'axis', type: 'cross',
      axisPointer: { lineStyle: { color: '#374151' } },
      backgroundColor: '#1a1e2e', borderColor: '#374151', textStyle: { color: '#9ca3af', fontSize: 11 },
      formatter: (params) => {
        const p = params[0]; if (!p) return ''
        const idx = p.dataIndex
        return `<span style="color:#6b7280;font-size:10px">${p.axisValue}</span><br/>`
          + `<span style="color:#9ca3af;font-size:10px">价</span> <span style="color:${lineColor};font-size:11px">${(prices[idx]||0).toFixed(3)}</span><br/>`
          + `<span style="color:#9ca3af;font-size:10px">均</span> <span style="color:#fbbf24;font-size:11px">${avg[idx]?.toFixed(3)}</span><br/>`
          + `<span style="color:#6b7280;font-size:10px">量</span> <span style="color:#9ca3af;font-size:11px">${(vols[idx]/1e8).toFixed(2)}亿</span>`
      } },
    dataZoom: [
      { type: 'inside', xAxisIndex: [0,1], start: 80, end: 100 },
      { type: 'slider', xAxisIndex: [0], start: 90, end: 100, height: 12, bottom: 2,
        borderColor: '#2d3748', fillerColor: 'rgba(59,130,246,0.10)',
        handleStyle: { color: '#60a5fa' },
        textStyle: { color: '#6b7280', fontSize: 9 },
        dataBackground: { lineStyle: { color: '#374151' }, areaStyle: { color: 'rgba(59,130,246,0.06)' } } },
    ],
  }
}

// ── 指标计算 ───────────────────────────────────────────────────
function calcMA(data, n) {
  return data.map((_, i) => {
    if (i < n-1) return null
    return +(data.slice(i-n+1, i+1).reduce((a,b) => a+b, 0)/n).toFixed(3)
  })
}
function calcEMA(data, n) {
  const k = 2/(n+1); const r = []; let e = data[0]
  for (let i=0; i<data.length; i++) { e = i===0 ? data[0] : data[i]*k + e*(1-k); r.push(+e.toFixed(4)) }
  return r
}
function calcBOLL(closes) {
  const P=20, mid=[], upper=[], lower=[]
  for (let i=0; i<closes.length; i++) {
    if (i<P-1) { mid.push('-'); upper.push('-'); lower.push('-'); continue }
    const s=closes.slice(i-P+1,i+1), m=s.reduce((a,b)=>a+b,0)/P
    const std=Math.sqrt(s.reduce((a,b)=>a+(b-m)**2,0)/P)
    mid.push(+m.toFixed(3)); upper.push(+(m+2*std).toFixed(3)); lower.push(+(m-2*std).toFixed(3))
  }
  return { mid, upper, lower }
}
function calcMACD(closes) {
  const e12=calcEMA(closes,12), e26=calcEMA(closes,26)
  const dif=e12.map((v,i)=>+(v-e26[i]).toFixed(4))
  const dea=calcEMA(dif,9)
  return { dif, dea, macd: dif.map((v,i)=>+((v-dea[i])*2).toFixed(4)) }
}
function calcKDJ(closes, highs, lows, n=9) {
  const k=[], d=[], j=[]
  for (let i=0; i<closes.length; i++) {
    if (i<n-1) { k.push('-'); d.push('-'); j.push('-'); continue }
    const rh=Math.max(...highs.slice(i-n+1,i+1)), rl=Math.min(...lows.slice(i-n+1,i+1))
    const rsv=rh===rl?50:(closes[i]-rl)/(rh-rl)*100
    const pk=k[i-1]!=='-'?k[i-1]:50, pd=d[i-1]!=='-'?d[i-1]:50
    k.push(+(2/3*pk+1/3*rsv).toFixed(2)); d.push(+(2/3*pd+1/3*k[i]).toFixed(2)); j.push(+(3*k[i]-2*d[i]).toFixed(2))
  }
  return { k, d, j }
}
function calcWR(closes, highs, lows, n=10) {
  return closes.map((_, i) => {
    if (i < n-1) return null
    const rh=Math.max(...highs.slice(i-n+1,i+1)), rl=Math.min(...lows.slice(i-n+1,i+1))
    if (rh===rl) return 0
    return +((rh-closes[i])/(rh-rl)*-100).toFixed(2)
  })
}

function buildMASeries(closes, xIdx, yIdx) {
  return [
    { name:'MA5',  type:'line', data:calcMA(closes,5),  xAxisIndex:xIdx, yAxisIndex:yIdx, smooth:true, symbol:'none',
      lineStyle:{ color:'#ffffff',width:1 }, tooltip:{ show:true } },
    { name:'MA10', type:'line', data:calcMA(closes,10), xAxisIndex:xIdx, yAxisIndex:yIdx, smooth:true, symbol:'none',
      lineStyle:{ color:'#fbbf24',width:1 }, tooltip:{ show:true } },
    { name:'MA20', type:'line', data:calcMA(closes,20), xAxisIndex:xIdx, yAxisIndex:yIdx, smooth:true, symbol:'none',
      lineStyle:{ color:'#c084fc',width:1 }, tooltip:{ show:true } },
  ]
}
function buildBOLLSeries(closes, xIdx, yIdx) {
  const { mid, upper, lower } = calcBOLL(closes)
  return [
    { name:'BOLL-M', type:'line', data:mid,  xAxisIndex:xIdx, yAxisIndex:yIdx, smooth:true, symbol:'none', lineStyle:{ color:'#a78bfa',width:1.2 } },
    { name:'BOLL-U', type:'line', data:upper, xAxisIndex:xIdx, yAxisIndex:yIdx, smooth:true, symbol:'none', lineStyle:{ color:'#a78bfa',width:1,type:'dashed' } },
    { name:'BOLL-L', type:'line', data:lower, xAxisIndex:xIdx, yAxisIndex:yIdx, smooth:true, symbol:'none', lineStyle:{ color:'#a78bfa',width:1,type:'dashed' } },
  ]
}
function buildSubSeries(closes, highs, lows, sub, xIdx, yIdx) {
  if (sub==='MACD') {
    const { dif, dea, macd } = calcMACD(closes)
    return [
      { name:'DIF', type:'line', data:dif,  xAxisIndex:xIdx, yAxisIndex:yIdx, smooth:true, symbol:'none', lineStyle:{ color:'#60a5fa',width:1.2 } },
      { name:'DEA', type:'line', data:dea,  xAxisIndex:xIdx, yAxisIndex:yIdx, smooth:true, symbol:'none', lineStyle:{ color:'#f87171',width:1.2 } },
      { name:'MACD', type:'bar',
        data: macd.map(v => ({ value:Math.abs(v), itemStyle:{ color:v>=0?UP:DOWN } })),
        xAxisIndex:xIdx, yAxisIndex:yIdx, barMaxWidth:4 },
    ]
  }
  if (sub==='KDJ') {
    const { k, d, j } = calcKDJ(closes, highs, lows)
    return [
      { name:'K', type:'line', data:k, xAxisIndex:xIdx, yAxisIndex:yIdx, smooth:true, symbol:'none', lineStyle:{ color:'#f87171',width:1.2 } },
      { name:'D', type:'line', data:d, xAxisIndex:xIdx, yAxisIndex:yIdx, smooth:true, symbol:'none', lineStyle:{ color:'#60a5fa',width:1.2 } },
      { name:'J', type:'line', data:j, xAxisIndex:xIdx, yAxisIndex:yIdx, smooth:true, symbol:'none', lineStyle:{ color:'#fbbf24',width:1.2 } },
    ]
  }
  if (sub==='WR') {
    const wr = calcWR(closes, highs, lows)
    return [{ name:'W&R', type:'line', data:wr.map(v=>v==null?'-':v), xAxisIndex:xIdx, yAxisIndex:yIdx, smooth:true, symbol:'none',
      lineStyle:{ color:'#fb923c',width:1.2 },
      markLine:{ silent:true, symbol:'none', lineStyle:{ color:'#4b5563',type:'dashed',width:1 },
        data:[{ yAxis:-20 },{ yAxis:-80 }],
        label:{ show:true, formatter:'{c}', fontSize:8, color:'#6b7280' } } }]
  }
  return []
}

// ── 渲染 ───────────────────────────────────────────────────────
function renderChart(hist, type) {
  if (!chartInstance) return
  const opt = type === 'line' ? buildLineOpt(hist) : buildKLineOpt(hist)
  chartInstance.clear()
  chartInstance.setOption(opt, { notMerge: true })
}

function initChart() {
  if (!chartRef.value || !window.echarts) return
  chartInstance = window.echarts.init(chartRef.value, null, { renderer: 'canvas' })
  resizeObserver = new ResizeObserver(() => chartInstance?.resize())
  resizeObserver.observe(chartRef.value)
  fetchData()
}

// ── 切换操作 ───────────────────────────────────────────────────
function switchSymbol(sym, name) {
  emit('symbol-change', { symbol: sym, name })
}
function toggleIndicator(key) {
  const idx = activeIndicators.value.indexOf(key)
  if (idx >= 0) activeIndicators.value.splice(idx, 1)
  else {
    if (activeIndicators.value.length >= 1) activeIndicators.value.splice(0, 1, key)
    else activeIndicators.value.push(key)
  }
}

// ── 监听 ───────────────────────────────────────────────────────
watch(() => props.symbol, fetchData)
watch(() => period,      fetchData)
watch(activeIndicators, () => {
  if (!chartInstance) return
  // 重新渲染以应用新指标（数据已加载，只需重新构建option）
  // 触发一次 fetchData 获取 hist 然后重新 render
  fetchData()
}, { deep: true })

// ── 生命周期 ──────────────────────────────────────────────────
onMounted(() => { initChart() })
onUnmounted(() => {
  resizeObserver?.disconnect()
  chartInstance?.dispose()
  chartInstance = null
})
</script>
