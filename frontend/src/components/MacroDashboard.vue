<template>
  <div class="h-full flex flex-col bg-terminal-bg">
    <!-- 顶部标题栏 -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-theme-secondary">
      <div class="flex items-center gap-3">
        <span class="text-lg font-bold text-terminal-accent">📊 宏观经济</span>
        <span class="text-xs text-terminal-dim">中国宏观指标监控</span>
      </div>
      <div class="flex items-center gap-2">
        <span v-if="lastUpdate" class="text-xs text-terminal-dim">
          更新于 {{ formatTime(lastUpdate) }}
        </span>
        <button 
          class="px-3 py-1.5 rounded text-xs bg-terminal-accent/20 text-terminal-accent hover:bg-terminal-accent/30 transition"
          @click="refreshAll"
          :disabled="loading"
        >
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>
    </div>

    <!-- 核心指标卡片 -->
    <div v-if="overview" class="grid grid-cols-2 lg:grid-cols-4 gap-3 p-4">
      <!-- GDP卡片 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs text-terminal-dim">GDP</span>
          <span class="text-xs text-terminal-dim">{{ overview.gdp?.period }}</span>
        </div>
        <div class="text-2xl font-bold text-terminal-primary">
          {{ formatNumber(overview.gdp?.yoy) }}<span class="text-sm">%</span>
        </div>
        <div class="text-xs text-terminal-dim mt-1">同比增长</div>
      </div>

      <!-- CPI卡片 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs text-terminal-dim">CPI</span>
          <span class="text-xs text-terminal-dim">{{ overview.cpi?.period }}</span>
        </div>
        <div class="text-2xl font-bold" :class="getColorClass(overview.cpi?.yoy)">
          {{ formatNumber(overview.cpi?.yoy) }}<span class="text-sm">%</span>
        </div>
        <div class="text-xs text-terminal-dim mt-1">同比</div>
      </div>

      <!-- PPI卡片 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs text-terminal-dim">PPI</span>
          <span class="text-xs text-terminal-dim">{{ overview.ppi?.period }}</span>
        </div>
        <div class="text-2xl font-bold" :class="getColorClass(overview.ppi?.yoy)">
          {{ formatNumber(overview.ppi?.yoy) }}<span class="text-sm">%</span>
        </div>
        <div class="text-xs text-terminal-dim mt-1">同比</div>
      </div>

      <!-- PMI卡片 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs text-terminal-dim">PMI</span>
          <span class="text-xs text-terminal-dim">{{ overview.pmi?.period }}</span>
        </div>
        <div class="text-2xl font-bold" :class="getPMIColor(overview.pmi?.manufacturing)">
          {{ formatNumber(overview.pmi?.manufacturing) }}
        </div>
        <div class="text-xs text-terminal-dim mt-1">制造业</div>
      </div>

      <!-- M2卡片 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs text-terminal-dim">M2</span>
          <span class="text-xs text-terminal-dim">{{ overview.m2?.period }}</span>
        </div>
        <div class="text-2xl font-bold text-terminal-primary">
          {{ formatNumber(overview.m2?.yoy) }}<span class="text-sm">%</span>
        </div>
        <div class="text-xs text-terminal-dim mt-1">同比</div>
      </div>

      <!-- 社融卡片 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs text-terminal-dim">社融</span>
          <span class="text-xs text-terminal-dim">{{ overview.social_financing?.period }}</span>
        </div>
        <div class="text-2xl font-bold" :class="getColorClass(overview.social_financing?.yoy)">
          {{ formatNumber(overview.social_financing?.total) }}
        </div>
        <div class="text-xs text-terminal-dim mt-1">亿元</div>
      </div>

      <!-- 工业增加值卡片 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs text-terminal-dim">工业增加值</span>
          <span class="text-xs text-terminal-dim">{{ overview.industrial_production?.period }}</span>
        </div>
        <div class="text-2xl font-bold" :class="getColorClass(overview.industrial_production?.yoy)">
          {{ formatNumber(overview.industrial_production?.yoy) }}<span class="text-sm">%</span>
        </div>
        <div class="text-xs text-terminal-dim mt-1">同比</div>
      </div>

      <!-- 失业率卡片 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs text-terminal-dim">失业率</span>
          <span class="text-xs text-terminal-dim">{{ overview.unemployment?.period }}</span>
        </div>
        <div class="text-2xl font-bold" :class="getUnemploymentColor(overview.unemployment?.rate)">
          {{ formatNumber(overview.unemployment?.rate) }}<span class="text-sm">%</span>
        </div>
        <div class="text-xs text-terminal-dim mt-1">城镇调查</div>
      </div>
    </div>

    <!-- 图表区域 -->
    <div class="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-4 px-4 pb-4 min-h-0 overflow-y-auto">
      <!-- GDP趋势图 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4 flex flex-col">
        <h3 class="text-sm font-bold text-terminal-accent mb-3">GDP同比增长率</h3>
        <div ref="gdpChart" class="flex-1 min-h-[200px]"></div>
      </div>

      <!-- CPI趋势图 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4 flex flex-col">
        <h3 class="text-sm font-bold text-terminal-accent mb-3">CPI同比/环比</h3>
        <div ref="cpiChart" class="flex-1 min-h-[200px]"></div>
      </div>

      <!-- PMI趋势图 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4 flex flex-col">
        <h3 class="text-sm font-bold text-terminal-accent mb-3">PMI制造业/非制造业</h3>
        <div ref="pmiChart" class="flex-1 min-h-[200px]"></div>
      </div>

      <!-- PPI趋势图 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4 flex flex-col">
        <h3 class="text-sm font-bold text-terminal-accent mb-3">PPI同比</h3>
        <div ref="ppiChart" class="flex-1 min-h-[200px]"></div>
      </div>

      <!-- M2趋势图 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4 flex flex-col">
        <h3 class="text-sm font-bold text-terminal-accent mb-3">M2货币供应量同比</h3>
        <div ref="m2Chart" class="flex-1 min-h-[200px]"></div>
      </div>

      <!-- 社融趋势图 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4 flex flex-col">
        <h3 class="text-sm font-bold text-terminal-accent mb-3">社会融资规模</h3>
        <div ref="socialFinancingChart" class="flex-1 min-h-[200px]"></div>
      </div>

      <!-- 工业增加值趋势图 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4 flex flex-col">
        <h3 class="text-sm font-bold text-terminal-accent mb-3">工业增加值同比</h3>
        <div ref="industrialProductionChart" class="flex-1 min-h-[200px]"></div>
      </div>

      <!-- 失业率趋势图 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4 flex flex-col">
        <h3 class="text-sm font-bold text-terminal-accent mb-3">城镇调查失业率</h3>
        <div ref="unemploymentChart" class="flex-1 min-h-[200px]"></div>
      </div>
    </div>

    <!-- 经济日历 -->
    <div class="px-4 pb-4">
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
        <h3 class="text-sm font-bold text-terminal-accent mb-3">📅 近期数据发布</h3>
        <div class="space-y-2">
          <div v-for="(item, index) in calendar" :key="index" class="flex items-center justify-between py-2 border-b border-theme/10 last:border-0">
            <div class="flex items-center gap-3">
              <span class="text-xs px-2 py-0.5 rounded" :class="getStatusClass(item.status)">
                {{ item.status === 'released' ? '已发布' : '待发布' }}
              </span>
              <span class="text-sm text-terminal-primary">{{ item.name }}</span>
            </div>
            <div class="flex items-center gap-4">
              <span class="text-xs text-terminal-dim">{{ item.date }}</span>
              <span v-if="item.value !== null" class="text-sm font-mono" :class="getColorClass(item.value)">
                {{ formatNumber(item.value) }}{{ item.unit }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { apiFetch } from '../utils/api.js'

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

// 获取概览数据
async function fetchOverview() {
  try {
    const data = await apiFetch('/api/v1/macro/overview')
    if (data?.overview) {
      overview.value = data.overview
      lastUpdate.value = data.last_update
    }
  } catch (e) {
    console.error('[Macro] Overview fetch error:', e)
  }
}

// 获取经济日历
async function fetchCalendar() {
  try {
    const data = await apiFetch('/api/v1/macro/calendar')
    if (data?.calendar) {
      calendar.value = data.calendar
    }
  } catch (e) {
    console.error('[Macro] Calendar fetch error:', e)
  }
}

// 获取GDP数据并绘制图表
async function fetchGDP() {
  try {
    const data = await apiFetch('/api/v1/macro/gdp?limit=20')
    if (data?.data?.data) {
      drawGDPChart(data.data.data)
    }
  } catch (e) {
    console.error('[Macro] GDP fetch error:', e)
  }
}

// 获取CPI数据并绘制图表
async function fetchCPI() {
  try {
    const data = await apiFetch('/api/v1/macro/cpi?limit=24')
    if (data?.data?.data) {
      drawCPIChart(data.data.data)
    }
  } catch (e) {
    console.error('[Macro] CPI fetch error:', e)
  }
}

// 获取PMI数据并绘制图表
async function fetchPMI() {
  try {
    const data = await apiFetch('/api/v1/macro/pmi?limit=24')
    if (data?.data?.data) {
      drawPMIChart(data.data.data)
    }
  } catch (e) {
    console.error('[Macro] PMI fetch error:', e)
  }
}

// 获取PPI数据并绘制图表
async function fetchPPI() {
  try {
    const data = await apiFetch('/api/v1/macro/ppi?limit=24')
    if (data?.data?.data) {
      drawPPIChart(data.data.data)
    }
  } catch (e) {
    console.error('[Macro] PPI fetch error:', e)
  }
}

// 获取M2数据并绘制图表
async function fetchM2() {
  try {
    const data = await apiFetch('/api/v1/macro/m2?limit=24')
    if (data?.data?.data) {
      drawM2Chart(data.data.data)
    }
  } catch (e) {
    console.error('[Macro] M2 fetch error:', e)
  }
}

// 获取社融数据并绘制图表
async function fetchSocialFinancing() {
  try {
    const data = await apiFetch('/api/v1/macro/social_financing?limit=24')
    if (data?.data?.data) {
      drawSocialFinancingChart(data.data.data)
    }
  } catch (e) {
    console.error('[Macro] Social financing fetch error:', e)
  }
}

// 获取工业增加值数据并绘制图表
async function fetchIndustrialProduction() {
  try {
    const data = await apiFetch('/api/v1/macro/industrial_production?limit=24')
    if (data?.data?.data) {
      drawIndustrialProductionChart(data.data.data)
    }
  } catch (e) {
    console.error('[Macro] Industrial production fetch error:', e)
  }
}

// 获取失业率数据并绘制图表
async function fetchUnemployment() {
  try {
    const data = await apiFetch('/api/v1/macro/unemployment?limit=24')
    if (data?.data?.data) {
      drawUnemploymentChart(data.data.data)
    }
  } catch (e) {
    console.error('[Macro] Unemployment fetch error:', e)
  }
}

// 绘制GDP图表
function drawGDPChart(data) {
  if (!gdpChartInstance || !gdpChart.value) return
  
  const quarters = data.map(d => d.quarter)
  const yoyData = data.map(d => d.gdp_yoy)
  
  const primaryColor = getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim() || '#2E7DFF'
  const chartTextColor = getComputedStyle(document.documentElement).getPropertyValue('--chart-text').trim() || '#8B949E'
  
  gdpChartInstance.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: { 
      type: 'category', 
      data: quarters,
      axisLabel: { color: chartTextColor, fontSize: 10 }
    },
    yAxis: { 
      type: 'value',
      axisLabel: { color: chartTextColor, fontSize: 10, formatter: '{value}%' }
    },
    series: [{
      name: 'GDP同比',
      type: 'line',
      data: yoyData,
      smooth: true,
      lineStyle: { color: primaryColor, width: 2 },
      itemStyle: { color: primaryColor },
      areaStyle: { 
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: primaryColor + '4D' },  // 30% opacity
            { offset: 1, color: primaryColor + '0D' }   // 5% opacity
          ]
        }
      }
    }]
  })
}

// 绘制CPI图表
function drawCPIChart(data) {
  if (!cpiChartInstance || !cpiChart.value) return
  
  const months = data.map(d => d.month)
  const yoyData = data.map(d => d.nation_yoy)
  const momData = data.map(d => d.nation_mom)
  
  const chartTextColor = getComputedStyle(document.documentElement).getPropertyValue('--chart-text').trim() || '#8B949E'
  const upColor = getComputedStyle(document.documentElement).getPropertyValue('--color-up').trim() || '#FF6B6B'
  const downColor = getComputedStyle(document.documentElement).getPropertyValue('--color-down').trim() || '#51CF66'
  
  cpiChartInstance.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['同比', '环比'], textStyle: { color: chartTextColor, fontSize: 10 } },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '15%', containLabel: true },
    xAxis: { 
      type: 'category', 
      data: months,
      axisLabel: { color: chartTextColor, fontSize: 10 }
    },
    yAxis: { 
      type: 'value',
      axisLabel: { color: chartTextColor, fontSize: 10, formatter: '{value}%' }
    },
    series: [
      {
        name: '同比',
        type: 'line',
        data: yoyData,
        smooth: true,
        lineStyle: { color: upColor, width: 2 },
        itemStyle: { color: upColor }
      },
      {
        name: '环比',
        type: 'line',
        data: momData,
        smooth: true,
        lineStyle: { color: downColor, width: 2 },
        itemStyle: { color: downColor }
      }
    ]
  })
}

// 绘制PMI图表
function drawPMIChart(data) {
  if (!pmiChartInstance || !pmiChart.value) return
  
  const months = data.map(d => d.month)
  const manufacturingData = data.map(d => d.manufacturing_index)
  const nonManufacturingData = data.map(d => d.non_manufacturing_index)
  
  const chartTextColor = getComputedStyle(document.documentElement).getPropertyValue('--chart-text').trim() || '#8B949E'
  const primaryColor = getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim() || '#2E7DFF'
  const warningColor = getComputedStyle(document.documentElement).getPropertyValue('--color-warning').trim() || '#FF7D00'
  const successColor = getComputedStyle(document.documentElement).getPropertyValue('--color-success').trim() || '#51CF66'
  
  pmiChartInstance.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['制造业', '非制造业'], textStyle: { color: chartTextColor, fontSize: 10 } },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '15%', containLabel: true },
    xAxis: { 
      type: 'category', 
      data: months,
      axisLabel: { color: chartTextColor, fontSize: 10 }
    },
    yAxis: { 
      type: 'value',
      min: 45,
      max: 60,
      axisLabel: { color: chartTextColor, fontSize: 10 }
    },
    series: [
      {
        name: '制造业',
        type: 'line',
        data: manufacturingData,
        smooth: true,
        lineStyle: { color: primaryColor, width: 2 },
        itemStyle: { color: primaryColor },
        markLine: {
          data: [{ yAxis: 50, lineStyle: { color: warningColor, type: 'dashed' } }],
          label: { formatter: '荣枯线', color: warningColor, fontSize: 10 }
        }
      },
      {
        name: '非制造业',
        type: 'line',
        data: nonManufacturingData,
        smooth: true,
        lineStyle: { color: successColor, width: 2 },
        itemStyle: { color: successColor }
      }
    ]
  })
}

// 绘制PPI图表
function drawPPIChart(data) {
  if (!ppiChartInstance || !ppiChart.value) return
  
  const months = data.map(d => d.month)
  const yoyData = data.map(d => d.yoy)
  
  const chartTextColor = getComputedStyle(document.documentElement).getPropertyValue('--chart-text').trim() || '#8B949E'
  const upColor = getComputedStyle(document.documentElement).getPropertyValue('--color-up').trim() || '#FF6B6B'
  
  ppiChartInstance.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: { 
      type: 'category', 
      data: months,
      axisLabel: { color: chartTextColor, fontSize: 10 }
    },
    yAxis: { 
      type: 'value',
      axisLabel: { color: chartTextColor, fontSize: 10, formatter: '{value}%' }
    },
    series: [{
      name: 'PPI同比',
      type: 'line',
      data: yoyData,
      smooth: true,
      lineStyle: { color: upColor, width: 2 },
      itemStyle: { color: upColor },
      areaStyle: { 
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: upColor + '4D' },  // 30% opacity
            { offset: 1, color: upColor + '0D' }   // 5% opacity
          ]
        }
      }
    }]
  })
}

// 绘制M2图表
function drawM2Chart(data) {
  if (!m2ChartInstance || !m2Chart.value) return
  
  const months = data.map(d => d.month)
  const yoyData = data.map(d => d.m2_yoy)
  
  const chartTextColor = getComputedStyle(document.documentElement).getPropertyValue('--chart-text').trim() || '#8B949E'
  const primaryColor = getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim() || '#2E7DFF'
  
  m2ChartInstance.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: { 
      type: 'category', 
      data: months,
      axisLabel: { color: chartTextColor, fontSize: 10 }
    },
    yAxis: { 
      type: 'value',
      axisLabel: { color: chartTextColor, fontSize: 10, formatter: '{value}%' }
    },
    series: [{
      name: 'M2同比',
      type: 'line',
      data: yoyData,
      smooth: true,
      lineStyle: { color: primaryColor, width: 2 },
      itemStyle: { color: primaryColor },
      areaStyle: { 
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: primaryColor + '4D' },
            { offset: 1, color: primaryColor + '0D' }
          ]
        }
      }
    }]
  })
}

// 绘制社融图表
function drawSocialFinancingChart(data) {
  if (!socialFinancingChartInstance || !socialFinancingChart.value) return
  
  const months = data.map(d => d.month)
  const totalData = data.map(d => d.total)
  
  const chartTextColor = getComputedStyle(document.documentElement).getPropertyValue('--chart-text').trim() || '#8B949E'
  const upColor = getComputedStyle(document.documentElement).getPropertyValue('--color-up').trim() || '#FF6B6B'
  
  socialFinancingChartInstance.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: { 
      type: 'category', 
      data: months,
      axisLabel: { color: chartTextColor, fontSize: 10 }
    },
    yAxis: { 
      type: 'value',
      axisLabel: { color: chartTextColor, fontSize: 10 }
    },
    series: [{
      name: '社融增量',
      type: 'bar',
      data: totalData,
      itemStyle: { color: upColor }
    }]
  })
}

// 绘制工业增加值图表
function drawIndustrialProductionChart(data) {
  if (!industrialProductionChartInstance || !industrialProductionChart.value) return
  
  const months = data.map(d => d.month)
  const yoyData = data.map(d => d.yoy)
  
  const chartTextColor = getComputedStyle(document.documentElement).getPropertyValue('--chart-text').trim() || '#8B949E'
  const successColor = getComputedStyle(document.documentElement).getPropertyValue('--color-success').trim() || '#51CF66'
  
  industrialProductionChartInstance.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: { 
      type: 'category', 
      data: months,
      axisLabel: { color: chartTextColor, fontSize: 10 }
    },
    yAxis: { 
      type: 'value',
      axisLabel: { color: chartTextColor, fontSize: 10, formatter: '{value}%' }
    },
    series: [{
      name: '工业增加值同比',
      type: 'line',
      data: yoyData,
      smooth: true,
      lineStyle: { color: successColor, width: 2 },
      itemStyle: { color: successColor },
      areaStyle: { 
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: successColor + '4D' },
            { offset: 1, color: successColor + '0D' }
          ]
        }
      }
    }]
  })
}

// 绘制失业率图表
function drawUnemploymentChart(data) {
  if (!unemploymentChartInstance || !unemploymentChart.value) return
  
  const months = data.map(d => d.month)
  const rateData = data.map(d => d.rate)
  
  const chartTextColor = getComputedStyle(document.documentElement).getPropertyValue('--chart-text').trim() || '#8B949E'
  const warningColor = getComputedStyle(document.documentElement).getPropertyValue('--color-warning').trim() || '#FF7D00'
  
  unemploymentChartInstance.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: { 
      type: 'category', 
      data: months,
      axisLabel: { color: chartTextColor, fontSize: 10 }
    },
    yAxis: { 
      type: 'value',
      min: 3,
      max: 7,
      axisLabel: { color: chartTextColor, fontSize: 10, formatter: '{value}%' }
    },
    series: [{
      name: '失业率',
      type: 'line',
      data: rateData,
      smooth: true,
      lineStyle: { color: warningColor, width: 2 },
      itemStyle: { color: warningColor },
      areaStyle: { 
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: warningColor + '4D' },
            { offset: 1, color: warningColor + '0D' }
          ]
        }
      }
    }]
  })
}

// 刷新所有数据
async function refreshAll() {
  loading.value = true
  await Promise.all([
    fetchOverview(),
    fetchCalendar(),
    fetchGDP(),
    fetchCPI(),
    fetchPMI(),
    fetchPPI(),
    fetchM2(),
    fetchSocialFinancing(),
    fetchIndustrialProduction(),
    fetchUnemployment()
  ])
  loading.value = false
}

// 工具函数
function formatNumber(val) {
  if (val === null || val === undefined) return '--'
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
    ? 'bg-[var(--color-success-bg)] text-[var(--color-success)]' 
    : 'bg-[var(--color-warning-bg)] text-[var(--color-warning)]'
}

// 初始化图表
onMounted(async () => {
  await nextTick()
  
  if (gdpChart.value) {
    gdpChartInstance = echarts.init(gdpChart.value)
  }
  if (cpiChart.value) {
    cpiChartInstance = echarts.init(cpiChart.value)
  }
  if (pmiChart.value) {
    pmiChartInstance = echarts.init(pmiChart.value)
  }
  if (ppiChart.value) {
    ppiChartInstance = echarts.init(ppiChart.value)
  }
  if (m2Chart.value) {
    m2ChartInstance = echarts.init(m2Chart.value)
  }
  if (socialFinancingChart.value) {
    socialFinancingChartInstance = echarts.init(socialFinancingChart.value)
  }
  if (industrialProductionChart.value) {
    industrialProductionChartInstance = echarts.init(industrialProductionChart.value)
  }
  if (unemploymentChart.value) {
    unemploymentChartInstance = echarts.init(unemploymentChart.value)
  }
  
  await refreshAll()
  
  // 窗口大小改变时重绘图表
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  gdpChartInstance?.dispose()
  cpiChartInstance?.dispose()
  pmiChartInstance?.dispose()
  ppiChartInstance?.dispose()
  m2ChartInstance?.dispose()
  socialFinancingChartInstance?.dispose()
  industrialProductionChartInstance?.dispose()
  unemploymentChartInstance?.dispose()
})

function handleResize() {
  gdpChartInstance?.resize()
  cpiChartInstance?.resize()
  pmiChartInstance?.resize()
  ppiChartInstance?.resize()
  m2ChartInstance?.resize()
  socialFinancingChartInstance?.resize()
  industrialProductionChartInstance?.resize()
  unemploymentChartInstance?.resize()
}
</script>