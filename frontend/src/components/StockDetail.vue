<template>
  <div class="h-full flex flex-col bg-terminal-bg">
    <!-- 顶部证券代码栏 -->
    <div class="flex items-center gap-3 px-4 py-2 border-b border-theme-secondary bg-terminal-panel">
      <div class="flex items-center gap-2">
        <span class="text-lg font-bold text-terminal-accent">F9</span>
        <span class="text-xs text-terminal-dim">深度资料</span>
      </div>
      
      <!-- 代码输入框 -->
      <div class="flex items-center gap-2 flex-1 max-w-md">
        <input
          v-model="inputSymbol"
          type="text"
          placeholder="输入股票代码/拼音/名称"
          class="flex-1 px-3 py-1.5 rounded bg-terminal-bg border border-theme-secondary text-sm text-terminal-primary placeholder-terminal-dim focus:border-terminal-accent focus:outline-none"
          @keyup.enter="handleSearch"
        />
        <button
          class="px-3 py-1.5 rounded bg-terminal-accent/20 text-terminal-accent text-sm hover:bg-terminal-accent/30 transition"
          @click="handleSearch"
        >
          查询
        </button>
      </div>
      
      <!-- 当前股票信息 -->
      <div v-if="stockInfo" class="flex items-center gap-3 text-sm">
        <span class="font-bold text-terminal-primary">{{ stockInfo.name }}</span>
        <span class="text-terminal-dim">{{ stockInfo.symbol }}</span>
        <span :class="priceClass">{{ stockInfo.price }}</span>
        <span :class="changeClass">{{ stockInfo.change }}%</span>
      </div>
    </div>
    
    <!-- 主体区域：左侧导航 + 右侧内容 -->
    <div class="flex-1 flex min-h-0">
      <!-- 左侧导航树 -->
      <div class="w-44 border-r border-theme-secondary bg-terminal-panel overflow-y-auto">
        <div class="py-2">
          <div
            v-for="item in menuItems"
            :key="item.id"
            class="px-3 py-2 text-sm cursor-pointer transition flex items-center gap-2"
            :class="activeTab === item.id ? 'bg-terminal-accent/20 text-terminal-accent border-l-2 border-terminal-accent' : 'text-terminal-secondary hover:bg-theme-hover'"
            @click="activeTab = item.id"
          >
            <span>{{ item.icon }}</span>
            <span>{{ item.name }}</span>
          </div>
        </div>
      </div>
      
      <!-- 右侧内容区 -->
      <div class="flex-1 overflow-y-auto p-4">
        <!-- 公司概况 -->
        <CompanyOverview
          v-if="activeTab === 'overview'"
          :stock-info="stockInfo"
          :loading="loading"
        />
        
        <!-- 财务摘要 -->
        <FinancialSummary
          v-else-if="activeTab === 'finance'"
          :data="financialData"
          :loading="financialLoading"
          :error="financialError"
          @retry="fetchFinancialData"
        />
        
        <!-- 盈利预测 -->
        <ProfitForecast
          v-else-if="activeTab === 'forecast'"
          :data="forecastData"
          :loading="forecastLoading"
          :error="forecastError"
        />
        
        <!-- 机构持股 -->
        <InstitutionalHoldings
          v-else-if="activeTab === 'institution'"
          :data="institutionData"
          :loading="institutionLoading"
          :error="institutionError"
        />
        
        <!-- 股东研究 -->
        <ShareholderResearch
          v-else-if="activeTab === 'shareholder'"
          :data="shareholderData"
          :loading="shareholderLoading"
          :error="shareholderError"
        />
        
        <!-- 公司公告 -->
        <CompanyAnnouncements
          v-else-if="activeTab === 'announcement'"
          :data="announcementsData"
          :loading="announcementsLoading"
          :error="announcementsError"
          :current-page="announcementsPage"
          :page-size="announcementsPageSize"
          @page-change="fetchAnnouncementsData"
        />
        
        <!-- 同业比较 -->
        <PeerComparison
          v-else-if="activeTab === 'peer'"
          :data="peersData"
          :loading="peersLoading"
          :error="peersError"
          :current-symbol="inputSymbol"
        />
        
        <!-- 融资融券 -->
        <MarginTrading
          v-else-if="activeTab === 'margin'"
          :data="marginData"
          :loading="marginLoading"
          :error="marginError"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { apiFetch } from '../utils/api.js'
import { useStockDetail, useStockQuote } from '../composables/useStockDetail.js'

// Import sub-components
import CompanyOverview from './stock-detail/CompanyOverview.vue'
import FinancialSummary from './stock-detail/FinancialSummary.vue'
import InstitutionalHoldings from './stock-detail/InstitutionalHoldings.vue'
import ProfitForecast from './stock-detail/ProfitForecast.vue'
import ShareholderResearch from './stock-detail/ShareholderResearch.vue'
import CompanyAnnouncements from './stock-detail/CompanyAnnouncements.vue'
import PeerComparison from './stock-detail/PeerComparison.vue'
import MarginTrading from './stock-detail/MarginTrading.vue'

const props = defineProps({
  symbol: { type: String, default: '' }
})

const { getBareSymbol } = useStockDetail()
const { stockInfo, loading, fetchQuote, priceClass, changeClass } = useStockQuote()

const inputSymbol = ref(props.symbol)
const activeTab = ref('overview')

// Data states for each tab
const shareholderData = ref(null)
const shareholderLoading = ref(false)
const shareholderError = ref(null)

const marginData = ref(null)
const marginLoading = ref(false)
const marginError = ref(null)

const institutionData = ref(null)
const institutionLoading = ref(false)
const institutionError = ref('')

const financialData = ref(null)
const financialLoading = ref(false)
const financialError = ref('')

const forecastData = ref(null)
const forecastLoading = ref(false)
const forecastError = ref(null)

const peersData = ref(null)
const peersLoading = ref(false)
const peersError = ref(null)

const announcementsData = ref(null)
const announcementsLoading = ref(false)
const announcementsError = ref(null)
const announcementsPage = ref(1)
const announcementsPageSize = ref(20)

const menuItems = [
  { id: 'overview', name: '公司概况', icon: '🏢' },
  { id: 'finance', name: '财务摘要', icon: '📊' },
  { id: 'forecast', name: '盈利预测', icon: '📈' },
  { id: 'institution', name: '机构持股', icon: '🏛️' },
  { id: 'shareholder', name: '股东研究', icon: '👥' },
  { id: 'announcement', name: '公司公告', icon: '📢' },
  { id: 'peer', name: '同业比较', icon: '📋' },
  { id: 'margin', name: '融资融券', icon: '💹' },
]

async function handleSearch() {
  if (!inputSymbol.value) return
  await fetchQuote(inputSymbol.value)
}

async function fetchShareholderData() {
  if (!inputSymbol.value) return
  shareholderLoading.value = true
  shareholderError.value = null
  try {
    const bareSymbol = getBareSymbol(inputSymbol.value)
    const data = await apiFetch(`/api/v1/f9/${bareSymbol}/shareholder`, { timeoutMs: 30000 })
    if (data && (data.circulateHolders || data.shareChanges || data.holderChanges)) {
      shareholderData.value = data
    } else {
      shareholderError.value = '获取股东数据失败'
    }
  } catch (e) {
    console.error('[StockDetail] Shareholder fetch error:', e)
    shareholderError.value = e.message || '网络请求失败'
  } finally {
    shareholderLoading.value = false
  }
}

async function fetchMarginData(symbol) {
  if (!symbol) return
  marginLoading.value = true
  marginError.value = null
  try {
    const bareSymbol = getBareSymbol(symbol)
    const data = await apiFetch(`/api/v1/f9/${bareSymbol}/margin`, { timeoutMs: 30000 })
    if (data && data.current) {
      marginData.value = data
    } else {
      marginError.value = '暂无融资融券数据'
    }
  } catch (e) {
    console.error('[StockDetail] Margin data fetch error:', e)
    marginError.value = e.message || '获取融资融券数据失败'
  } finally {
    marginLoading.value = false
  }
}

async function fetchFinancialData() {
  if (!inputSymbol.value) return
  financialLoading.value = true
  financialError.value = ''
  try {
    const bareSymbol = getBareSymbol(inputSymbol.value)
    const data = await apiFetch(`/api/v1/f9/${bareSymbol}/financial`, { timeoutMs: 30000 })
    if (data && data.indicators && data.indicators.length > 0) {
      financialData.value = data
    } else {
      financialError.value = '暂无财务数据'
    }
  } catch (e) {
    console.error('[StockDetail] Financial data fetch error:', e)
    financialError.value = '加载财务数据失败，请稍后重试'
  } finally {
    financialLoading.value = false
  }
}

async function fetchForecastData(symbol) {
  if (!symbol) return
  forecastLoading.value = true
  forecastError.value = null
  try {
    const bareSymbol = getBareSymbol(symbol)
    const data = await apiFetch(`/api/v1/f9/${bareSymbol}/forecast`, { timeoutMs: 30000 })
    if (data && ((data.eps_forecast && data.eps_forecast.length > 0) || (data.institutions && data.institutions.length > 0))) {
      forecastData.value = data
    } else {
      forecastError.value = '暂无盈利预测数据'
    }
  } catch (e) {
    console.error('[StockDetail] Forecast error:', e)
    forecastError.value = e.message || '网络请求失败'
  } finally {
    forecastLoading.value = false
  }
}

async function fetchPeersData(symbol) {
  if (!symbol) return
  peersLoading.value = true
  peersError.value = null
  try {
    const bareSymbol = getBareSymbol(symbol)
    const data = await apiFetch(`/api/v1/f9/${bareSymbol}/peers`, { timeoutMs: 30000 })
    if (data && data.peers && data.peers.length > 0) {
      peersData.value = data
    } else {
      peersError.value = '暂无同业比较数据'
    }
  } catch (e) {
    console.error('[StockDetail] Peers error:', e)
    peersError.value = e.message || '网络请求失败'
  } finally {
    peersLoading.value = false
  }
}

async function fetchAnnouncementsData(page = 1) {
  if (!inputSymbol.value) return
  announcementsLoading.value = true
  announcementsError.value = null
  announcementsPage.value = page
  try {
    const bareSymbol = getBareSymbol(inputSymbol.value)
    const data = await apiFetch(`/api/v1/f9/${bareSymbol}/announcements?page=${page}&page_size=${announcementsPageSize.value}`, { timeoutMs: 30000 })
    if (data && data.announcements) {
      announcementsData.value = data
    } else {
      announcementsError.value = '获取公告数据失败'
    }
  } catch (e) {
    console.error('[StockDetail] Announcements fetch error:', e)
    announcementsError.value = e.message || '网络请求失败'
  } finally {
    announcementsLoading.value = false
  }
}

async function fetchInstitutionData() {
  if (!inputSymbol.value) return
  
  institutionLoading.value = true
  institutionError.value = ''
  
  try {
    const bareSymbol = getBareSymbol(inputSymbol.value)
    const data = await apiFetch(`/api/v1/f9/${bareSymbol}/institution`, { timeoutMs: 30000 })
    if (data && ((data.current && data.current.length > 0) || (data.trend && data.trend.length > 0))) {
      institutionData.value = data
    } else {
      institutionError.value = '暂无机构持股数据'
    }
  } catch (e) {
    console.error('[StockDetail] Institution fetch error:', e)
    institutionError.value = `获取数据失败: ${e.message || '未知错误'}`
  } finally {
    institutionLoading.value = false
  }
}

// Watch props.symbol changes
watch(() => props.symbol, (newSymbol) => {
  if (newSymbol) {
    inputSymbol.value = newSymbol
    handleSearch()
  }
}, { immediate: true })

// Watch activeTab changes to lazy-load data
watch(activeTab, (newTab) => {
  if (!inputSymbol.value) return
  
  if (newTab === 'finance' && !financialData.value) {
    fetchFinancialData()
  }
  if (newTab === 'shareholder' && !shareholderData.value) {
    fetchShareholderData()
  }
  if (newTab === 'margin' && !marginData.value) {
    fetchMarginData(inputSymbol.value)
  }
  if (newTab === 'institution' && !institutionData.value) {
    fetchInstitutionData()
  }
  if (newTab === 'forecast' && !forecastData.value) {
    fetchForecastData(inputSymbol.value)
  }
  if (newTab === 'peer' && !peersData.value) {
    fetchPeersData(inputSymbol.value)
  }
  if (newTab === 'announcement' && !announcementsData.value) {
    fetchAnnouncementsData()
  }
})
</script>
