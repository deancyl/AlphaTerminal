<template>
  <div class="flex flex-col h-full bg-terminal-bg text-terminal-fg font-mono overflow-y-auto">
    
    <!-- 顶部：选项卡 + 搜索 -->
    <div class="p-4 border-b border-theme-secondary shrink-0 bg-terminal-panel/50">
      <div class="flex flex-col gap-3">
        <!-- 选项卡 -->
        <div class="flex gap-2">
          <button 
            @click="activeTab = 'etf'"
            class="px-4 py-2 text-sm rounded-t-lg border-b-2 transition-colors"
            :class="activeTab === 'etf' 
              ? 'bg-terminal-panel border-terminal-accent text-terminal-accent' 
              : 'bg-terminal-bg border-transparent text-theme-tertiary hover:text-theme-secondary'"
          >📊 场内基金 (ETF/LOF)</button>
          <button 
            @click="activeTab = 'open'"
            class="px-4 py-2 text-sm rounded-t-lg border-b-2 transition-colors"
            :class="activeTab === 'open' 
              ? 'bg-terminal-panel border-terminal-accent text-terminal-accent' 
              : 'bg-terminal-bg border-transparent text-theme-tertiary hover:text-theme-secondary'"
          >💰 场外公募基金</button>
        </div>
        
        <!-- 搜索栏 -->
        <div class="flex items-center gap-2">
          <div class="relative flex-1">
            <input 
              v-model="searchQuery" 
              @keyup.enter="searchFund"
              :placeholder="activeTab === 'etf' ? '输入 ETF 代码（如 510300）' : '输入基金代码/名称/拼音'"
              class="w-full bg-terminal-bg border border-theme-secondary rounded px-3 py-1.5 text-sm focus:border-terminal-accent outline-none"
            />
            <button 
              @click="searchFund"
              class="absolute right-1 top-1/2 -translate-y-1/2 px-2 py-0.5 text-xs bg-terminal-accent/20 text-terminal-accent rounded hover:bg-terminal-accent/30 transition"
            >🔍</button>
          </div>
          <!-- 快捷列表 -->
          <div class="flex gap-1 flex-wrap">
            <button 
              v-for="f in (activeTab === 'etf' ? quickETFs : quickFunds)" 
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
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="flex-1 flex items-center justify-center">
      <div class="text-center">
        <div class="text-2xl mb-2">⏳</div>
        <div class="text-theme-muted text-sm">正在加载{{ activeTab === 'etf' ? 'ETF' : '基金' }}数据...</div>
        <div v-if="dataSource" class="text-xs text-theme-tertiary mt-1">数据源：{{ dataSource }}</div>
      </div>
    </div>

    <!-- 无数据 -->
    <div v-else-if="!fundInfo && !loading" class="flex-1 flex items-center justify-center">
      <div class="text-center">
        <div class="text-4xl mb-3">📭</div>
        <div class="text-theme-muted text-sm">请输入代码或从快捷列表选择</div>
        <div class="text-xs text-theme-tertiary mt-1">
          {{ activeTab === 'etf' ? '支持沪深 ETF、LOF' : '支持股票型、混合型、债券型基金' }}
        </div>
      </div>
    </div>

    <!-- 主内容区 -->
    <div v-else class="flex-1 p-4 space-y-4 overflow-y-auto">
      
      <!-- ETF 面板 -->
      <div v-if="activeTab === 'etf'" class="space-y-4">
        <!-- 核心指标（ETF 特有） -->
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <div class="bg-terminal-panel/50 border border-theme rounded-lg p-3">
            <div class="text-[10px] text-theme-tertiary mb-1">最新价</div>
            <div class="text-lg font-bold" :class="getChangeColor(fundInfo?.change_pct)">
              {{ fundInfo?.price ?? '-' }}
            </div>
          </div>
          <div class="bg-terminal-panel/50 border border-theme rounded-lg p-3">
            <div class="text-[10px] text-theme-tertiary mb-1">涨跌幅</div>
            <div class="text-lg font-bold" :class="getChangeColor(fundInfo?.change_pct)">
              {{ fundInfo?.change_pct ?? '-' }}%
            </div>
          </div>
          <div class="bg-terminal-panel/50 border border-theme rounded-lg p-3">
            <div class="text-[10px] text-theme-tertiary mb-1">IOPV 净值</div>
            <div class="text-lg font-bold text-theme-primary">
              {{ fundInfo?.iopv ?? '-' }}
            </div>
          </div>
          <div class="bg-terminal-panel/50 border border-theme rounded-lg p-3">
            <div class="text-[10px] text-theme-tertiary mb-1">折溢价率</div>
            <div class="text-lg font-bold" :class="getChangeColor(-fundInfo?.premium_rate)">
              {{ fundInfo?.premium_rate ?? '-' }}%
            </div>
          </div>
          <div class="bg-terminal-panel/50 border border-theme rounded-lg p-3">
            <div class="text-[10px] text-theme-tertiary mb-1">成交量</div>
            <div class="text-sm font-bold text-theme-primary">
              {{ formatVolume(fundInfo?.volume) }}
            </div>
          </div>
          <div class="bg-terminal-panel/50 border border-theme rounded-lg p-3">
            <div class="text-[10px] text-theme-tertiary mb-1">成交额</div>
            <div class="text-sm font-bold text-theme-primary">
              {{ formatAmount(fundInfo?.amount) }}
            </div>
          </div>
        </div>

        <!-- K 线走势图 -->
        <div class="bg-terminal-panel border border-theme rounded-xl p-4">
          <div class="flex items-center justify-between mb-3">
            <span class="text-terminal-accent font-bold text-sm">📈 K 线走势</span>
            <div class="flex gap-1">
              <button 
                v-for="p in klinePeriods" 
                :key="p.key"
                @click="loadETFHistory(p.key)"
                class="px-2 py-0.5 text-[10px] rounded border transition"
                :class="klinePeriod === p.key 
                  ? 'bg-terminal-accent/20 border-terminal-accent/50 text-terminal-accent' 
                  : 'bg-terminal-bg border-theme-secondary text-theme-tertiary hover:border-gray-500'"
              >{{ p.label }}</button>
            </div>
          </div>
          <div ref="klineChartRef" class="w-full" style="height: 320px;"></div>
        </div>

        <!-- 数据源信息 -->
        <div class="text-xs text-theme-tertiary text-center">
          数据来源：{{ dataSource }} | 最后更新：{{ lastUpdateTime }}
        </div>
      </div>

      <!-- 公募基金面板 -->
      <div v-else class="space-y-4">
        <!-- 核心指标（公募特有） -->
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <div class="bg-terminal-panel/50 border border-theme rounded-lg p-3">
            <div class="text-[10px] text-theme-tertiary mb-1">单位净值</div>
            <div class="text-lg font-bold" :class="getChangeColor(fundInfo?.nav_change_pct)">
              {{ fundInfo?.nav ?? '-' }}
            </div>
          </div>
          <div class="bg-terminal-panel/50 border border-theme rounded-lg p-3">
            <div class="text-[10px] text-theme-tertiary mb-1">累计净值</div>
            <div class="text-lg font-bold text-theme-primary">
              {{ fundInfo?.accumulated_nav ?? '-' }}
            </div>
          </div>
          <div class="bg-terminal-panel/50 border border-theme rounded-lg p-3">
            <div class="text-[10px] text-theme-tertiary mb-1">日增长率</div>
            <div class="text-lg font-bold" :class="getChangeColor(fundInfo?.nav_change_pct)">
              {{ fundInfo?.nav_change_pct ?? '-' }}%
            </div>
          </div>
          <div class="bg-terminal-panel/50 border border-theme rounded-lg p-3">
            <div class="text-[10px] text-theme-tertiary mb-1">基金规模</div>
            <div class="text-sm font-bold text-theme-primary">
              {{ fundInfo?.scale ?? '-' }}亿
            </div>
          </div>
          <div class="bg-terminal-panel/50 border border-theme rounded-lg p-3">
            <div class="text-[10px] text-theme-tertiary mb-1">成立日期</div>
            <div class="text-xs font-bold text-theme-primary">
              {{ fundInfo?.found_date ?? '-' }}
            </div>
          </div>
          <div class="bg-terminal-panel/50 border border-theme rounded-lg p-3">
            <div class="text-[10px] text-theme-tertiary mb-1">基金类型</div>
            <div class="text-xs font-bold text-theme-primary">
              {{ fundInfo?.type ?? '-' }}
            </div>
          </div>
        </div>

        <!-- 基金经理与公司 -->
        <div class="bg-terminal-panel border border-theme rounded-xl p-4">
          <div class="flex items-center justify-between mb-3">
            <span class="text-terminal-accent font-bold text-sm">👨‍💼 基金管理人</span>
          </div>
          <div class="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span class="text-theme-tertiary">基金经理：</span>
              <span class="text-theme-primary font-medium">{{ fundInfo?.manager ?? '-' }}</span>
            </div>
            <div>
              <span class="text-theme-tertiary">基金公司：</span>
              <span class="text-theme-primary font-medium">{{ fundInfo?.company ?? '-' }}</span>
            </div>
          </div>
        </div>

        <!-- 净值走势图 -->
        <div class="bg-terminal-panel border border-theme rounded-xl p-4">
          <div class="flex items-center justify-between mb-3">
            <span class="text-terminal-accent font-bold text-sm">📈 净值走势</span>
            <div class="flex gap-1">
              <button 
                v-for="p in navPeriods" 
                :key="p.key"
                @click="loadNAVHistory(p.key)"
                class="px-2 py-0.5 text-[10px] rounded border transition"
                :class="navPeriod === p.key 
                  ? 'bg-terminal-accent/20 border-terminal-accent/50 text-terminal-accent' 
                  : 'bg-terminal-bg border-theme-secondary text-theme-tertiary hover:border-gray-500'"
              >{{ p.label }}</button>
            </div>
          </div>
          <div ref="navChartRef" class="w-full" style="height: 280px;"></div>
        </div>

        <!-- 资产配置 + 重仓股 -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <!-- 资产配置饼图 -->
          <div class="bg-terminal-panel border border-theme rounded-xl p-4">
            <div class="flex items-center justify-between mb-3">
              <span class="text-terminal-accent font-bold text-sm">🎯 资产配置</span>
              <span class="text-[10px] text-theme-tertiary">X-Ray</span>
            </div>
            <div ref="assetChartRef" class="w-full" style="height: 200px;"></div>
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

          <!-- 重仓股表格 -->
          <div class="bg-terminal-panel border border-theme rounded-xl p-4">
            <div class="flex items-center justify-between mb-3">
              <span class="text-terminal-accent font-bold text-sm">📊 重仓股</span>
              <span class="text-[10px] text-theme-tertiary">{{ fundInfo?.quarter ?? '-' }}</span>
            </div>
            <div class="overflow-x-auto scrollbar-hide">
              <table class="w-full text-xs whitespace-nowrap">
                <thead class="border-b border-theme">
                  <tr class="text-terminal-dim">
                    <th class="px-2 py-2 text-left font-normal">#</th>
                    <th class="px-2 py-2 text-left font-normal">代码</th>
                    <th class="px-2 py-2 text-left font-normal">名称</th>
                    <th class="px-2 py-2 text-right font-normal">占比</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(stock, i) in topHoldings" :key="i" 
                      class="border-b border-theme/30 hover:bg-theme-hover/30">
                    <td class="px-2 py-2 text-theme-tertiary">{{ i + 1 }}</td>
                    <td class="px-2 py-2 text-theme-primary">{{ stock.code }}</td>
                    <td class="px-2 py-2 text-theme-primary font-medium">{{ stock.name }}</td>
                    <td class="px-2 py-2 text-right text-theme-accent font-bold">{{ stock.ratio }}%</td>
                  </tr>
                  <tr v-if="topHoldings.length === 0">
                    <td colspan="4" class="px-2 py-8 text-center text-theme-muted">暂无重仓股数据</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- 数据源信息 -->
        <div class="text-xs text-theme-tertiary text-center">
          数据来源：{{ dataSource }} | 最后更新：{{ lastUpdateTime }}
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
const activeTab = ref('open') // 'etf' | 'open' - 默认场外基金（更常用）
const fundInfo = ref(null)
const dataSource = ref('')
const lastUpdateTime = ref('')

// 快捷列表
const quickETFs = [
  { code: '510300', name: '沪深 300ETF' },
  { code: '510500', name: '中证 500ETF' },
  { code: '159915', name: '创业板 ETF' },
  { code: '518880', name: '黄金 ETF' },
  { code: '513050', name: '中概互联 ETF' },
]

const quickFunds = [
  { code: '005827', name: '易方达蓝筹' },
  { code: '000311', name: '景顺长城沪深 300' },
  { code: '110011', name: '易方达中小盘' },
  { code: '007119', name: '睿远成长价值' },
]

// 周期选项
const klinePeriods = [
  { key: 'daily', label: '日 K' },
  { key: 'weekly', label: '周 K' },
  { key: 'monthly', label: '月 K' },
]
const klinePeriod = ref('daily')

const navPeriods = [
  { key: '1m', label: '1 月' },
  { key: '3m', label: '3 月' },
  { key: '6m', label: '6 月' },
  { key: '1y', label: '1 年' },
]
const navPeriod = ref('6m')

// 数据
const klineHistory = ref([])
const navHistory = ref([])
const topHoldings = ref([])
const assetAllocation = ref([])

// Chart refs
const klineChartRef = ref(null)
const navChartRef = ref(null)
const assetChartRef = ref(null)
let klineChart = null
let navChart = null
let assetChart = null

// ── API 调用 ────────────────────────────────────────────────────

async function searchFund() {
  const query = searchQuery.value.trim()
  if (!query) return
  await selectFund(query)
}

async function selectFund(code) {
  if (!code) return
  selectedFundCode.value = code
  loading.value = true
  dataSource.value = ''
  
  try {
    if (activeTab.value === 'etf') {
      await Promise.all([
        loadETFInfo(code),
        loadETFHistory(klinePeriod.value),
      ])
    } else {
      await Promise.all([
        loadOpenFundInfo(code),
        loadNAVHistory(navPeriod.value),
        loadPortfolio(code),
      ])
    }
    
    lastUpdateTime.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } catch (e) {
    logger.error('[FundDashboard] 加载失败:', e)
  } finally {
    loading.value = false
  }
}

// ── ETF 相关 ───────────────────────────────────────────────────

async function loadETFInfo(code) {
  try {
    const res = await apiFetch(`/api/v1/fund/etf/info?code=${code}`)
    const data = extractData(res)
    if (data) {
      fundInfo.value = {
        code: data.code || code,
        name: data.name || '-',
        price: data.price || '-',
        change_pct: data.change_pct ? parseFloat(data.change_pct).toFixed(2) : '-',
        change: data.change || 0,
        volume: data.volume || 0,
        amount: data.amount || 0,
        iopv: data.iopv || '-',
        premium_rate: data.premium_rate ? parseFloat(data.premium_rate).toFixed(2) : '-',
      }
      dataSource.value = data.source || 'unknown'
    }
  } catch (e) {
    logger.warn('[ETF Info] 获取失败:', e)
  }
}

async function loadETFHistory(period) {
  klinePeriod.value = period
  const code = selectedFundCode.value
  if (!code) return
  
  try {
    const res = await apiFetch(`/api/v1/fund/etf/history?code=${code}&period=${period}`)
    const data = extractData(res)
    klineHistory.value = Array.isArray(data) ? data : []
    
    await nextTick()
    renderKlineChart()
  } catch (e) {
    logger.warn('[ETF History] 获取失败:', e)
  }
}

// ── 公募基金相关 ───────────────────────────────────────────────

async function loadOpenFundInfo(code) {
  try {
    const res = await apiFetch(`/api/v1/fund/open/info?code=${code}`)
    const data = extractData(res)
    if (data) {
      fundInfo.value = {
        code: data.code || code,
        name: data.name || '-',
        type: data.type || '-',
        nav: data.nav || '-',
        accumulated_nav: data.accumulated_nav || '-',
        nav_change_pct: data.nav_change_pct ? parseFloat(data.nav_change_pct).toFixed(2) : '-',
        nav_date: data.nav_date || '-',
        scale: data.scale || '-',
        found_date: data.found_date || '-',
        manager: data.manager || '-',
        company: data.company || '-',
        quarter: data.quarter || '-',
      }
      dataSource.value = data.source || 'unknown'
    }
  } catch (e) {
    logger.warn('[Open Fund Info] 获取失败:', e)
  }
}

async function loadNAVHistory(period) {
  navPeriod.value = period
  const code = selectedFundCode.value
  if (!code) return
  
  try {
    const res = await apiFetch(`/api/v1/fund/open/nav/${code}?period=${period}`)
    const data = extractData(res)
    navHistory.value = Array.isArray(data) ? data : []
    
    await nextTick()
    renderNavChart()
  } catch (e) {
    logger.warn('[NAV History] 获取失败:', e)
  }
}

async function loadPortfolio(code) {
  try {
    const res = await apiFetch(`/api/v1/fund/portfolio/${code}`)
    const data = extractData(res)
    if (data) {
      topHoldings.value = (data.stocks || []).slice(0, 10)
      fundInfo.value = { ...fundInfo.value, quarter: data.quarter || '' }
      
      if (data.assets && data.assets.length > 0) {
        assetAllocation.value = data.assets.map((a, i) => ({
          name: a.name,
          value: a.ratio,
          color: ['#60a5fa', '#34d399', '#fbbf24', '#f87171', '#a78bfa'][i % 5]
        }))
      } else {
        // Mock
        assetAllocation.value = [
          { name: '股票', value: 85.5, color: '#60a5fa' },
          { name: '债券', value: 5.2, color: '#34d399' },
          { name: '现金', value: 8.3, color: '#fbbf24' },
          { name: '其他', value: 1.0, color: '#a78bfa' }
        ]
      }
      
      await nextTick()
      renderAssetChart()
    }
  } catch (e) {
    logger.warn('[Portfolio] 获取失败:', e)
  }
}

// ── ECharts 渲染 ───────────────────────────────────────────────

function renderKlineChart() {
  if (!klineChartRef.value) return
  if (!klineChart) klineChart = echarts.init(klineChartRef.value)
  
  const data = klineHistory.value.map(d => ({
    date: d.date || d.trade_date,
    value: d.close || d.nav
  })).reverse()
  
  const option = {
    tooltip: { trigger: 'axis' },
    grid: { top: 10, right: 10, bottom: 20, left: 40 },
    xAxis: {
      type: 'category',
      data: data.map(d => d.date),
      axisLine: { lineStyle: { color: '#4b5563' } },
      axisLabel: { color: '#9ca3af', fontSize: 10, maxRotation: 45 }
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
      smooth: false,
      lineStyle: { color: '#60a5fa', width: 1.5 },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(96, 165, 250, 0.3)' },
            { offset: 1, color: 'rgba(96, 165, 250, 0)' }
          ]
        }
      }
    }]
  }
  klineChart.setOption(option)
}

function renderNavChart() {
  if (!navChartRef.value) return
  if (!navChart) navChart = echarts.init(navChartRef.value)
  
  const data = navHistory.value.map(d => ({
    date: d.date,
    nav: d.nav,
    accumulated: d.accumulated_nav
  }))
  
  const option = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['单位净值', '累计净值'], textStyle: { color: '#9ca3af', fontSize: 10 } },
    grid: { top: 30, right: 10, bottom: 20, left: 40 },
    xAxis: {
      type: 'category',
      data: data.map(d => d.date),
      axisLine: { lineStyle: { color: '#4b5563' } },
      axisLabel: { color: '#9ca3af', fontSize: 10, maxRotation: 45 }
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#4b5563' } },
      axisLabel: { color: '#9ca3af', fontSize: 10 },
      splitLine: { lineStyle: { color: '#374151' } }
    },
    series: [
      { name: '单位净值', type: 'line', data: data.map(d => d.nav), smooth: true, lineStyle: { color: '#60a5fa', width: 2 } },
      { name: '累计净值', type: 'line', data: data.map(d => d.accumulated), smooth: true, lineStyle: { color: '#34d399', width: 2, type: 'dashed' } }
    ]
  }
  navChart.setOption(option)
}

function renderAssetChart() {
  if (!assetChartRef.value) return
  if (!assetChart) assetChart = echarts.init(assetChartRef.value)
  
  const option = {
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '50%'],
      itemStyle: { borderRadius: 4, borderColor: '#1f2937', borderWidth: 2 },
      label: { show: false },
      data: assetAllocation.value.map(a => ({ name: a.name, value: a.value, itemStyle: { color: a.color } }))
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

function formatVolume(vol) {
  if (!vol) return '-'
  if (vol > 100000000) return (vol / 100000000).toFixed(1) + '亿'
  if (vol > 10000) return (vol / 10000).toFixed(0) + '万'
  return vol.toFixed(0)
}

function formatAmount(amt) {
  if (!amt) return '-'
  if (amt > 100000000) return (amt / 100000000).toFixed(1) + '亿'
  if (amt > 10000) return (amt / 10000).toFixed(0) + '万'
  return amt.toFixed(0)
}

// ── 生命周期 ───────────────────────────────────────────────────

onMounted(() => {
  window.addEventListener('resize', () => {
    klineChart?.resize()
    navChart?.resize()
    assetChart?.resize()
  })
  
  // 默认加载第一个快捷基金（根据当前选项卡）
  if (activeTab.value === 'etf' && quickETFs.length > 0) {
    selectFund(quickETFs[0].code)
  } else if (activeTab.value === 'open' && quickFunds.length > 0) {
    selectFund(quickFunds[0].code)
  }
})

onUnmounted(() => {
  klineChart?.dispose()
  navChart?.dispose()
  assetChart?.dispose()
})

// 监听选项卡切换
watch(activeTab, () => {
  searchQuery.value = ''
  fundInfo.value = null
  selectedFundCode.value = ''
})
</script>

<style scoped>
@media (max-width: 768px) {
  .grid-cols-6 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .grid-cols-3 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
