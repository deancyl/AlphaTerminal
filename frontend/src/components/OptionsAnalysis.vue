<template>
  <div class="h-full flex flex-col bg-terminal-bg overflow-hidden">
    <!-- 顶部标题栏 -->
    <div class="flex items-center justify-between px-4 py-2 border-b border-theme-secondary shrink-0">
      <div class="flex items-center gap-3">
        <span class="text-lg font-bold text-terminal-accent">⚡ 期权分析</span>
        <span class="text-xs text-terminal-dim cursor-help" title="Black-Scholes模型：1973年由Fischer Black和Myron Scholes提出的期权定价模型，是现代金融理论的基石之一。该模型假设股票价格服从对数正态分布，通过五个参数（标的资产价格、行权价、到期时间、波动率、无风险利率）计算欧式期权的理论价格">Black-Scholes 希腊值计算</span>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto p-4 space-y-4">
      <!-- 输入参数 -->
      <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <div class="space-y-1">
          <label class="text-xs text-terminal-dim">标的资产价格 S</label>
          <input
            v-model.number="params.S"
            type="number"
            class="w-full min-h-[44px] bg-terminal-panel border border-theme-secondary rounded-sm px-3 py-2 text-sm text-terminal-primary"
            placeholder="100.00"
          />
        </div>
        
        <div class="space-y-1">
          <label class="text-xs text-terminal-dim">行权价 K</label>
          <input
            v-model.number="params.K"
            type="number"
            class="w-full min-h-[44px] bg-terminal-panel border border-theme-secondary rounded-sm px-3 py-2 text-sm text-terminal-primary"
            placeholder="100.00"
          />
        </div>
        
        <div class="space-y-1">
          <label class="text-xs text-terminal-dim">到期时间 T(年)</label>
          <input
            v-model.number="params.T"
            type="number"
            step="0.01"
            class="w-full min-h-[44px] bg-terminal-panel border border-theme-secondary rounded-sm px-3 py-2 text-sm text-terminal-primary"
            placeholder="0.25"
          />
        </div>
        
        <div class="space-y-1">
          <label class="text-xs text-terminal-dim">波动率 σ(%)</label>
          <input
            v-model.number="params.sigma"
            type="number"
            step="0.1"
            class="w-full min-h-[44px] bg-terminal-panel border border-theme-secondary rounded-sm px-3 py-2 text-sm text-terminal-primary"
            placeholder="20.0"
          />
        </div>
        
        <div class="space-y-1">
          <label class="text-xs text-terminal-dim">无风险利率 r(%)</label>
          <input
            v-model.number="params.r"
            type="number"
            step="0.1"
            class="w-full min-h-[44px] bg-terminal-panel border border-theme-secondary rounded-sm px-3 py-2 text-sm text-terminal-primary"
            placeholder="3.0"
          />
        </div>
        
        <div class="space-y-1">
          <label class="text-xs text-terminal-dim">股息率 q(%)</label>
          <input
            v-model.number="params.q"
            type="number"
            step="0.1"
            class="w-full min-h-[44px] bg-terminal-panel border border-theme-secondary rounded-sm px-3 py-2 text-sm text-terminal-primary"
            placeholder="0.0"
          />
        </div>
      </div>

      <!-- 计算结果 -->
      <div v-if="results" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        <!-- 期权价格 -->
        <div class="rounded-sm border border-theme bg-terminal-panel/60 p-3">
          <div class="text-[10px] text-theme-muted mb-1">看涨期权价格</div>
          <div class="text-xl font-mono font-bold text-bullish">{{ results.callPrice.toFixed(4) }}</div>
          <div class="text-[10px] text-theme-muted mt-1">看跌期权价格</div>
          <div class="text-xl font-mono font-bold text-bearish">{{ results.putPrice.toFixed(4) }}</div>
        </div>

        <!-- Delta -->
        <div class="rounded-sm border border-theme bg-terminal-panel/60 p-3">
          <div class="text-[10px] text-theme-muted mb-1 cursor-help" title="Delta (Δ)：期权价格对标的资产价格的敏感度。看涨期权Delta范围0-1，看跌期权Delta范围-1到0。Delta=0.5表示标的资产每变动1元，期权价格变动0.5元">Delta (Δ)</div>
          <div class="text-lg font-mono font-bold">{{ results.callDelta.toFixed(4) }}</div>
          <div class="text-[10px] text-theme-muted">看涨 | 看跌: {{ results.putDelta.toFixed(4) }}</div>
          <div class="text-[10px] text-terminal-dim mt-1">价格对标的敏感度</div>
        </div>

        <!-- Gamma -->
        <div class="rounded-sm border border-theme bg-terminal-panel/60 p-3">
          <div class="text-[10px] text-theme-muted mb-1 cursor-help" title="Gamma (Γ)：Delta对标的资产价格的二阶导数，衡量Delta的变化速度。Gamma越大，Delta变化越快，期权价格对标的资产价格变动越敏感。平值期权Gamma最大">Gamma (Γ)</div>
          <div class="text-lg font-mono font-bold text-terminal-accent">{{ results.gamma.toFixed(4) }}</div>
          <div class="text-[10px] text-terminal-dim mt-1">Delta对标的二阶敏感度</div>
        </div>

        <!-- Theta -->
        <div class="rounded-sm border border-theme bg-terminal-panel/60 p-3">
          <div class="text-[10px] text-theme-muted mb-1 cursor-help" title="Theta (Θ)：期权价格对时间流逝的敏感度，表示每过一天期权价值的损耗。通常为负值，因为随着到期日临近，期权时间价值逐渐减少。平值期权Theta绝对值最大">Theta (Θ)</div>
          <div class="text-lg font-mono font-bold">{{ results.callTheta.toFixed(4) }}</div>
          <div class="text-[10px] text-theme-muted">看涨 | 看跌: {{ results.putTheta.toFixed(4) }}</div>
          <div class="text-[10px] text-terminal-dim mt-1">时间衰减（每日）</div>
        </div>

        <!-- Vega -->
        <div class="rounded-sm border border-theme bg-terminal-panel/60 p-3">
          <div class="text-[10px] text-theme-muted mb-1 cursor-help" title="Vega (V)：期权价格对波动率的敏感度，表示波动率每变动1%，期权价格的变动量。Vega始终为正，因为波动率上升会增加期权价值。平值期权Vega最大">Vega (V)</div>
          <div class="text-lg font-mono font-bold text-[var(--color-warning)]">{{ results.vega.toFixed(4) }}</div>
          <div class="text-[10px] text-terminal-dim mt-1">对波动率的敏感度</div>
        </div>
      </div>

      <!-- 策略盈亏图 -->
      <div v-if="results" class="rounded-sm border border-theme bg-terminal-panel/40 p-3">
        <div class="text-[10px] text-theme-muted font-bold mb-2">📈 策略盈亏分析</div>
        <div class="flex flex-wrap gap-2 mb-3">
          <button
            v-for="s in strategies"
            :key="s.id"
            class="text-[10px] px-3 py-2 min-h-[44px] rounded-sm border transition"
            :class="activeStrategy === s.id
              ? 'bg-terminal-accent/20 border-terminal-accent/50 text-terminal-accent'
              : 'bg-terminal-bg border-theme-secondary text-theme-tertiary hover:text-theme-primary'"
            @click="activeStrategy = s.id"
          >
            {{ s.name }}
          </button>
        </div>
        <div ref="strategyChart" class="w-full h-[250px] sm:h-[300px]"></div>
      </div>

      <!-- 希腊值说明 -->
      <div class="rounded-sm border border-theme bg-terminal-panel/40 px-3 py-2 space-y-1">
        <div class="text-[10px] text-theme-muted font-bold mb-1">📊 希腊值说明</div>
        <div class="text-[10px] text-theme-muted leading-relaxed">
          <span class="text-theme-primary">Delta</span>: 标的价格变动1元，期权价格变动Δ元 |
          <span class="text-theme-primary">Gamma</span>: 标的价格变动1元，Delta变动Γ |
          <span class="text-theme-primary">Theta</span>: 每过1天，期权价格衰减Θ |
          <span class="text-theme-primary">Vega</span>: 波动率变动1%，期权价格变动V
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'

// ── Black-Scholes 参数 ──
const params = ref({
  S: 100,      // 标的资产价格
  K: 100,      // 行权价
  T: 0.25,     // 到期时间（年）
  sigma: 20,   // 波动率（%）
  r: 3,        // 无风险利率（%）
  q: 0,        // 股息率（%）
})

// ── 策略列表 ──
const strategies = [
  { id: 'long_call', name: '买入看涨' },
  { id: 'long_put', name: '买入看跌' },
  { id: 'covered_call', name: '备兑看涨' },
  { id: 'protective_put', name: '保护性看跌' },
  { id: 'straddle', name: '跨式组合' },
  { id: 'strangle', name: '勒式组合' },
]

const activeStrategy = ref('long_call')

const strategyChart = ref(null)
let chart = null

// ── Black-Scholes 计算 ──
const results = computed(() => {
  const { S, K, T, sigma, r, q } = params.value
  
  if (S <= 0 || K <= 0 || T <= 0 || sigma <= 0) return null
  
  const sigmaDecimal = sigma / 100
  const rDecimal = r / 100
  const qDecimal = q / 100
  
  const d1 = (Math.log(S / K) + (rDecimal - qDecimal + 0.5 * sigmaDecimal ** 2) * T) / (sigmaDecimal * Math.sqrt(T))
  const d2 = d1 - sigmaDecimal * Math.sqrt(T)
  
  // 标准正态分布 CDF
  function cdf(x) {
    return 0.5 * (1 + erf(x / Math.sqrt(2)))
  }
  
  // 误差函数
  function erf(x) {
    const a1 =  0.254829592
    const a2 = -0.284496736
    const a3 =  1.421413741
    const a4 = -1.453152027
    const a5 =  1.061405429
    const p  =  0.3275911
    
    const sign = x >= 0 ? 1 : -1
    x = Math.abs(x)
    
    const t = 1.0 / (1.0 + p * x)
    const y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x)
    
    return sign * y
  }
  
  // 标准正态分布 PDF
  function pdf(x) {
    return Math.exp(-0.5 * x * x) / Math.sqrt(2 * Math.PI)
  }
  
  const Nd1 = cdf(d1)
  const Nd2 = cdf(d2)
  const NNegD1 = cdf(-d1)
  const NNegD2 = cdf(-d2)
  
  const callPrice = S * Math.exp(-qDecimal * T) * Nd1 - K * Math.exp(-rDecimal * T) * Nd2
  const putPrice = K * Math.exp(-rDecimal * T) * NNegD2 - S * Math.exp(-qDecimal * T) * NNegD1
  
  const callDelta = Math.exp(-qDecimal * T) * Nd1
  const putDelta = Math.exp(-qDecimal * T) * (Nd1 - 1)
  
  const gamma = Math.exp(-qDecimal * T) * pdf(d1) / (S * sigmaDecimal * Math.sqrt(T))
  
  const callTheta = (-S * Math.exp(-qDecimal * T) * pdf(d1) * sigmaDecimal / (2 * Math.sqrt(T))
    - rDecimal * K * Math.exp(-rDecimal * T) * Nd2
    + qDecimal * S * Math.exp(-qDecimal * T) * Nd1) / 365
  
  const putTheta = (-S * Math.exp(-qDecimal * T) * pdf(d1) * sigmaDecimal / (2 * Math.sqrt(T))
    + rDecimal * K * Math.exp(-rDecimal * T) * NNegD2
    - qDecimal * S * Math.exp(-qDecimal * T) * NNegD1) / 365
  
  const vega = S * Math.exp(-qDecimal * T) * pdf(d1) * Math.sqrt(T) / 100
  
  return {
    callPrice,
    putPrice,
    callDelta,
    putDelta,
    gamma,
    callTheta,
    putTheta,
    vega,
    d1,
    d2,
  }
})

// ── 策略盈亏计算 ──
function calculateStrategyPnl(spotPrices) {
  if (!results.value) return []
  
  const { callPrice, putPrice } = results.value
  const { S, K } = params.value
  
  return spotPrices.map(spot => {
    let pnl = 0
    
    switch (activeStrategy.value) {
      case 'long_call':
        pnl = Math.max(spot - K, 0) - callPrice
        break
      case 'long_put':
        pnl = Math.max(K - spot, 0) - putPrice
        break
      case 'covered_call':
        pnl = (spot - S) + (Math.min(K - spot, 0) + callPrice)
        break
      case 'protective_put':
        pnl = (spot - S) + (Math.max(K - spot, 0) - putPrice)
        break
      case 'straddle':
        pnl = Math.max(spot - K, 0) + Math.max(K - spot, 0) - callPrice - putPrice
        break
      case 'strangle': {
        const lowerK = K * 0.95
        const upperK = K * 1.05
        // 简化：使用相同的期权价格
        pnl = Math.max(spot - upperK, 0) + Math.max(lowerK - spot, 0) - callPrice - putPrice
        break
      }
    }
    
    return { spot, pnl }
  })
}

// ── 渲染策略盈亏图 ──
function renderStrategyChart() {
  if (!strategyChart.value || !results.value) return
  
  if (chart) { chart.dispose(); chart = null }
  
  const { S, K } = params.value
  const minSpot = Math.max(K * 0.7, 1)
  const maxSpot = K * 1.3
  const step = (maxSpot - minSpot) / 50
  
  const spotPrices = []
  for (let s = minSpot; s <= maxSpot; s += step) {
    spotPrices.push(s)
  }
  
  const pnlData = calculateStrategyPnl(spotPrices)
  
  const chartTextColor = getComputedStyle(document.documentElement).getPropertyValue('--chart-text').trim() || '#8B949E'
  const upColor = getComputedStyle(document.documentElement).getPropertyValue('--color-up').trim() || '#FF6B6B'
  const downColor = getComputedStyle(document.documentElement).getPropertyValue('--color-down').trim() || '#51CF66'
  
  chart = window.echarts.init(strategyChart.value, 'dark')
  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      formatter: (items) => {
        const item = items[0]
        return `标的价: ${item.axisValue}<br/>盈亏: ${item.value >= 0 ? '+' : ''}${item.value.toFixed(2)}`
      }
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      data: spotPrices.map(s => s.toFixed(1)),
      axisLabel: { color: chartTextColor, fontSize: 9 }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: chartTextColor, fontSize: 10 }
    },
    series: [{
      type: 'line',
      data: pnlData.map(d => d.pnl.toFixed(2)),
      smooth: true,
      lineStyle: { color: upColor, width: 2 },
      itemStyle: { color: upColor },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: upColor + '4D' },
            { offset: 0.5, color: upColor + '0D' },
            { offset: 1, color: downColor + '4D' }
          ]
        }
      },
      markLine: {
        data: [
          { yAxis: 0, lineStyle: { color: '#666', type: 'dashed' } }
        ],
        silent: true
      }
    }]
  })
}

watch([results, activeStrategy], () => {
  nextTick(() => renderStrategyChart())
})

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (chart) {
    chart.dispose()
    chart = null
  }
})

function handleResize() {
  chart?.resize()
}
</script>