<template>
  <div class="h-full flex flex-col bg-terminal-bg overflow-hidden">
    <!-- 顶部标题栏 -->
    <div class="flex-shrink-0 flex items-center justify-between px-4 py-3 border-b border-theme-secondary">
      <div class="flex items-center gap-3">
        <span class="text-lg font-bold text-terminal-accent">📊 宏观经济</span>
        <span class="text-xs text-terminal-dim hidden sm:inline">中国宏观指标监控</span>
      </div>
      <div class="flex items-center gap-2">
        <span v-if="lastUpdate" class="text-xs text-terminal-dim hidden md:inline">
          更新于 {{ formatTime(lastUpdate) }}
        </span>
        <button 
          class="px-3 py-1.5 rounded-sm text-xs bg-terminal-accent/20 text-terminal-accent hover:bg-terminal-accent/30 transition disabled:opacity-50"
          @click="refreshAll"
          :disabled="loading"
        >
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>
    </div>

    <!-- 主内容区域 - 可滚动 -->
    <div class="flex-1 overflow-y-auto">
      <!-- 核心指标卡片 - 响应式网格 -->
      <div v-if="overview" class="grid grid-cols-2 md:grid-cols-4 gap-2 md:gap-3 p-3 md:p-4">
        <!-- GDP卡片 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 hover:border-terminal-accent/50 transition-colors">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-terminal-dim cursor-help font-medium" title="国内生产总值">GDP</span>
            <span class="text-[10px] text-terminal-dim/70">{{ overview.gdp?.period }}</span>
          </div>
          <div class="text-xl md:text-2xl font-bold text-terminal-primary">
            {{ formatNumber(overview.gdp?.yoy) }}<span class="text-sm ml-0.5">%</span>
          </div>
          <div class="text-[10px] md:text-xs text-terminal-dim mt-1">同比增长</div>
          <div class="mt-2 h-1 bg-terminal-bg/50 rounded-full overflow-hidden">
            <div class="h-full bg-terminal-accent/60 rounded-full" :style="{ width: Math.min(Math.abs(overview.gdp?.yoy || 0) * 10, 100) + '%' }"></div>
          </div>
        </div>

        <!-- CPI卡片 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 hover:border-terminal-accent/50 transition-colors">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-terminal-dim cursor-help font-medium" title="消费者物价指数">CPI</span>
            <span class="text-[10px] text-terminal-dim/70">{{ overview.cpi?.period }}</span>
          </div>
          <div class="text-xl md:text-2xl font-bold" :class="getColorClass(overview.cpi?.yoy)">
            {{ formatNumber(overview.cpi?.yoy) }}<span class="text-sm ml-0.5">%</span>
          </div>
          <div class="text-[10px] md:text-xs text-terminal-dim mt-1">同比</div>
          <div class="mt-2 flex items-center gap-1">
            <span class="text-[10px]" :class="getColorClass(overview.cpi?.mom)">
              {{ overview.cpi?.mom >= 0 ? '↑' : '↓' }}{{ Math.abs(overview.cpi?.mom || 0).toFixed(1) }}%
            </span>
            <span class="text-[10px] text-terminal-dim">环比</span>
          </div>
        </div>

        <!-- PPI卡片 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 hover:border-terminal-accent/50 transition-colors">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-terminal-dim cursor-help font-medium" title="生产者物价指数">PPI</span>
            <span class="text-[10px] text-terminal-dim/70">{{ overview.ppi?.period }}</span>
          </div>
          <div class="text-xl md:text-2xl font-bold" :class="getColorClass(overview.ppi?.yoy)">
            {{ formatNumber(overview.ppi?.yoy) }}<span class="text-sm ml-0.5">%</span>
          </div>
          <div class="text-[10px] md:text-xs text-terminal-dim mt-1">同比</div>
          <div class="mt-2 h-1 bg-terminal-bg/50 rounded-full overflow-hidden">
            <div class="h-full rounded-full transition-all" 
                 :class="overview.ppi?.yoy >= 0 ? 'bg-bullish/60' : 'bg-bearish/60'"
                 :style="{ width: Math.min(Math.abs(overview.ppi?.yoy || 0) * 10, 100) + '%' }"></div>
          </div>
        </div>

        <!-- PMI卡片 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 hover:border-terminal-accent/50 transition-colors">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-terminal-dim cursor-help font-medium" title="采购经理指数">PMI</span>
            <span class="text-[10px] text-terminal-dim/70">{{ overview.pmi?.period }}</span>
          </div>
          <div class="text-xl md:text-2xl font-bold" :class="getPMIColor(overview.pmi?.manufacturing)">
            {{ formatNumber(overview.pmi?.manufacturing) }}
          </div>
          <div class="text-[10px] md:text-xs text-terminal-dim mt-1">制造业</div>
          <div class="mt-2 flex items-center gap-1">
            <span class="text-[10px]" :class="getPMIColor(overview.pmi?.manufacturing)">
              {{ overview.pmi?.manufacturing >= 50 ? '扩张' : '收缩' }}
            </span>
            <span class="text-[10px] text-terminal-dim/50">|</span>
            <span class="text-[10px] text-terminal-dim">非制造 {{ formatNumber(overview.pmi?.non_manufacturing) }}</span>
          </div>
        </div>

        <!-- M2卡片 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 hover:border-terminal-accent/50 transition-colors">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-terminal-dim cursor-help font-medium" title="广义货币供应量">M2</span>
            <span class="text-[10px] text-terminal-dim/70">{{ overview.m2?.period }}</span>
          </div>
          <div class="text-xl md:text-2xl font-bold text-terminal-primary">
            {{ formatNumber(overview.m2?.yoy) }}<span class="text-sm ml-0.5">%</span>
          </div>
          <div class="text-[10px] md:text-xs text-terminal-dim mt-1">同比</div>
          <div class="mt-2 text-[10px] text-terminal-dim">
            {{ formatLargeNumber(overview.m2?.value) }}亿元
          </div>
        </div>

        <!-- 社融卡片 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 hover:border-terminal-accent/50 transition-colors">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-terminal-dim cursor-help font-medium" title="社会融资规模">社融</span>
            <span class="text-[10px] text-terminal-dim/70">{{ overview.social_financing?.period }}</span>
          </div>
          <div class="text-xl md:text-2xl font-bold text-terminal-primary">
            {{ formatLargeNumber(overview.social_financing?.total) }}
          </div>
          <div class="text-[10px] md:text-xs text-terminal-dim mt-1">亿元</div>
          <div class="mt-2 h-1 bg-terminal-bg/50 rounded-full overflow-hidden">
            <div class="h-full bg-terminal-accent/60 rounded-full" :style="{ width: Math.min((overview.social_financing?.total || 0) / 500, 100) + '%' }"></div>
          </div>
        </div>

        <!-- 工业增加值卡片 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 hover:border-terminal-accent/50 transition-colors">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-terminal-dim cursor-help font-medium" title="工业增加值">工业</span>
            <span class="text-[10px] text-terminal-dim/70">{{ overview.industrial_production?.period }}</span>
          </div>
          <div class="text-xl md:text-2xl font-bold" :class="getColorClass(overview.industrial_production?.yoy)">
            {{ formatNumber(overview.industrial_production?.yoy) }}<span class="text-sm ml-0.5">%</span>
          </div>
          <div class="text-[10px] md:text-xs text-terminal-dim mt-1">同比</div>
          <div class="mt-2 h-1 bg-terminal-bg/50 rounded-full overflow-hidden">
            <div class="h-full rounded-full transition-all"
                 :class="overview.industrial_production?.yoy >= 0 ? 'bg-bullish/60' : 'bg-bearish/60'"
                 :style="{ width: Math.min(Math.abs(overview.industrial_production?.yoy || 0) * 10, 100) + '%' }"></div>
          </div>
        </div>

        <!-- 失业率卡片 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 hover:border-terminal-accent/50 transition-colors">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-terminal-dim cursor-help font-medium" title="城镇调查失业率">失业率</span>
            <span class="text-[10px] text-terminal-dim/70">{{ overview.unemployment?.period }}</span>
          </div>
          <div class="text-xl md:text-2xl font-bold" :class="getUnemploymentColor(overview.unemployment?.rate)">
            {{ formatNumber(overview.unemployment?.rate) }}<span class="text-sm ml-0.5">%</span>
          </div>
          <div class="text-[10px] md:text-xs text-terminal-dim mt-1">城镇调查</div>
          <div class="mt-2 flex items-center gap-1">
            <div class="flex-1 h-1 bg-terminal-bg/50 rounded-full overflow-hidden">
              <div class="h-full bg-warning/60 rounded-full" :style="{ width: Math.min((overview.unemployment?.rate || 0) * 10, 100) + '%' }"></div>
            </div>
            <span class="text-[10px] text-terminal-dim">{{ overview.unemployment?.rate >= 5.5 ? '⚠️' : '✓' }}</span>
          </div>
        </div>
      </div>

      <!-- 图表区域 - PC端3列，平板2列，移动端1列 -->
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 md:gap-4 px-3 md:px-4 pb-3">
        <!-- GDP趋势图 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 flex flex-col min-h-[280px] md:min-h-[320px]">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-bold text-terminal-accent">📈 GDP同比增长率</h3>
            <span class="text-[10px] text-terminal-dim/70">近20季度</span>
          </div>
          <div ref="gdpChart" class="flex-1 w-full h-[250px]"></div>
        </div>

        <!-- CPI趋势图 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 flex flex-col min-h-[280px] md:min-h-[320px]">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-bold text-terminal-accent">📊 CPI同比/环比</h3>
            <span class="text-[10px] text-terminal-dim/70">近24月</span>
          </div>
          <div ref="cpiChart" class="flex-1 w-full h-[250px]"></div>
        </div>

        <!-- PMI趋势图 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 flex flex-col min-h-[280px] md:min-h-[320px]">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-bold text-terminal-accent">📉 PMI制造业/非制造业</h3>
            <span class="text-[10px] text-terminal-dim/70">近24月</span>
          </div>
          <div ref="pmiChart" class="flex-1 w-full h-[250px]"></div>
        </div>

        <!-- PPI趋势图 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 flex flex-col min-h-[280px] md:min-h-[320px]">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-bold text-terminal-accent">📈 PPI同比</h3>
            <span class="text-[10px] text-terminal-dim/70">近24月</span>
          </div>
          <div ref="ppiChart" class="flex-1 w-full h-[250px]"></div>
        </div>

        <!-- M2趋势图 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 flex flex-col min-h-[280px] md:min-h-[320px]">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-bold text-terminal-accent">💰 M2货币供应量同比</h3>
            <span class="text-[10px] text-terminal-dim/70">近24月</span>
          </div>
          <div ref="m2Chart" class="flex-1 w-full h-[250px]"></div>
        </div>

        <!-- 社融趋势图 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 flex flex-col min-h-[280px] md:min-h-[320px]">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-bold text-terminal-accent">🏦 社会融资规模</h3>
            <span class="text-[10px] text-terminal-dim/70">近24月</span>
          </div>
          <div ref="socialFinancingChart" class="flex-1 w-full h-[250px]"></div>
        </div>

        <!-- 工业增加值趋势图 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 flex flex-col min-h-[280px] md:min-h-[320px]">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-bold text-terminal-accent">🏭 工业增加值同比</h3>
            <span class="text-[10px] text-terminal-dim/70">近24月</span>
          </div>
          <div ref="industrialProductionChart" class="flex-1 w-full h-[250px]"></div>
        </div>

        <!-- 失业率趋势图 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 flex flex-col min-h-[280px] md:min-h-[320px]">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-bold text-terminal-accent">👥 城镇调查失业率</h3>
            <span class="text-[10px] text-terminal-dim/70">近24月</span>
          </div>
          <div ref="unemploymentChart" class="flex-1 w-full h-[250px]"></div>
        </div>
      </div>

      <!-- 经济日历 -->
      <div class="px-3 md:px-4 pb-4">
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-bold text-terminal-accent">📅 近期数据发布</h3>
            <span class="text-[10px] text-terminal-dim/70">{{ calendar.length }}项</span>
          </div>
          <div v-if="calendar.length > 0" class="space-y-2">
            <div v-for="(item, index) in calendar" :key="index" 
                 class="flex items-center justify-between py-2 px-3 rounded-md hover:bg-terminal-bg/30 transition-colors"
                 :class="index < calendar.length - 1 ? 'border-b border-theme/10' : ''">
              <div class="flex items-center gap-3">
                <span class="text-[10px] px-2 py-0.5 rounded-full font-medium" 
                      :class="getStatusClass(item.status)">
                  {{ item.status === 'released' ? '已发布' : '待发布' }}
                </span>
                <span class="text-sm text-terminal-primary font-medium">{{ item.name }}</span>
              </div>
              <div class="flex items-center gap-3 md:gap-4">
                <span class="text-[10px] md:text-xs text-terminal-dim">{{ item.date }}</span>
                <span v-if="item.value !== null" class="text-sm font-mono font-bold" :class="getColorClass(item.value)">
                  {{ formatNumber(item.value) }}{{ item.unit }}
                </span>
              </div>
            </div>
          </div>
          <div v-else class="text-center py-8 text-terminal-dim text-sm">
            暂无数据发布计划
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { apiFetch } from '../utils/api.js'

const echarts = window.echarts

const loading = ref(false)
const overview = ref(null)
const calendar = ref([])
const lastUpdate = ref(null)

const gdpChart = ref(null)
const cpiChart = ref(null)
const pmiChart = ref(null)
const ppiChart = ref(null)
const m2Chart = ref(null)
const socialFinancingChart = ref(null)
const industrialProductionChart = ref(null)
const unemploymentChart = ref(null)

let gdpChartInstance = null
let cpiChartInstance = null
let pmiChartInstance = null
let ppiChartInstance = null
let m2ChartInstance = null
let socialFinancingChartInstance = null
let industrialProductionChartInstance = null
let unemploymentChartInstance = null

async function fetchAllData() {
  loading.value = true
  error.value = null

  try {
    const [
      overviewRes,
      calendarRes,
      gdpRes,
      cpiRes,
      pmiRes,
      ppiRes,
      m2Res,
      socialRes,
      industrialRes,
      unemploymentRes
    ] = await Promise.all([
      apiFetch('/api/v1/macro/overview', { timeoutMs: 30000 }).catch(e => { console.error('[Macro] Overview error:', e); return null }),
      apiFetch('/api/v1/macro/calendar', { timeoutMs: 30000 }).catch(e => { console.error('[Macro] Calendar error:', e); return null }),
      apiFetch('/api/v1/macro/gdp?limit=20', { timeoutMs: 30000 }).catch(e => { console.error('[Macro] GDP error:', e); return null }),
      apiFetch('/api/v1/macro/cpi?limit=24', { timeoutMs: 30000 }).catch(e => { console.error('[Macro] CPI error:', e); return null }),
      apiFetch('/api/v1/macro/pmi?limit=24', { timeoutMs: 30000 }).catch(e => { console.error('[Macro] PMI error:', e); return null }),
      apiFetch('/api/v1/macro/ppi?limit=24', { timeoutMs: 30000 }).catch(e => { console.error('[Macro] PPI error:', e); return null }),
      apiFetch('/api/v1/macro/m2?limit=24', { timeoutMs: 30000 }).catch(e => { console.error('[Macro] M2 error:', e); return null }),
      apiFetch('/api/v1/macro/social_financing?limit=24', { timeoutMs: 30000 }).catch(e => { console.error('[Macro] Social error:', e); return null }),
      apiFetch('/api/v1/macro/industrial_production?limit=24', { timeoutMs: 30000 }).catch(e => { console.error('[Macro] Industrial error:', e); return null }),
      apiFetch('/api/v1/macro/unemployment?limit=24', { timeoutMs: 30000 }).catch(e => { console.error('[Macro] Unemployment error:', e); return null })
    ])

    // Process results
    if (overviewRes?.overview) {
      overview.value = overviewRes.overview
      lastUpdate.value = overviewRes.last_update
    }
    if (calendarRes?.calendar) calendar.value = calendarRes.calendar
    if (gdpRes?.data) drawGDPChart(gdpRes.data)
    if (cpiRes?.data) drawCPIChart(cpiRes.data)
    if (pmiRes?.data) drawPMIChart(pmiRes.data)
    if (ppiRes?.data) drawPPIChart(ppiRes.data)
    if (m2Res?.data) drawM2Chart(m2Res.data)
    if (socialRes?.data) drawSocialFinancingChart(socialRes.data)
    if (industrialRes?.data) drawIndustrialProductionChart(industrialRes.data)
    if (unemploymentRes?.data) drawUnemploymentChart(unemploymentRes.data)

  } catch (e) {
    console.error('[Macro] Fetch all error:', e)
    error.value = '数据加载失败'
  } finally {
    loading.value = false
  }
}

function getChartColors() {
  return {
    primary: getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim() || '#0F52BA',
    text: getComputedStyle(document.documentElement).getPropertyValue('--chart-text').trim() || '#8B949E',
    up: getComputedStyle(document.documentElement).getPropertyValue('--color-up').trim() || '#FF6B6B',
    down: getComputedStyle(document.documentElement).getPropertyValue('--color-down').trim() || '#51CF66',
    warning: getComputedStyle(document.documentElement).getPropertyValue('--color-warning').trim() || '#FF7D00',
    success: getComputedStyle(document.documentElement).getPropertyValue('--color-success').trim() || '#51CF66',
  }
}

function drawGDPChart(data) {
  if (!gdpChartInstance || !gdpChart.value) return
  
  const colors = getChartColors()
  const quarters = data.map(d => d.quarter)
  const yoyData = data.map(d => d.gdp_yoy)
  
  gdpChartInstance.setOption({
    tooltip: { 
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: colors.primary,
      textStyle: { color: '#E5E7EB', fontSize: 12 }
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: { 
      type: 'category', 
      data: quarters,
      axisLabel: { color: colors.text, fontSize: 10, rotate: 45 },
      axisLine: { lineStyle: { color: colors.text + '40' } }
    },
    yAxis: { 
      type: 'value',
      axisLabel: { color: colors.text, fontSize: 10, formatter: '{value}%' },
      axisLine: { lineStyle: { color: colors.text + '40' } },
      splitLine: { lineStyle: { color: colors.text + '20' } }
    },
    series: [{
      name: 'GDP同比',
      type: 'line',
      data: yoyData,
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { color: colors.primary, width: 3 },
      itemStyle: { color: colors.primary, borderWidth: 2 },
      areaStyle: { 
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: colors.primary + '60' },
            { offset: 1, color: colors.primary + '10' }
          ]
        }
      }
    }]
  })
}

function drawCPIChart(data) {
  if (!cpiChartInstance || !cpiChart.value) return
  
  const colors = getChartColors()
  const months = data.map(d => d.month)
  const yoyData = data.map(d => d.nation_yoy)
  const momData = data.map(d => d.nation_mom)
  
  cpiChartInstance.setOption({
    tooltip: { 
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: colors.primary,
      textStyle: { color: '#E5E7EB', fontSize: 12 }
    },
    legend: { 
      data: ['同比', '环比'], 
      textStyle: { color: colors.text, fontSize: 11 },
      top: 0,
      right: 0
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '15%', containLabel: true },
    xAxis: { 
      type: 'category', 
      data: months,
      axisLabel: { color: colors.text, fontSize: 10, rotate: 45 },
      axisLine: { lineStyle: { color: colors.text + '40' } }
    },
    yAxis: { 
      type: 'value',
      axisLabel: { color: colors.text, fontSize: 10, formatter: '{value}%' },
      axisLine: { lineStyle: { color: colors.text + '40' } },
      splitLine: { lineStyle: { color: colors.text + '20' } }
    },
    series: [
      {
        name: '同比',
        type: 'line',
        data: yoyData,
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { color: colors.up, width: 2 },
        itemStyle: { color: colors.up }
      },
      {
        name: '环比',
        type: 'line',
        data: momData,
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { color: colors.down, width: 2, type: 'dashed' },
        itemStyle: { color: colors.down }
      }
    ]
  })
}

function drawPMIChart(data) {
  if (!pmiChartInstance || !pmiChart.value) return
  
  const colors = getChartColors()
  const months = data.map(d => d.month)
  const manufacturingData = data.map(d => d.manufacturing_index)
  const nonManufacturingData = data.map(d => d.non_manufacturing_index)
  
  pmiChartInstance.setOption({
    tooltip: { 
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: colors.primary,
      textStyle: { color: '#E5E7EB', fontSize: 12 }
    },
    legend: { 
      data: ['制造业', '非制造业'], 
      textStyle: { color: colors.text, fontSize: 11 },
      top: 0,
      right: 0
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '15%', containLabel: true },
    xAxis: { 
      type: 'category', 
      data: months,
      axisLabel: { color: colors.text, fontSize: 10, rotate: 45 },
      axisLine: { lineStyle: { color: colors.text + '40' } }
    },
    yAxis: { 
      type: 'value',
      min: 45,
      max: 60,
      axisLabel: { color: colors.text, fontSize: 10 },
      axisLine: { lineStyle: { color: colors.text + '40' } },
      splitLine: { lineStyle: { color: colors.text + '20' } }
    },
    series: [
      {
        name: '制造业',
        type: 'line',
        data: manufacturingData,
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { color: colors.primary, width: 2 },
        itemStyle: { color: colors.primary },
        markLine: {
          data: [{ yAxis: 50, lineStyle: { color: colors.warning, type: 'dashed', width: 2 } }],
          label: { formatter: '荣枯线', color: colors.warning, fontSize: 10 }
        }
      },
      {
        name: '非制造业',
        type: 'line',
        data: nonManufacturingData,
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { color: colors.success, width: 2 },
        itemStyle: { color: colors.success }
      }
    ]
  })
}

function drawPPIChart(data) {
  if (!ppiChartInstance || !ppiChart.value) return
  
  const colors = getChartColors()
  const months = data.map(d => d.month)
  const yoyData = data.map(d => d.yoy)
  
  ppiChartInstance.setOption({
    tooltip: { 
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: colors.primary,
      textStyle: { color: '#E5E7EB', fontSize: 12 }
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: { 
      type: 'category', 
      data: months,
      axisLabel: { color: colors.text, fontSize: 10, rotate: 45 },
      axisLine: { lineStyle: { color: colors.text + '40' } }
    },
    yAxis: { 
      type: 'value',
      axisLabel: { color: colors.text, fontSize: 10, formatter: '{value}%' },
      axisLine: { lineStyle: { color: colors.text + '40' } },
      splitLine: { lineStyle: { color: colors.text + '20' } }
    },
    series: [{
      name: 'PPI同比',
      type: 'line',
      data: yoyData,
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      lineStyle: { color: colors.up, width: 2 },
      itemStyle: { color: colors.up },
      areaStyle: { 
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: colors.up + '40' },
            { offset: 1, color: colors.up + '10' }
          ]
        }
      }
    }]
  })
}

function drawM2Chart(data) {
  if (!m2ChartInstance || !m2Chart.value) return
  
  const colors = getChartColors()
  const months = data.map(d => d.month)
  const yoyData = data.map(d => d.m2_yoy)
  
  m2ChartInstance.setOption({
    tooltip: { 
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: colors.primary,
      textStyle: { color: '#E5E7EB', fontSize: 12 }
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: { 
      type: 'category', 
      data: months,
      axisLabel: { color: colors.text, fontSize: 10, rotate: 45 },
      axisLine: { lineStyle: { color: colors.text + '40' } }
    },
    yAxis: { 
      type: 'value',
      axisLabel: { color: colors.text, fontSize: 10, formatter: '{value}%' },
      axisLine: { lineStyle: { color: colors.text + '40' } },
      splitLine: { lineStyle: { color: colors.text + '20' } }
    },
    series: [{
      name: 'M2同比',
      type: 'line',
      data: yoyData,
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      lineStyle: { color: colors.primary, width: 2 },
      itemStyle: { color: colors.primary },
      areaStyle: { 
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: colors.primary + '40' },
            { offset: 1, color: colors.primary + '10' }
          ]
        }
      }
    }]
  })
}

function drawSocialFinancingChart(data) {
  if (!socialFinancingChartInstance || !socialFinancingChart.value) return
  
  const colors = getChartColors()
  const months = data.map(d => d.month)
  const totalData = data.map(d => d.total)
  
  socialFinancingChartInstance.setOption({
    tooltip: { 
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: colors.primary,
      textStyle: { color: '#E5E7EB', fontSize: 12 }
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: { 
      type: 'category', 
      data: months,
      axisLabel: { color: colors.text, fontSize: 10, rotate: 45 },
      axisLine: { lineStyle: { color: colors.text + '40' } }
    },
    yAxis: { 
      type: 'value',
      axisLabel: { color: colors.text, fontSize: 10 },
      axisLine: { lineStyle: { color: colors.text + '40' } },
      splitLine: { lineStyle: { color: colors.text + '20' } }
    },
    series: [{
      name: '社融增量',
      type: 'bar',
      data: totalData,
      itemStyle: { 
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: colors.up },
            { offset: 1, color: colors.up + '60' }
          ]
        },
        borderRadius: [4, 4, 0, 0]
      },
      barMaxWidth: 30
    }]
  })
}

function drawIndustrialProductionChart(data) {
  if (!industrialProductionChartInstance || !industrialProductionChart.value) return
  
  const colors = getChartColors()
  const months = data.map(d => d.month)
  const yoyData = data.map(d => d.yoy)
  
  industrialProductionChartInstance.setOption({
    tooltip: { 
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: colors.primary,
      textStyle: { color: '#E5E7EB', fontSize: 12 }
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: { 
      type: 'category', 
      data: months,
      axisLabel: { color: colors.text, fontSize: 10, rotate: 45 },
      axisLine: { lineStyle: { color: colors.text + '40' } }
    },
    yAxis: { 
      type: 'value',
      axisLabel: { color: colors.text, fontSize: 10, formatter: '{value}%' },
      axisLine: { lineStyle: { color: colors.text + '40' } },
      splitLine: { lineStyle: { color: colors.text + '20' } }
    },
    series: [{
      name: '工业增加值同比',
      type: 'line',
      data: yoyData,
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      lineStyle: { color: colors.success, width: 2 },
      itemStyle: { color: colors.success },
      areaStyle: { 
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: colors.success + '40' },
            { offset: 1, color: colors.success + '10' }
          ]
        }
      }
    }]
  })
}

function drawUnemploymentChart(data) {
  if (!unemploymentChartInstance || !unemploymentChart.value) return
  
  const colors = getChartColors()
  const months = data.map(d => d.month)
  const rateData = data.map(d => d.rate)
  
  unemploymentChartInstance.setOption({
    tooltip: { 
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: colors.primary,
      textStyle: { color: '#E5E7EB', fontSize: 12 }
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: { 
      type: 'category', 
      data: months,
      axisLabel: { color: colors.text, fontSize: 10, rotate: 45 },
      axisLine: { lineStyle: { color: colors.text + '40' } }
    },
    yAxis: { 
      type: 'value',
      axisLabel: { color: colors.text, fontSize: 10, formatter: '{value}%' },
      axisLine: { lineStyle: { color: colors.text + '40' } },
      splitLine: { lineStyle: { color: colors.text + '20' } }
    },
    series: [{
      name: '失业率',
      type: 'line',
      data: rateData,
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      lineStyle: { color: colors.warning, width: 2 },
      itemStyle: { color: colors.warning },
      areaStyle: { 
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: colors.warning + '40' },
            { offset: 1, color: colors.warning + '10' }
          ]
        }
      },
      markLine: {
        data: [{ yAxis: 5.5, lineStyle: { color: colors.up, type: 'dashed', width: 2 } }],
        label: { formatter: '警戒线', color: colors.up, fontSize: 10 }
      }
    }]
  })
}

async function refreshAll() {
  await fetchAllData()
}

function formatNumber(val) {
  if (val === null || val === undefined) return '--'
  return Number(val).toFixed(2)
}

function formatLargeNumber(val) {
  if (val === null || val === undefined) return '--'
  if (val >= 10000) {
    return (val / 10000).toFixed(2) + '万'
  }
  return Number(val).toFixed(2)
}

function formatTime(isoString) {
  if (!isoString) return ''
  const date = new Date(isoString)
  return date.toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function getColorClass(val) {
  if (val === null || val === undefined) return 'text-terminal-dim'
  return val >= 0 ? 'text-bullish' : 'text-bearish'
}

function getPMIColor(val) {
  if (val === null || val === undefined) return 'text-terminal-dim'
  return val >= 50 ? 'text-bullish' : 'text-bearish'
}

function getUnemploymentColor(val) {
  if (val === null || val === undefined) return 'text-terminal-dim'
  return val >= 5.5 ? 'text-bearish' : 'text-bullish'
}

function getStatusClass(status) {
  return status === 'released' 
    ? 'bg-success/20 text-success' 
    : 'bg-warning/20 text-warning'
}

let resizeTimer = null
function handleResize() {
  clearTimeout(resizeTimer)
  resizeTimer = setTimeout(() => {
    gdpChartInstance?.resize()
    cpiChartInstance?.resize()
    pmiChartInstance?.resize()
    ppiChartInstance?.resize()
    m2ChartInstance?.resize()
    socialFinancingChartInstance?.resize()
    industrialProductionChartInstance?.resize()
    unemploymentChartInstance?.resize()
  }, 150)
}

onMounted(async () => {
  await nextTick()
  
  const chartRefs = [
    { ref: gdpChart.value, name: 'GDP', instance: 'gdpChartInstance' },
    { ref: cpiChart.value, name: 'CPI', instance: 'cpiChartInstance' },
    { ref: pmiChart.value, name: 'PMI', instance: 'pmiChartInstance' },
    { ref: ppiChart.value, name: 'PPI', instance: 'ppiChartInstance' },
    { ref: m2Chart.value, name: 'M2', instance: 'm2ChartInstance' },
    { ref: socialFinancingChart.value, name: 'SocialFinancing', instance: 'socialFinancingChartInstance' },
    { ref: industrialProductionChart.value, name: 'IndustrialProduction', instance: 'industrialProductionChartInstance' },
    { ref: unemploymentChart.value, name: 'Unemployment', instance: 'unemploymentChartInstance' },
  ]
  
  chartRefs.forEach(({ ref, name }) => {
    if (ref) {
      try {
        if (name === 'GDP') gdpChartInstance = echarts.init(ref)
        else if (name === 'CPI') cpiChartInstance = echarts.init(ref)
        else if (name === 'PMI') pmiChartInstance = echarts.init(ref)
        else if (name === 'PPI') ppiChartInstance = echarts.init(ref)
        else if (name === 'M2') m2ChartInstance = echarts.init(ref)
        else if (name === 'SocialFinancing') socialFinancingChartInstance = echarts.init(ref)
        else if (name === 'IndustrialProduction') industrialProductionChartInstance = echarts.init(ref)
        else if (name === 'Unemployment') unemploymentChartInstance = echarts.init(ref)
      } catch (e) {
        console.warn(`[MacroDashboard] Failed to init ${name} chart:`, e.message)
      }
    }
  })
  
  await refreshAll()
  
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  clearTimeout(resizeTimer)
  window.removeEventListener('resize', handleResize)
  try { gdpChartInstance?.dispose() } catch (e) { console.warn('[MacroDashboard] GDP dispose error:', e.message) }
  try { cpiChartInstance?.dispose() } catch (e) { console.warn('[MacroDashboard] CPI dispose error:', e.message) }
  try { pmiChartInstance?.dispose() } catch (e) { console.warn('[MacroDashboard] PMI dispose error:', e.message) }
  try { ppiChartInstance?.dispose() } catch (e) { console.warn('[MacroDashboard] PPI dispose error:', e.message) }
  try { m2ChartInstance?.dispose() } catch (e) { console.warn('[MacroDashboard] M2 dispose error:', e.message) }
  try { socialFinancingChartInstance?.dispose() } catch (e) { console.warn('[MacroDashboard] SocialFinancing dispose error:', e.message) }
  try { industrialProductionChartInstance?.dispose() } catch (e) { console.warn('[MacroDashboard] IndustrialProduction dispose error:', e.message) }
  try { unemploymentChartInstance?.dispose() } catch (e) { console.warn('[MacroDashboard] Unemployment dispose error:', e.message) }
  gdpChartInstance = null
  cpiChartInstance = null
  pmiChartInstance = null
  ppiChartInstance = null
  m2ChartInstance = null
  socialFinancingChartInstance = null
  industrialProductionChartInstance = null
  unemploymentChartInstance = null
})
</script>

<style scoped>
.bg-terminal-panel {
  background: var(--bg-secondary, #1a1f2e);
}

.text-terminal-accent {
  color: var(--color-primary, #0F52BA);
}

.text-terminal-primary {
  color: var(--text-primary, #E5E7EB);
}

.text-terminal-dim {
  color: var(--text-secondary, #8B949E);
}

.text-bullish {
  color: var(--color-up, #FF6B6B);
}

.text-bearish {
  color: var(--color-down, #51CF66);
}

.text-success {
  color: var(--color-success, #51CF66);
}

.text-warning {
  color: var(--color-warning, #FF7D00);
}

.border-theme-secondary {
  border-color: var(--border-color, #2d3748);
}

.bg-terminal-bg {
  background: var(--bg-primary, #0f1419);
}

@media (max-width: 768px) {
  .text-xl {
    font-size: 1.25rem;
  }
  
  .text-2xl {
    font-size: 1.5rem;
  }
}
</style>
