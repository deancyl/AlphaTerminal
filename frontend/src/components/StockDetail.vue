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
        <div v-if="activeTab === 'overview'" class="space-y-4">
          <h2 class="text-lg font-bold text-terminal-accent">公司概况</h2>
          
          <div v-if="loading" class="text-center py-8 text-terminal-dim">
            加载中...
          </div>
          
          <div v-else-if="!stockInfo" class="text-center py-8 text-terminal-dim">
            请输入股票代码查询
          </div>
          
          <div v-else class="space-y-4">
            <!-- 基本信息卡片 -->
            <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
              <h3 class="text-sm font-bold text-terminal-primary mb-3">基本信息</h3>
              <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div>
                  <div class="text-xs text-terminal-dim">股票名称</div>
                  <div class="text-sm text-terminal-primary">{{ stockInfo.name || '--' }}</div>
                </div>
                <div>
                  <div class="text-xs text-terminal-dim">股票代码</div>
                  <div class="text-sm text-terminal-primary">{{ stockInfo.symbol || '--' }}</div>
                </div>
                <div>
                  <div class="text-xs text-terminal-dim">所属行业</div>
                  <div class="text-sm text-terminal-primary">{{ stockInfo.industry || '--' }}</div>
                </div>
                <div>
                  <div class="text-xs text-terminal-dim">上市时间</div>
                  <div class="text-sm text-terminal-primary">{{ stockInfo.listDate || '--' }}</div>
                </div>
                <div>
                  <div class="text-xs text-terminal-dim">总股本</div>
                  <div class="text-sm text-terminal-primary">{{ formatNumber(stockInfo.totalShares) }}</div>
                </div>
                <div>
                  <div class="text-xs text-terminal-dim">流通股本</div>
                  <div class="text-sm text-terminal-primary">{{ formatNumber(stockInfo.floatShares) }}</div>
                </div>
                <div>
                  <div class="text-xs text-terminal-dim">总市值</div>
                  <div class="text-sm text-terminal-primary">{{ formatMoney(stockInfo.totalMarketCap) }}</div>
                </div>
                <div>
                  <div class="text-xs text-terminal-dim">流通市值</div>
                  <div class="text-sm text-terminal-primary">{{ formatMoney(stockInfo.floatMarketCap) }}</div>
                </div>
              </div>
            </div>
            
            <!-- 主营业务 -->
            <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
              <h3 class="text-sm font-bold text-terminal-primary mb-3">主营业务</h3>
              <p class="text-sm text-terminal-secondary leading-relaxed">
                {{ stockInfo.business || '暂无数据' }}
              </p>
            </div>
          </div>
        </div>
        
        <!-- 财务摘要 -->
        <div v-else-if="activeTab === 'finance'" class="space-y-4">
          <h2 class="text-lg font-bold text-terminal-accent">财务摘要</h2>
          <div class="text-center py-8 text-terminal-dim">
            财务数据开发中...
          </div>
        </div>
        
        <!-- 盈利预测 -->
        <div v-else-if="activeTab === 'forecast'" class="space-y-4">
          <h2 class="text-lg font-bold text-terminal-accent">盈利预测</h2>
          <div class="text-center py-8 text-terminal-dim">
            盈利预测数据开发中...
          </div>
        </div>
        
        <!-- 机构持股 -->
        <div v-else-if="activeTab === 'institution'" class="space-y-4">
          <h2 class="text-lg font-bold text-terminal-accent">机构持股</h2>
          <div class="text-center py-8 text-terminal-dim">
            机构持股数据开发中...
          </div>
        </div>
        
        <!-- 股东研究 -->
        <div v-else-if="activeTab === 'shareholder'" class="space-y-4">
          <h2 class="text-lg font-bold text-terminal-accent">股东研究</h2>
          <div class="text-center py-8 text-terminal-dim">
            股东数据开发中...
          </div>
        </div>
        
        <!-- 公司公告 -->
        <div v-else-if="activeTab === 'announcement'" class="space-y-4">
          <h2 class="text-lg font-bold text-terminal-accent">公司公告</h2>
          <div class="text-center py-8 text-terminal-dim">
            公告数据开发中...
          </div>
        </div>
        
        <!-- 同业比较 -->
        <div v-else-if="activeTab === 'peer'" class="space-y-4">
          <h2 class="text-lg font-bold text-terminal-accent">同业比较</h2>
          <div class="text-center py-8 text-terminal-dim">
            同业比较数据开发中...
          </div>
        </div>
        
        <!-- 融资融券 -->
        <div v-else-if="activeTab === 'margin'" class="space-y-4">
          <h2 class="text-lg font-bold text-terminal-accent">融资融券</h2>
          <div class="text-center py-8 text-terminal-dim">
            融资融券数据开发中...
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { apiFetch } from '../utils/api.js'

const props = defineProps({
  symbol: { type: String, default: '' }
})

const inputSymbol = ref(props.symbol)
const activeTab = ref('overview')
const loading = ref(false)
const stockInfo = ref(null)

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

const priceClass = computed(() => {
  if (!stockInfo.value) return ''
  return stockInfo.value.change >= 0 ? 'text-bullish' : 'text-bearish'
})

const changeClass = computed(() => {
  if (!stockInfo.value) return ''
  return stockInfo.value.change >= 0 ? 'text-bullish' : 'text-bearish'
})

async function handleSearch() {
  if (!inputSymbol.value) return
  loading.value = true
  try {
    // 先尝试从已有接口获取数据
    const data = await apiFetch(`/api/v1/stocks/quote?symbol=${inputSymbol.value}`, { timeoutMs: 10000 })
    if (data) {
      stockInfo.value = {
        symbol: inputSymbol.value,
        name: data.name || inputSymbol.value,
        price: data.price || 0,
        change: data.change || 0,
        industry: data.industry || '--',
        totalShares: data.totalShares,
        floatShares: data.floatShares,
        totalMarketCap: data.totalMarketCap,
        floatMarketCap: data.floatMarketCap,
        listDate: data.listDate,
        business: data.business || '暂无主营业务数据',
      }
    }
  } catch (e) {
    console.error('[StockDetail] Search error:', e)
    // 使用模拟数据演示UI
    stockInfo.value = {
      symbol: inputSymbol.value,
      name: '演示股票',
      price: 10.50,
      change: 2.35,
      industry: '计算机软件',
      totalShares: 1000000000,
      floatShares: 800000000,
      totalMarketCap: 10500000000,
      floatMarketCap: 8400000000,
      listDate: '2020-01-01',
      business: '公司主要从事人工智能、大数据、云计算等前沿技术的研发与应用，为客户提供智能化的解决方案。',
    }
  } finally {
    loading.value = false
  }
}

function formatNumber(num) {
  if (!num) return '--'
  if (num >= 1e8) return (num / 1e8).toFixed(2) + '亿'
  if (num >= 1e4) return (num / 1e4).toFixed(2) + '万'
  return num.toString()
}

function formatMoney(num) {
  if (!num) return '--'
  if (num >= 1e12) return (num / 1e12).toFixed(2) + '万亿'
  if (num >= 1e8) return (num / 1e8).toFixed(2) + '亿'
  if (num >= 1e4) return (num / 1e4).toFixed(2) + '万'
  return num.toString()
}

// 监听 props.symbol 变化
watch(() => props.symbol, (newSymbol) => {
  if (newSymbol) {
    inputSymbol.value = newSymbol
    handleSearch()
  }
}, { immediate: true })
</script>
