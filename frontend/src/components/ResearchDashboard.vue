<template>
  <div class="h-full flex flex-col bg-terminal-bg overflow-hidden" role="region" aria-label="研报平台">
    <div class="flex-shrink-0 flex flex-col sm:flex-row items-start sm:items-center justify-between px-4 py-3 gap-3 border-b border-theme-secondary">
      <div class="flex items-center gap-3">
        <span class="text-lg font-bold text-terminal-accent" role="heading" aria-level="2">📄 研报平台</span>
        <span class="text-xs text-terminal-dim hidden sm:inline">券商研报查询</span>
      </div>
      <div class="flex items-center gap-2 w-full sm:w-auto">
        <input
          v-model="symbol"
          type="text"
          placeholder="股票代码 (如 600519)"
          class="flex-1 sm:w-32 px-3 py-2 text-xs bg-terminal-panel border border-theme-secondary rounded-sm text-terminal-primary placeholder-terminal-dim focus:outline-none focus:border-terminal-accent"
          style="min-height: 44px;"
          aria-label="股票代码输入"
          @keyup.enter="fetchData"
        />
        <button
          class="px-4 py-2 rounded-sm text-xs bg-terminal-accent/20 text-terminal-accent hover:bg-terminal-accent/30 transition disabled:opacity-50"
          style="min-width: 44px; min-height: 44px;"
          @click="fetchData"
          :disabled="loading || !symbol"
          aria-label="查询研报"
          aria-busy="loading"
        >
          {{ loading ? '...' : '查询' }}
        </button>
      </div>
    </div>

    <!-- 筛选工具栏 -->
    <div v-if="symbol" class="flex-shrink-0 flex flex-wrap items-center gap-2 sm:gap-3 px-4 py-2 border-b border-theme-secondary bg-terminal-panel/50">
      <div class="flex items-center gap-2 w-full sm:w-auto">
        <input
          v-model="keyword"
          type="text"
          placeholder="关键词搜索"
          class="flex-1 sm:w-48 px-3 py-2 text-xs bg-terminal-bg border border-theme-secondary rounded-sm text-terminal-primary placeholder-terminal-dim focus:outline-none focus:border-terminal-accent"
          style="min-height: 44px;"
          @keyup.enter="fetchData"
        />
      </div>
      <div class="flex items-center gap-2 w-full sm:w-auto">
        <select
          v-model="selectedInstitution"
          class="flex-1 sm:flex-none px-3 py-2 text-xs bg-terminal-bg border border-theme-secondary rounded-sm text-terminal-primary focus:outline-none focus:border-terminal-accent"
          style="min-height: 44px; min-width: 120px;"
        >
          <option value="">全部机构</option>
          <option v-for="inst in institutions" :key="inst" :value="inst">{{ inst }}</option>
        </select>
      </div>
      <button
        class="px-4 py-2 rounded-sm text-xs border border-theme-secondary text-terminal-dim hover:bg-terminal-hover hover:text-terminal-primary transition disabled:opacity-50"
        style="min-width: 44px; min-height: 44px;"
        @click="fetchData"
        :disabled="loading"
        title="刷新数据"
      >
        🔄 刷新
      </button>
    </div>

    <div class="flex-1 overflow-y-auto">
      <div v-if="loading && !reports" class="p-4 space-y-4">
        <div class="grid grid-cols-2 gap-4">
          <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4 animate-pulse">
            <div class="h-4 w-20 bg-terminal-bg/50 rounded mb-2"></div>
            <div class="h-32 w-full bg-terminal-bg/50 rounded"></div>
          </div>
          <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4 animate-pulse">
            <div class="h-4 w-20 bg-terminal-bg/50 rounded mb-2"></div>
            <div class="h-32 w-full bg-terminal-bg/50 rounded"></div>
          </div>
        </div>
      </div>

      <div v-else-if="!symbol" class="flex flex-col items-center justify-center h-full text-terminal-dim">
        <span class="text-4xl mb-4">📄</span>
        <p class="text-sm">请输入股票代码查询研报</p>
        <p class="text-xs mt-2">例如: 600519 (贵州茅台)</p>
      </div>

      <div v-else-if="error" class="flex flex-col items-center justify-center h-full text-terminal-dim">
        <span class="text-4xl mb-4">⚠️</span>
        <p class="text-sm">{{ error }}</p>
        <button @click="fetchData" class="mt-4 px-4 py-2 rounded-sm text-xs bg-terminal-accent/20 text-terminal-accent hover:bg-terminal-accent/30">
          重试
        </button>
      </div>

      <div v-else class="p-3 md:p-4 space-y-4">
        <div v-if="isFallback && !cacheReady" class="bg-terminal-panel rounded-lg border border-theme-secondary p-4 text-center">
          <span class="text-2xl animate-pulse">⏳</span>
          <p class="text-sm text-terminal-dim mt-2">正在从数据源获取研报数据，首次加载约需 60 秒...</p>
          <p class="text-xs text-terminal-dim mt-1">后续访问将从缓存快速响应</p>
        </div>
        
        <div v-if="statistics" class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
            <h3 class="text-sm font-medium text-terminal-primary mb-3">机构分布</h3>
            <div ref="institutionChartRef" class="h-40 sm:h-48"></div>
          </div>
          <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
            <h3 class="text-sm font-medium text-terminal-primary mb-3">评级分布</h3>
            <div ref="ratingChartRef" class="h-40 sm:h-48"></div>
          </div>
        </div>

        <div v-if="reports && reports.items?.length > 0" class="bg-terminal-panel rounded-lg border border-theme-secondary">
          <div class="px-4 py-3 border-b border-theme-secondary flex items-center justify-between">
            <h3 class="text-sm font-medium text-terminal-primary">研报列表</h3>
            <span class="text-xs text-terminal-dim">共 {{ reports.total }} 条</span>
          </div>
          
          <!-- Desktop Table View -->
          <div class="hidden md:block overflow-x-auto">
            <table class="w-full text-xs">
              <thead class="bg-terminal-bg/50">
                <tr>
                  <th @click="sortBy('title')" class="px-4 py-2 text-left text-terminal-dim font-medium cursor-pointer hover:text-terminal-primary transition select-none">
                    标题 <span v-if="sortField === 'title'" class="text-terminal-accent">{{ sortOrder === 'asc' ? '↑' : '↓' }}</span>
                  </th>
                  <th @click="sortBy('institution')" class="px-4 py-2 text-left text-terminal-dim font-medium w-24 cursor-pointer hover:text-terminal-primary transition select-none">
                    机构 <span v-if="sortField === 'institution'" class="text-terminal-accent">{{ sortOrder === 'asc' ? '↑' : '↓' }}</span>
                  </th>
                  <th @click="sortBy('date')" class="px-4 py-2 text-left text-terminal-dim font-medium w-20 cursor-pointer hover:text-terminal-primary transition select-none">
                    日期 <span v-if="sortField === 'date'" class="text-terminal-accent">{{ sortOrder === 'asc' ? '↑' : '↓' }}</span>
                  </th>
                  <th @click="sortBy('rating')" class="px-4 py-2 text-left text-terminal-dim font-medium w-16 cursor-pointer hover:text-terminal-primary transition select-none">
                    评级 <span v-if="sortField === 'rating'" class="text-terminal-accent">{{ sortOrder === 'asc' ? '↑' : '↓' }}</span>
                  </th>
                  <th class="px-4 py-2 text-left text-terminal-dim font-medium w-16">链接</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(item, idx) in sortedReports"
                  :key="idx"
                  class="border-t border-theme-secondary/50 hover:bg-terminal-hover/30 cursor-pointer"
                  @click="showReportDetail(item)"
                >
                  <td class="px-4 py-2 text-terminal-primary truncate max-w-xs">{{ item.title || '-' }}</td>
                  <td class="px-4 py-2 text-terminal-dim">{{ item.institution || '-' }}</td>
                  <td class="px-4 py-2 text-terminal-dim">{{ item.date || '-' }}</td>
                  <td class="px-4 py-2">
                    <span v-if="item.rating" class="px-2 py-0.5 rounded-sm text-[10px]" :class="getRatingClass(item.rating)">
                      {{ item.rating }}
                    </span>
                    <span v-else class="text-terminal-dim">-</span>
                  </td>
                  <td class="px-4 py-2">
                    <a v-if="item.url" :href="getPdfProxyUrl(item.url)" target="_blank" class="text-terminal-accent hover:underline" @click.stop>PDF</a>
                    <span v-else class="text-terminal-dim">-</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          
          <!-- Mobile Card View -->
          <div class="md:hidden space-y-2 p-3">
            <div
              v-for="(item, idx) in sortedReports"
              :key="idx"
              class="bg-terminal-bg rounded-lg border border-theme-secondary p-3 cursor-pointer hover:bg-terminal-hover/30"
              @click="showReportDetail(item)"
            >
              <div class="flex justify-between items-start gap-2 mb-2">
                <span class="text-sm text-terminal-primary line-clamp-2 flex-1">{{ item.title || '-' }}</span>
                <a v-if="item.url" :href="getPdfProxyUrl(item.url)" target="_blank" class="text-terminal-accent hover:underline text-xs flex-shrink-0 px-2 py-1 bg-terminal-accent/10 rounded" @click.stop>PDF</a>
              </div>
              <div class="flex flex-wrap items-center gap-2 text-xs">
                <span class="text-terminal-dim">{{ item.institution || '-' }}</span>
                <span class="text-terminal-dim">•</span>
                <span class="text-terminal-dim">{{ item.date || '-' }}</span>
                <span v-if="item.rating" class="px-2 py-0.5 rounded-sm" :class="getRatingClass(item.rating)">
                  {{ item.rating }}
                </span>
              </div>
            </div>
          </div>
          
          <div v-if="reports.total > pageSize" class="px-4 py-3 border-t border-theme-secondary flex items-center justify-between">
            <button
              @click="goToPage(page - 1)"
              :disabled="page <= 1 || loading"
              class="px-4 py-2 rounded-sm text-xs border border-theme-secondary text-terminal-dim hover:bg-terminal-hover disabled:opacity-50 disabled:cursor-not-allowed"
              style="min-width: 44px; min-height: 44px;"
            >
              上一页
            </button>
            <span class="text-xs text-terminal-dim">第 {{ page }} 页 / 共 {{ Math.ceil(reports.total / pageSize) }} 页</span>
            <button
              @click="goToPage(page + 1)"
              :disabled="page >= Math.ceil(reports.total / pageSize) || loading"
              class="px-4 py-2 rounded-sm text-xs border border-theme-secondary text-terminal-dim hover:bg-terminal-hover disabled:opacity-50 disabled:cursor-not-allowed"
              style="min-width: 44px; min-height: 44px;"
            >
              下一页
            </button>
          </div>
        </div>

        <div v-else-if="reports && reports.total === 0" class="flex flex-col items-center justify-center py-12 text-terminal-dim">
          <span class="text-3xl mb-3">📭</span>
          <p class="text-sm">暂无研报数据</p>
        </div>
      </div>
    </div>

    <!-- 研报详情弹窗 -->
    <Teleport to="body">
      <div v-if="showDetailModal" class="fixed inset-0 z-50 flex items-center justify-center" @click.self="closeDetailModal">
        <div class="absolute inset-0 bg-black/60" @click="closeDetailModal"></div>
        <div class="relative bg-terminal-panel border border-theme-secondary rounded-lg shadow-lg max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto">
          <div class="sticky top-0 bg-terminal-panel px-4 py-3 border-b border-theme-secondary flex items-center justify-between">
            <h3 class="font-bold text-sm text-terminal-primary truncate pr-4">{{ selectedReport?.title }}</h3>
            <button @click="closeDetailModal" class="text-terminal-dim hover:text-terminal-primary transition text-lg leading-none">&times;</button>
          </div>
          <div class="p-4 space-y-3">
            <div class="flex items-center gap-2">
              <span class="text-xs text-terminal-dim w-12">机构:</span>
              <span class="text-xs text-terminal-primary">{{ selectedReport?.institution || '-' }}</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-xs text-terminal-dim w-12">评级:</span>
              <span v-if="selectedReport?.rating" class="px-2 py-0.5 rounded-sm text-[10px]" :class="getRatingClass(selectedReport.rating)">
                {{ selectedReport.rating }}
              </span>
              <span v-else class="text-xs text-terminal-dim">-</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-xs text-terminal-dim w-12">日期:</span>
              <span class="text-xs text-terminal-primary">{{ selectedReport?.date || '-' }}</span>
            </div>
            <div class="pt-3 border-t border-theme-secondary">
              <a
                v-if="selectedReport?.url"
                :href="getPdfProxyUrl(selectedReport.url)"
                target="_blank"
                class="inline-flex items-center gap-1 px-4 py-2 rounded-sm text-xs bg-terminal-accent/20 text-terminal-accent hover:bg-terminal-accent/30 transition"
              >
                📄 查看原文 PDF
              </a>
              <span v-else class="text-xs text-terminal-dim">暂无原文链接</span>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, computed, watch } from 'vue'
import { apiFetch } from '../utils/api.js'
import { useApiError } from '../composables/useApiError.js'
import { safeDispose } from '../utils/chartManager.js'

const { handleError } = useApiError({ showToast: false })

const symbol = ref('')
const keyword = ref('')
const selectedInstitution = ref('')
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const error = ref(null)
const reports = ref(null)
const statistics = ref(null)
const isFallback = ref(false)
const cacheReady = ref(false)

// 排序状态
const sortField = ref('date')
const sortOrder = ref('desc')

// 详情弹窗状态
const showDetailModal = ref(false)
const selectedReport = ref(null)

// 机构列表（从统计数据中提取）
const institutions = computed(() => {
  if (!statistics.value?.institutions) return []
  return Object.keys(statistics.value.institutions).sort()
})

// 排序后的研报列表
const sortedReports = computed(() => {
  if (!reports.value?.items) return []
  const items = [...reports.value.items]
  const field = sortField.value
  const order = sortOrder.value === 'asc' ? 1 : -1
  
  return items.sort((a, b) => {
    let valA = a[field] || ''
    let valB = b[field] || ''
    
    if (field === 'date') {
      valA = valA.replace(/-/g, '')
      valB = valB.replace(/-/g, '')
    }
    
    if (valA < valB) return -1 * order
    if (valA > valB) return 1 * order
    return 0
  })
})

async function checkCacheStatus() {
  try {
    const res = await apiFetch('/api/v1/research/status', { timeoutMs: 5000 })
    cacheReady.value = res?.cache_ready || false
  } catch (e) {
    cacheReady.value = false
  }
}

// 监听机构筛选变化，重置页码并重新获取数据
watch(selectedInstitution, () => {
  if (symbol.value) {
    page.value = 1
    fetchData()
  }
})

// 排序切换
function sortBy(field) {
  if (sortField.value === field) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = field
    sortOrder.value = 'desc'
  }
}

// 显示研报详情
function showReportDetail(report) {
  selectedReport.value = report
  showDetailModal.value = true
}

// 关闭详情弹窗
function closeDetailModal() {
  showDetailModal.value = false
  selectedReport.value = null
}

function getPdfProxyUrl(url) {
  if (!url) return ''
  if (url.startsWith('https://pdf.dfcfw.com/')) {
    return `/api/v1/research/pdf?url=${encodeURIComponent(url)}`
  }
  return url
}

const institutionChartRef = ref(null)
const ratingChartRef = ref(null)
let institutionChartInstance = null
let ratingChartInstance = null

async function fetchData() {
  if (!symbol.value) return
  
  loading.value = true
  error.value = null
  isFallback.value = false
  
  try {
    // 构建查询参数
    const params = new URLSearchParams({
      symbol: symbol.value,
      page: page.value.toString(),
      page_size: pageSize.toString()
    })
    
    if (keyword.value) {
      params.append('keyword', keyword.value)
    }
    
    if (selectedInstitution.value) {
      params.append('institution', selectedInstitution.value)
    }
    
    const [reportsRes, statsRes] = await Promise.all([
      apiFetch(`/api/v1/research/reports?${params.toString()}`, { timeoutMs: 30000 })
        .catch(e => { handleError(e, { context: '研报列表', silent: true }); return null }),
      apiFetch(`/api/v1/research/statistics?symbol=${symbol.value}`, { timeoutMs: 30000 })
        .catch(e => { handleError(e, { context: '研报统计', silent: true }); return null })
    ])
    
    if (reportsRes) {
      reports.value = reportsRes
      isFallback.value = reportsRes.is_fallback || false
      
      if (isFallback.value && !cacheReady.value) {
        setTimeout(() => {
          if (symbol.value) fetchData()
        }, 5000)
      }
    }
    
    if (statsRes) {
      statistics.value = statsRes
      await nextTick()
      drawCharts()
    }
  } catch (e) {
    const { userMessage } = handleError(e, { context: '研报数据' })
    error.value = userMessage
  } finally {
    loading.value = false
  }
}

async function goToPage(newPage) {
  page.value = newPage
  await fetchData()
}

function getChartColors() {
  return {
    primary: getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim() || '#0F52BA',
    text: getComputedStyle(document.documentElement).getPropertyValue('--chart-text').trim() || '#8B949E',
    up: getComputedStyle(document.documentElement).getPropertyValue('--color-up').trim() || '#FF6B6B',
    down: getComputedStyle(document.documentElement).getPropertyValue('--color-down').trim() || '#51CF66',
  }
}

function drawCharts() {
  const echarts = window.echarts
  if (!echarts) return
  
  const colors = getChartColors()
  
  if (institutionChartRef.value && statistics.value?.institutions) {
    if (!institutionChartInstance) {
      institutionChartInstance = echarts.init(institutionChartRef.value)
    }
    
    const data = Object.entries(statistics.value.institutions).map(([name, value]) => ({ name, value }))
    
    institutionChartInstance.setOption({
      tooltip: { trigger: 'item', backgroundColor: 'rgba(15, 23, 42, 0.95)', textStyle: { color: '#E5E7EB' } },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        data: data.slice(0, 10),
        label: { color: colors.text, fontSize: 10 },
        itemStyle: { borderColor: '#1a1f2e', borderWidth: 1 }
      }]
    })
  }
  
  if (ratingChartRef.value && statistics.value?.ratings) {
    if (!ratingChartInstance) {
      ratingChartInstance = echarts.init(ratingChartRef.value)
    }
    
    const data = Object.entries(statistics.value.ratings).map(([name, value]) => ({ name, value }))
    
    ratingChartInstance.setOption({
      tooltip: { trigger: 'axis', backgroundColor: 'rgba(15, 23, 42, 0.95)', textStyle: { color: '#E5E7EB' } },
      grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
      xAxis: { type: 'category', data: data.map(d => d.name), axisLabel: { color: colors.text, fontSize: 10 } },
      yAxis: { type: 'value', axisLabel: { color: colors.text, fontSize: 10 } },
      series: [{
        type: 'bar',
        data: data.map(d => d.value),
        itemStyle: { color: colors.primary }
      }]
    })
  }
}

function getRatingClass(rating) {
  if (!rating) return 'bg-terminal-panel text-terminal-dim'
  if (rating.includes('买入') || rating.includes('增持')) return 'bg-bullish/20 text-bullish'
  if (rating.includes('卖出') || rating.includes('减持')) return 'bg-bearish/20 text-bearish'
  return 'bg-terminal-panel text-terminal-dim'
}

let resizeTimer = null
function handleResize() {
  clearTimeout(resizeTimer)
  resizeTimer = setTimeout(() => {
    institutionChartInstance?.resize()
    ratingChartInstance?.resize()
  }, 150)
}

function handleKeydown(e) {
  if (e.key === 'Escape' && showDetailModal.value) {
    closeDetailModal()
  }
}

onMounted(() => {
  checkCacheStatus()
  window.addEventListener('resize', handleResize)
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  clearTimeout(resizeTimer)
  safeDispose(institutionChartInstance)
  safeDispose(ratingChartInstance)
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.bg-terminal-bg { background: var(--bg-primary, #0f1419); }
.bg-terminal-panel { background: var(--bg-secondary, #1a1f2e); }
.bg-terminal-hover { background: var(--bg-hover, #262d3d); }
.text-terminal-primary { color: var(--text-primary, #E5E7EB); }
.text-terminal-dim { color: var(--text-secondary, #8B949E); }
.text-terminal-accent { color: var(--color-primary, #0F52BA); }
.border-theme-secondary { border-color: var(--border-color, #2d3748); }
.text-bullish { color: var(--color-up, #FF6B6B); }
.text-bearish { color: var(--color-down, #51CF66); }
.bg-bullish\/20 { background: rgba(255, 107, 107, 0.2); }
.bg-bearish\/20 { background: rgba(81, 207, 102, 0.2); }
</style>
