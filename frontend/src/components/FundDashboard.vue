<template>
  <div class="flex flex-col h-full bg-terminal-bg text-terminal-fg font-mono overflow-y-auto">
    
    <!-- 顶部：搜索栏 -->
    <div class="p-4 border-b border-theme-secondary shrink-0 bg-terminal-panel/50">
      <div class="flex flex-col md:flex-row gap-3 items-start md:items-center justify-between">
        <!-- 搜索框 -->
        <div class="flex items-center gap-2 w-full md:w-auto">
          <span class="text-terminal-accent font-bold text-sm whitespace-nowrap">📊 公募基金分析</span>
          <div class="relative flex-1 md:w-64">
            <input 
              v-model="searchQuery" 
              @keyup.enter="searchFund"
              placeholder="输入基金代码/名称/拼音"
              class="w-full bg-terminal-bg border border-theme-secondary rounded px-3 py-1.5 text-sm focus:border-terminal-accent outline-none"
            />
            <button 
              @click="searchFund"
              class="absolute right-1 top-1/2 -translate-y-1/2 px-2 py-0.5 text-xs bg-terminal-accent/20 text-terminal-accent rounded hover:bg-terminal-accent/30 transition"
            >🔍</button>
          </div>
        </div>
        <!-- 快捷基金列表 -->
        <div class="flex gap-1 flex-wrap">
          <button 
            v-for="f in quickFunds" 
            :key="f.code"
            @click="selectFund(f.code)"
            class="px-2 py-1 text-xs rounded border transition-colors whitespace-nowrap"
            :class="selectedFundCode === f.code 
              ? 'bg-terminal-accent/20 border-terminal-accent/50 text-terminal-accent' 
              : 'bg-terminal-bg border-theme-secondary text-theme-tertiary hover:border-gray-500'"
          >
            {{ f.name }}
          </button>
        </div>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="flex-1 flex items-center justify-center">
      <div class="text-center">
        <div class="text-2xl mb-2">⏳</div>
        <div class="text-theme-muted text-sm">正在加载基金数据...</div>
      </div>
    </div>

    <!-- 无数据 -->
    <div v-else-if="!fundInfo && !loading" class="flex-1 flex items-center justify-center">
      <div class="text-center">
        <div class="text-4xl mb-3">📭</div>
        <div class="text-theme-muted text-sm">请输入基金代码或从快捷列表选择</div>
        <div class="text-xs text-theme-tertiary mt-1">支持 ETF、LOF、场外基金</div>
      </div>
    </div>

    <!-- 主内容区 -->
    <div v-else class="flex-1 p-4 space-y-4 overflow-y-auto">
      
      <!-- 核心指标卡片 -->
      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <div class="bg-terminal-panel/50 border border-theme rounded-lg p-3">
          <div class="text-[10px] text-theme-tertiary mb-1">最新净值</div>
          <div class="text-lg font-bold" :class="getChangeColor(fundInfo?.nav_change_pct)">
            {{ fundInfo?.nav ?? '-' }}
          </div>
        </div>
        <div class="bg-terminal-panel/50 border border-theme rounded-lg p-3">
          <div class="text-[10px] text-theme-tertiary mb-1">日涨跌</div>
          <div class="text-lg font-bold" :class="getChangeColor(fundInfo?.nav_change_pct)">
            {{ fundInfo?.nav_change_pct ?? '-' }}%
          </div>
        </div>
        <div class="bg-terminal-panel/50 border border-theme rounded-lg p-3">
          <div class="text-[10px] text-theme-tertiary mb-1">基金规模</div>
          <div class="text-lg font-bold text-theme-primary">
            {{ fundInfo?.scale ?? '-' }}亿
          </div>
        </div>
        <div class="bg-terminal-panel/50 border border-theme rounded-lg p-3">
          <div class="text-[10px] text-theme-tertiary mb-1">成立时间</div>
          <div class="text-sm font-bold text-theme-primary">
            {{ fundInfo?.found_date ?? '-' }}
          </div>
        </div>
        <div class="bg-terminal-panel/50 border border-theme rounded-lg p-3">
          <div class="text-[10px] text-theme-tertiary mb-1">基金经理</div>
          <div class="text-xs font-bold text-theme-primary truncate" :title="fundInfo?.manager">
            {{ fundInfo?.manager ?? '-' }}
          </div>
        </div>
        <div class="bg-terminal-panel/50 border border-theme rounded-lg p-3">
          <div class="text-[10px] text-theme-tertiary mb-1">基金类型</div>
          <div class="text-xs font-bold text-theme-primary">
            {{ fundInfo?.type ?? '-' }}
          </div>
        </div>
      </div>

      <!-- 净值走势 + 资产配置 -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <!-- 净值走势图 -->
        <div class="lg:col-span-2 bg-terminal-panel border border-theme rounded-xl p-4">
          <div class="flex items-center justify-between mb-3">
            <span class="text-terminal-accent font-bold text-sm">📈 净值走势</span>
            <div class="flex gap-1">
              <button 
                v-for="p in navPeriods" 
                :key="p.key"
                @click="loadNavHistory(p.key)"
                class="px-2 py-0.5 text-[10px] rounded border transition"
                :class="navPeriod === p.key 
                  ? 'bg-terminal-accent/20 border-terminal-accent/50 text-terminal-accent' 
                  : 'bg-terminal-bg border-theme-secondary text-theme-tertiary hover:border-gray-500'"
              >{{ p.label }}</button>
            </div>
          </div>
          <div ref="navChartRef" class="w-full" style="height: 280px;"></div>
        </div>

        <!-- 资产配置饼图 -->
        <div class="bg-terminal-panel border border-theme rounded-xl p-4">
          <div class="flex items-center justify-between mb-3">
            <span class="text-terminal-accent font-bold text-sm">🎯 资产配置</span>
            <span class="text-[10px] text-theme-tertiary">X-Ray 穿透</span>
          </div>
          <div ref="assetChartRef" class="w-full" style="height: 200px;"></div>
          <!-- 配置明细 -->
          <div class="mt-3 space-y-1">
            <div v-for="(item, i) in assetAllocation" :key="i" 
                 class="flex items-center justify-between text-xs">
              <div class="flex items-center gap-2">
                <span class="w-2 h-2 rounded-full" :style="{ background: item.color }"></span>
                <span class="text-theme-secondary">{{ item.name }}</span>
              </div>
              <span class="text-theme-primary font-bold">{{ item.value }}%</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 十大重仓股 -->
      <div class="bg-terminal-panel border border-theme rounded-xl p-4">
        <div class="flex items-center justify-between mb-3">
          <span class="text-terminal-accent font-bold text-sm">📊 十大重仓股</span>
          <span class="text-[10px] text-theme-tertiary">截至 {{ fundInfo?.report_date ?? '-' }}</span>
        </div>
        <div class="overflow-x-auto scrollbar-hide">
          <table class="w-full text-xs whitespace-nowrap">
            <thead class="border-b border-theme">
              <tr class="text-terminal-dim">
                <th class="px-2 py-2 text-left font-normal">#</th>
                <th class="px-2 py-2 text-left font-normal">代码</th>
                <th class="px-2 py-2 text-left font-normal">名称</th>
                <th class="px-2 py-2 text-right font-normal">持仓价</th>
                <th class="px-2 py-2 text-right font-normal">持仓占比</th>
                <th class="px-2 py-2 text-right font-normal">较上期</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(stock, i) in topHoldings" :key="i" 
                  class="border-b border-theme/30 hover:bg-theme-hover/30 transition-colors">
                <td class="px-2 py-2 text-theme-tertiary">{{ i + 1 }}</td>
                <td class="px-2 py-2 text-theme-primary">{{ stock.code }}</td>
                <td class="px-2 py-2 text-theme-primary font-medium">{{ stock.name }}</td>
                <td class="px-2 py-2 text-right" :class="getChangeColor(stock.change_pct)">
                  {{ stock.price ?? '-' }}
                </td>
                <td class="px-2 py-2 text-right text-theme-accent font-bold">{{ stock.ratio }}%</td>
                <td class="px-2 py-2 text-right" :class="getChangeColor(stock.change)">
                  {{ stock.change > 0 ? '+' : '' }}{{ stock.change }}%
                </td>
              </tr>
              <tr v-if="topHoldings.length === 0">
                <td colspan="6" class="px-2 py-8 text-center text-theme-muted">
                  暂无重仓股数据
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import { apiFetch, extractData } from '../utils/api.js'
import { logger } from '../utils/logger.js'

// ── 状态 ────────────────────────────────────────────────────────
const loading = ref(false)
const searchQuery = ref('')
const selectedFundCode = ref('')
const fundInfo = ref(null)
const navHistory = ref([])
const topHoldings = ref([])
const assetAllocation = ref([])

// 快捷基金列表
const quickFunds = [
  { code: '510300', name: '沪深 300ETF' },
  { code: '510500', name: '中证 500ETF' },
  { code: '159915', name: '创业板 ETF' },
  { code: '518880', name: '黄金 ETF' },
  { code: '513050', name: '中概互联 ETF' },
]

// 净值周期选项
const navPeriods = [
  { key: '1m', label: '1 月' },
  { key: '3m', label: '3 月' },
  { key: '6m', label: '6 月' },
  { key: '1y', label: '1 年' },
  { key: '3y', label: '3 年' },
  { key: 'all', label: '成立' },
]
const navPeriod = ref('6m')

// Chart refs
const navChartRef = ref(null)
const assetChartRef = ref(null)
let navChart = null
let assetChart = null

// ── API 调用 ────────────────────────────────────────────────────

/**
 * 搜索基金（调用场外基金排行接口模拟搜索）
 */
async function searchFund() {
  const query = searchQuery.value.trim()
  if (!query) return
  await selectFund(query)
}

/**
 * 选择基金并加载数据
 */
async function selectFund(code) {
  if (!code) return
  selectedFundCode.value = code
  loading.value = true
  
  try {
    // 1. 获取基金基本信息（通过 ETF info 接口）
    await Promise.all([
      loadFundInfo(code),
      loadNavHistory(navPeriod.value),
      loadPortfolio(code)
    ])
  } catch (e) {
    logger.error('[FundDashboard] 加载失败:', e)
  } finally {
    loading.value = false
  }
}

/**
 * 加载基金基本信息
 */
async function loadFundInfo(code) {
  try {
    const isETF = /^[0-9]{6}$/.test(code) && (code.startsWith('51') || code.startsWith('15'))
    if (isETF) {
      // ETF 使用 /api/v1/fund/etf/info
      const res = await apiFetch(`/api/v1/fund/etf/info?code=${code}`)
      const data = extractData(res)
      if (data) {
        fundInfo.value = {
          code: data.symbol || code,
          name: data.name || '-',
          nav: data.data?.price || '-',
          nav_change_pct: data.data?.change_pct ? parseFloat(data.data.change_pct).toFixed(2) : '-',
          scale: data.data?.amount ? (parseFloat(data.data.amount) / 100000000).toFixed(1) : '-',
          found_date: '-',
          manager: '-',
          type: 'ETF'
        }
      }
    } else {
      // 场外基金：从排行接口查找
      const res = await apiFetch('/api/v1/fund/open/rank')
      const data = extractData(res)
      if (Array.isArray(data)) {
        const found = data.find(f => f.code === code || f.name?.includes(code))
        if (found) {
          fundInfo.value = {
            code: found.code,
            name: found.name,
            nav: found.nav,
            nav_change_pct: found.nav_growthrate,
            scale: found.scale ? parseFloat(found.scale).toFixed(1) : '-',
            found_date: found.find_date,
            manager: found.manager,
            type: found.type
          }
        }
      }
    }
  } catch (e) {
    logger.warn('[FundDashboard] 获取基金信息失败:', e)
  }
}

/**
 * 加载净值历史
 */
async function loadNavHistory(period) {
  navPeriod.value = period
  const code = selectedFundCode.value
  if (!code) return
  
  try {
    const isETF = /^[0-9]{6}$/.test(code) && (code.startsWith('51') || code.startsWith('15'))
    if (isETF) {
      const res = await apiFetch(`/api/v1/fund/etf/history?code=${code}&period=${period}`)
      const data = extractData(res)
      navHistory.value = Array.isArray(data) ? data : []
    } else {
      // 场外基金暂用 mock 数据
      navHistory.value = generateMockNavHistory(period)
    }
    
    // 渲染图表
    await nextTick()
    renderNavChart()
  } catch (e) {
    logger.warn('[FundDashboard] 获取净值历史失败:', e)
    navHistory.value = generateMockNavHistory(period)
    await nextTick()
    renderNavChart()
  }
}

/**
 * 加载投资组合（重仓股 + 资产配置）
 */
async function loadPortfolio(code) {
  try {
    const res = await apiFetch(`/api/v1/fund/portfolio/${code}`)
    const data = extractData(res)
    if (Array.isArray(data)) {
      // 重仓股（API 返回的是数组）
      topHoldings.value = data.slice(0, 10).map(s => ({
        code: s.symbol || s.code,
        name: s.name,
        price: '-',  // API 不返回实时股价
        change_pct: 0,
        ratio: s.weight || s.ratio,
        change: 0  // API 不返回较上期变化
      }))
      
      // 资产配置（Mock，API 暂不支持）
      assetAllocation.value = [
        { name: '股票', value: 95.0, color: '#60a5fa' },
        { name: '现金', value: 5.0, color: '#fbbf24' }
      ]
    }
    
    await nextTick()
    renderAssetChart()
  } catch (e) {
    logger.warn('[FundDashboard] 获取投资组合失败:', e)
    // Mock 数据
    assetAllocation.value = [
      { name: '股票', value: 85.5, color: '#60a5fa' },
      { name: '债券', value: 5.2, color: '#34d399' },
      { name: '现金', value: 8.3, color: '#fbbf24' },
      { name: '其他', value: 1.0, color: '#a78bfa' }
    ]
    topHoldings.value = []
    await nextTick()
    renderAssetChart()
  }
}

// ── ECharts 渲染 ───────────────────────────────────────────────

function renderNavChart() {
  if (!navChartRef.value) return
  
  if (!navChart) {
    navChart = echarts.init(navChartRef.value)
  }
  
  const data = navHistory.value.map(d => ({
    date: d.date || d.trade_date,
    value: d.nav || d.close
  })).reverse()
  
  const option = {
    tooltip: { trigger: 'axis' },
    grid: { top: 10, right: 10, bottom: 20, left: 40 },
    xAxis: {
      type: 'category',
      data: data.map(d => d.date),
      axisLine: { lineStyle: { color: '#4b5563' } },
      axisLabel: { color: '#9ca3af', fontSize: 10 }
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#4b5563' } },
      axisLabel: { color: '#9ca3af', fontSize: 10 },
      splitLine: { lineStyle: { color: '#374151' } }
    },
    series: [{
      type: 'line',
      data: data.map(d => d.value),
      smooth: true,
      lineStyle: { color: '#60a5fa', width: 2 },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(96, 165, 250, 0.3)' },
            { offset: 1, color: 'rgba(96, 165, 250, 0)' }
          ]
        }
      }
    }]
  }
  
  navChart.setOption(option)
}

function renderAssetChart() {
  if (!assetChartRef.value) return
  
  if (!assetChart) {
    assetChart = echarts.init(assetChartRef.value)
  }
  
  const option = {
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '50%'],
      itemStyle: {
        borderRadius: 4,
        borderColor: '#1f2937',
        borderWidth: 2
      },
      label: { show: false },
      data: assetAllocation.value.map(a => ({
        name: a.name,
        value: a.value,
        itemStyle: { color: a.color }
      }))
    }]
  }
  
  assetChart.setOption(option)
}

// ── 工具函数 ───────────────────────────────────────────────────

function getChangeColor(pct) {
  if (pct === '-' || pct === undefined) return 'text-theme-muted'
  const v = parseFloat(pct)
  if (v > 0) return 'text-red-400'
  if (v < 0) return 'text-green-400'
  return 'text-theme-primary'
}

function generateMockNavHistory(period) {
  const days = { '1m': 20, '3m': 60, '6m': 120, '1y': 240, '3y': 720, 'all': 1000 }[period] || 120
  const result = []
  let base = 1.0 + Math.random() * 2
  for (let i = 0; i < days; i++) {
    const date = new Date()
    date.setDate(date.getDate() - (days - i))
    base = base * (1 + (Math.random() - 0.48) * 0.03)
    result.push({
      date: date.toISOString().split('T')[0],
      nav: base.toFixed(4)
    })
  }
  return result
}

// ── 生命周期 ───────────────────────────────────────────────────

onMounted(() => {
  window.addEventListener('resize', () => {
    navChart?.resize()
    assetChart?.resize()
  })
  
  // 默认加载第一个快捷基金
  if (quickFunds.length > 0) {
    selectFund(quickFunds[0].code)
  }
})

onUnmounted(() => {
  navChart?.dispose()
  assetChart?.dispose()
})
</script>

<style scoped>
/* 响应式：移动端优化 */
@media (max-width: 768px) {
  .grid-cols-6 {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
