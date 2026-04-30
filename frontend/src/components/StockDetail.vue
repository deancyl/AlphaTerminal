<template>
  <div class="h-full flex flex-col bg-terminal-bg overflow-hidden">
    <!-- 顶部标题栏 -->
    <div class="flex items-center justify-between px-4 py-2 border-b border-theme-secondary shrink-0">
      <div class="flex items-center gap-3">
        <button 
          class="w-8 h-8 flex items-center justify-center rounded hover:bg-theme-hover text-terminal-dim"
          @click="$emit('close')"
          title="返回"
        >
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <div class="flex items-baseline gap-2">
          <span class="text-lg font-bold text-terminal-accent">{{ stockInfo.name || '--' }}</span>
          <span class="text-sm text-terminal-dim font-mono">{{ stockInfo.symbol || symbol }}</span>
        </div>
        <span class="px-2 py-0.5 rounded text-xs" :class="getIndustryClass()">
          {{ stockInfo.industry || '未知行业' }}
        </span>
      </div>
      <div class="flex items-center gap-3">
        <span class="text-2xl font-bold font-mono" :class="priceColor">
          {{ formatPrice(stockInfo.price) }}
        </span>
        <div class="flex flex-col items-end">
          <span class="text-sm font-mono" :class="priceColor">
            {{ stockInfo.change >= 0 ? '+' : '' }}{{ formatPrice(stockInfo.change) }}
          </span>
          <span class="text-xs px-1.5 py-0.5 rounded" :class="changeBadgeClass">
            {{ stockInfo.change_pct >= 0 ? '+' : '' }}{{ formatNumber(stockInfo.change_pct) }}%
          </span>
        </div>
      </div>
    </div>

    <!-- 内容区：左侧导航 + 右侧内容 -->
    <div class="flex-1 flex overflow-hidden">
      <!-- 左侧导航：移动端水平滚动，桌面端固定宽度 -->
      <div class="shrink-0 border-r border-theme-secondary flex flex-col
                  w-full md:w-40 
                  md:flex-col
                  flex-row md:overflow-hidden overflow-x-auto">
        <nav class="p-2 space-y-0 md:space-y-1 flex md:flex-col gap-1 md:gap-0">
          <button
            v-for="tab in tabs"
            :key="tab.id"
            class="flex items-center gap-2 px-3 py-2 rounded text-sm transition-colors whitespace-nowrap"
            :class="activeTab === tab.id
              ? 'bg-terminal-accent/10 text-terminal-accent border-b-2 md:border-b-0 md:border-r-2 border-terminal-accent'
              : 'text-theme-secondary hover:bg-theme-hover hover:text-theme-primary'"
            @click="activeTab = tab.id"
          >
            <span>{{ tab.icon }}</span>
            <span>{{ tab.label }}</span>
          </button>
        </nav>
      </div>

      <!-- 右侧内容：移动端全宽，桌面端自适应 -->
      <div class="flex-1 overflow-y-auto p-2 md:p-4 min-w-0">
        <!-- 公司概况 -->
        <div v-if="activeTab === 'overview'" class="space-y-4">
          <!-- 基本信息卡片 -->
          <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
            <h3 class="text-sm font-bold text-terminal-accent mb-3">📋 基本信息</h3>
            <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <div v-for="item in basicInfoItems" :key="item.label" class="space-y-1">
                <div class="text-xs text-terminal-dim">{{ item.label }}</div>
                <div class="text-sm font-mono text-terminal-primary">{{ item.value || '--' }}</div>
              </div>
            </div>
          </div>

          <!-- 行情数据卡片 -->
          <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
            <h3 class="text-sm font-bold text-terminal-accent mb-3">📈 行情数据</h3>
            <div class="grid grid-cols-2 lg:grid-cols-5 gap-4">
              <div class="space-y-1">
                <div class="text-xs text-terminal-dim">今开</div>
                <div class="text-sm font-mono">{{ formatPrice(stockInfo.open) }}</div>
              </div>
              <div class="space-y-1">
                <div class="text-xs text-terminal-dim">最高</div>
                <div class="text-sm font-mono text-bullish">{{ formatPrice(stockInfo.high) }}</div>
              </div>
              <div class="space-y-1">
                <div class="text-xs text-terminal-dim">最低</div>
                <div class="text-sm font-mono text-bearish">{{ formatPrice(stockInfo.low) }}</div>
              </div>
              <div class="space-y-1">
                <div class="text-xs text-terminal-dim">昨收</div>
                <div class="text-sm font-mono">{{ formatPrice(stockInfo.prev_close) }}</div>
              </div>
              <div class="space-y-1">
                <div class="text-xs text-terminal-dim">成交量</div>
                <div class="text-sm font-mono">{{ formatVolume(stockInfo.volume) }}</div>
              </div>
              <div class="space-y-1">
                <div class="text-xs text-terminal-dim">成交额</div>
                <div class="text-sm font-mono">{{ formatAmount(stockInfo.amount) }}</div>
              </div>
              <div class="space-y-1">
                <div class="text-xs text-terminal-dim">振幅</div>
                <div class="text-sm font-mono">{{ formatNumber(stockInfo.amplitude) }}%</div>
              </div>
              <div class="space-y-1">
                <div class="text-xs text-terminal-dim">换手率</div>
                <div class="text-sm font-mono">{{ formatNumber(stockInfo.turnover_rate) }}%</div>
              </div>
              <div class="space-y-1">
                <div class="text-xs text-terminal-dim">市盈率(TTM)</div>
                <div class="text-sm font-mono">{{ formatNumber(stockInfo.pe_ttm) }}</div>
              </div>
              <div class="space-y-1">
                <div class="text-xs text-terminal-dim">市净率</div>
                <div class="text-sm font-mono">{{ formatNumber(stockInfo.pb) }}</div>
              </div>
            </div>
          </div>

          <!-- 收益率卡片 -->
          <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
            <h3 class="text-sm font-bold text-terminal-accent mb-3">📊 阶段收益</h3>
            <div class="grid grid-cols-2 lg:grid-cols-5 gap-4">
              <div v-for="item in returnItems" :key="item.label" class="space-y-1">
                <div class="text-xs text-terminal-dim">{{ item.label }}</div>
                <div class="text-sm font-mono" :class="getColorClass(item.value)">
                  {{ item.value >= 0 ? '+' : '' }}{{ formatNumber(item.value) }}%
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 财务分析 -->
        <div v-else-if="activeTab === 'financial'" class="space-y-4">
          <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-8 text-center">
            <div class="text-4xl mb-3">📊</div>
            <div class="text-sm text-terminal-dim">财务分析功能开发中...</div>
            <div class="text-xs text-theme-tertiary mt-2">将包含：三大报表、财务比率、杜邦分析</div>
          </div>
        </div>

        <!-- 盈利预测 -->
        <div v-else-if="activeTab === 'forecast'" class="space-y-4">
          <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-8 text-center">
            <div class="text-4xl mb-3">🎯</div>
            <div class="text-sm text-terminal-dim">盈利预测功能开发中...</div>
            <div class="text-xs text-theme-tertiary mt-2">将包含：一致预期、EPS预测、评级分布</div>
          </div>
        </div>

        <!-- 股东研究 -->
        <div v-else-if="activeTab === 'shareholders'" class="space-y-4">
          <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-8 text-center">
            <div class="text-4xl mb-3">👥</div>
            <div class="text-sm text-terminal-dim">股东研究功能开发中...</div>
            <div class="text-xs text-theme-tertiary mt-2">将包含：十大股东、股东户数、增减持</div>
          </div>
        </div>

        <!-- 新闻舆情 -->
        <div v-else-if="activeTab === 'news'" class="space-y-4">
          <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
            <h3 class="text-sm font-bold text-terminal-accent mb-3">📰 相关新闻</h3>
            <NewsFeed :symbol="symbol" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { apiFetch } from '../utils/api.js'
import NewsFeed from './NewsFeed.vue'

const props = defineProps({
  symbol: { type: String, required: true },
  name: { type: String, default: '' }
})

defineEmits(['close'])

const activeTab = ref('overview')
const loading = ref(false)
const stockInfo = ref({})

const tabs = [
  { id: 'overview', label: '公司概况', icon: '📋' },
  { id: 'financial', label: '财务分析', icon: '📊' },
  { id: 'forecast', label: '盈利预测', icon: '🎯' },
  { id: 'shareholders', label: '股东研究', icon: '👥' },
  { id: 'news', label: '新闻舆情', icon: '📰' },
]

// 计算属性：价格颜色
const priceColor = computed(() => {
  const change = stockInfo.value.change || 0
  return change >= 0 ? 'text-bullish' : 'text-bearish'
})

const changeBadgeClass = computed(() => {
  const pct = stockInfo.value.change_pct || 0
  return pct >= 0 ? 'bg-red-500/20 text-bullish' : 'bg-green-500/20 text-bearish'
})

// 基本信息列表
const basicInfoItems = computed(() => [
  { label: '股票代码', value: stockInfo.value.symbol },
  { label: '股票简称', value: stockInfo.value.name },
  { label: '所属行业', value: stockInfo.value.industry },
  { label: '上市时间', value: stockInfo.value.listing_date },
  { label: '总股本', value: formatVolume(stockInfo.value.total_shares) },
  { label: '流通股本', value: formatVolume(stockInfo.value.float_shares) },
  { label: '总市值', value: formatAmount(stockInfo.value.market_cap) },
  { label: '流通市值', value: formatAmount(stockInfo.value.float_cap) },
])

// 收益率列表
const returnItems = computed(() => [
  { label: '5日收益', value: stockInfo.value.returns_5d },
  { label: '20日收益', value: stockInfo.value.returns_20d },
  { label: '60日收益', value: stockInfo.value.returns_60d },
  { label: '年初至今', value: stockInfo.value.returns_ytd },
  { label: '52周最高', value: stockInfo.value.high_52w },
])

// 获取股票详情
async function fetchStockDetail() {
  if (!props.symbol) return
  
  loading.value = true
  try {
    const data = await apiFetch(`/api/v1/market/quote/${props.symbol}`)
    if (data) {
      stockInfo.value = {
        ...data,
        name: props.name || data.name || props.symbol,
      }
    }
  } catch (e) {
    console.error('[StockDetail] Fetch error:', e)
  } finally {
    loading.value = false
  }
}

// 工具函数
function formatPrice(val) {
  if (val === null || val === undefined) return '--'
  return Number(val).toFixed(2)
}

function formatNumber(val) {
  if (val === null || val === undefined) return '--'
  return Number(val).toFixed(2)
}

function formatVolume(val) {
  if (val === null || val === undefined) return '--'
  if (val >= 1e8) return (val / 1e8).toFixed(2) + '亿股'
  if (val >= 1e4) return (val / 1e4).toFixed(2) + '万股'
  return val.toFixed(0)
}

function formatAmount(val) {
  if (val === null || val === undefined) return '--'
  if (val >= 1e12) return (val / 1e12).toFixed(2) + '万亿'
  if (val >= 1e8) return (val / 1e8).toFixed(2) + '亿'
  if (val >= 1e4) return (val / 1e4).toFixed(2) + '万'
  return val.toFixed(0)
}

function getColorClass(val) {
  if (val === null || val === undefined) return 'text-terminal-dim'
  return val >= 0 ? 'text-bullish' : 'text-bearish'
}

function getIndustryClass() {
  return 'bg-terminal-accent/10 text-terminal-accent border border-terminal-accent/30'
}

// 监听symbol变化
watch(() => props.symbol, fetchStockDetail, { immediate: true })
</script>