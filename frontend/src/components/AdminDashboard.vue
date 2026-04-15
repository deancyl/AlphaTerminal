<template>
  <div class="flex h-full">
    <!-- 左侧：设置导航 -->
    <aside class="w-52 border-r border-theme bg-theme-panel flex-shrink-0">
      <div class="p-4 border-b border-theme">
        <span class="text-sm font-bold text-terminal-accent">⚙️ 系统管理</span>
      </div>
      <nav class="py-2">
        <button
          v-for="item in adminNavItems"
          :key="item.id"
          class="w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-all"
          :class="activeAdminTab === item.id
            ? 'bg-terminal-accent/15 text-terminal-accent border-r-2 border-terminal-accent'
            : 'text-theme-secondary hover:bg-theme-hover hover:text-theme-primary'"
          @click="activeAdminTab = item.id"
        >
          <span class="text-base">{{ item.icon }}</span>
          <span>{{ item.label }}</span>
          <span v-if="item.badge" class="ml-auto text-[10px] px-1.5 py-0.5 rounded-full" :class="item.badgeClass">
            {{ item.badge }}
          </span>
        </button>
      </nav>
      
      <!-- 版本信息 -->
      <div class="absolute bottom-4 left-4 text-[10px] text-theme-muted">
        AlphaTerminal v{{ version }}
      </div>
    </aside>

    <!-- 右侧：内容区 -->
    <main class="flex-1 overflow-auto p-6">
      
      <!-- ═══ 数据源管理 ══════════════════════════════════════════ -->
      <div v-if="activeAdminTab === 'source'" class="space-y-6">
        
        <!-- Header -->
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-bold text-theme-primary flex items-center gap-2">
              📡 数据源管理
              <span v-if="sourceStatus.current" class="text-xs font-normal px-2 py-0.5 rounded bg-terminal-accent/10 text-terminal-accent">
                主源: {{ sourceStatus.current }}
              </span>
            </h2>
            <p class="text-xs text-theme-muted mt-1">管理数据源连接、代理设置和 API Key</p>
          </div>
          <div class="flex gap-2">
            <button
              class="px-4 py-2 bg-blue-500/15 text-blue-400 rounded-lg text-sm hover:bg-blue-500/25 transition-all flex items-center gap-2"
              @click="testAllSources"
              :disabled="testing"
            >
              <span v-if="testing" class="animate-spin">⏳</span>
              <span v-else>🧪</span>
              {{ testing ? '测试中...' : '测试全部源' }}
            </button>
            <button
              class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-lg text-sm hover:bg-terminal-accent/25 transition-all flex items-center gap-2"
              @click="refreshStatus"
              :disabled="refreshing"
            >
              <span v-if="refreshing" class="animate-spin">🔄</span>
              <span v-else>🔄</span>
              {{ refreshing ? '刷新中...' : '刷新状态' }}
            </button>
          </div>
        </div>

        <!-- 测试结果 -->
        <div v-if="testResults" class="p-4 bg-theme-secondary/20 rounded-lg border border-theme animate-fade-in">
          <div class="flex items-center justify-between mb-3">
            <span class="text-sm font-medium text-theme-primary">🧪 测试结果</span>
            <span class="text-xs text-theme-muted">{{ testTime }}</span>
          </div>
          <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <div
              v-for="(result, key) in testResults"
              :key="key"
              class="p-3 rounded-lg text-center transition-all"
              :class="result.status === 'ok' 
                ? 'bg-green-500/10 border border-green-500/30' 
                : 'bg-red-500/10 border border-red-500/30'"
            >
              <div class="text-lg mb-1">{{ sourceIcons[key] || '📡' }}</div>
              <div class="text-xs font-medium" :class="result.status === 'ok' ? 'text-green-400' : 'text-red-400'">
                {{ key }}
              </div>
              <div class="text-[10px] mt-1" :class="result.status === 'ok' ? 'text-green-400' : 'text-red-400'">
                {{ result.status === 'ok' ? '✅ 在线' : '❌ 离线' }}
              </div>
              <div v-if="result.latency" class="text-[10px] text-theme-muted mt-0.5">
                {{ result.latency }}ms
              </div>
            </div>
          </div>
        </div>

        <!-- 代理与API设置 -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <!-- 代理设置 -->
          <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
            <div class="flex items-center justify-between mb-3">
              <h3 class="text-sm font-bold text-theme-primary flex items-center gap-2">
                🌐 代理设置
                <span class="text-[10px] px-1.5 py-0.5 rounded" :class="proxyAddress ? 'bg-orange-500/20 text-orange-400' : 'bg-green-500/20 text-green-400'">
                  {{ proxyAddress ? '已配置' : '直连' }}
                </span>
              </h3>
              <button
                v-if="!editingProxy"
                class="text-xs text-terminal-accent hover:underline flex items-center gap-1"
                @click="editingProxy = true"
              >
                ✏️ 编辑
              </button>
            </div>
            <div v-if="editingProxy" class="space-y-3">
              <input
                v-model="proxyAddress"
                type="text"
                placeholder="http://192.168.1.50:7897"
                class="w-full px-3 py-2 bg-theme-panel border border-theme rounded-lg text-sm text-theme-primary focus:border-terminal-accent outline-none"
              />
              <div class="flex gap-2">
                <button
                  class="px-4 py-1.5 bg-terminal-accent/20 text-terminal-accent rounded text-sm hover:bg-terminal-accent/30"
                  @click="saveProxy"
                  :disabled="savingProxy"
                >
                  {{ savingProxy ? '保存中...' : '💾 保存' }}
                </button>
                <button
                  class="px-4 py-1.5 bg-theme-secondary/50 text-theme-secondary rounded text-sm"
                  @click="editingProxy = false"
                >
                  取消
                </button>
              </div>
            </div>
            <div v-else class="text-sm text-theme-tertiary">
              {{ proxyAddress || '未设置 (使用直连)' }}
            </div>
          </div>

          <!-- AlphaVantage API Key -->
          <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
            <div class="flex items-center justify-between mb-3">
              <h3 class="text-sm font-bold text-theme-primary flex items-center gap-2">
                🔷 AlphaVantage API
                <span class="text-[10px] px-1.5 py-0.5 rounded" :class="alphaVKey ? 'bg-blue-500/20 text-blue-400' : 'bg-gray-500/20 text-gray-400'">
                  {{ alphaVKey ? '已配置' : '使用默认' }}
                </span>
              </h3>
              <button
                v-if="!editingAlphaVKey"
                class="text-xs text-terminal-accent hover:underline flex items-center gap-1"
                @click="editingAlphaVKey = true"
              >
                ✏️ 编辑
              </button>
            </div>
            <div v-if="editingAlphaVKey" class="space-y-3">
              <input
                v-model="alphaVKey"
                type="text"
                placeholder="输入你的 API Key"
                class="w-full px-3 py-2 bg-theme-panel border border-theme rounded-lg text-sm text-theme-primary focus:border-terminal-accent outline-none"
              />
              <div class="flex gap-2">
                <button
                  class="px-4 py-1.5 bg-terminal-accent/20 text-terminal-accent rounded text-sm hover:bg-terminal-accent/30"
                  @click="saveAlphaVKey"
                  :disabled="savingKey"
                >
                  {{ savingKey ? '保存中...' : '💾 保存' }}
                </button>
                <button
                  class="px-4 py-1.5 bg-theme-secondary/50 text-theme-secondary rounded text-sm"
                  @click="editingAlphaVKey = false"
                >
                  取消
                </button>
              </div>
            </div>
            <div v-else class="text-sm text-theme-tertiary">
              {{ alphaVKey ? alphaVKey.substring(0, 8) + '...' : '使用默认 Key (限速)' }}
            </div>
          </div>
        </div>

        <!-- 数据源列表 -->
        <div class="space-y-3">
          <span class="text-sm font-medium text-theme-primary">可用数据源</span>
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div
              v-for="(cfg, key) in sourceStatus.config"
              :key="key"
              class="p-4 rounded-lg border cursor-pointer transition-all hover:scale-[1.02]"
              :class="sourceStatus.current === key
                ? 'bg-terminal-accent/10 border-terminal-accent/50 ring-1 ring-terminal-accent/30'
                : 'bg-theme-secondary/20 border-theme hover:border-theme-tertiary'"
              @click="switchSource(key)"
            >
              <div class="flex items-center justify-between mb-3">
                <div class="flex items-center gap-2">
                  <span class="text-xl">{{ sourceIcons[key] || '📡' }}</span>
                  <div>
                    <div class="font-medium text-theme-primary">{{ cfg.name }}</div>
                    <div class="text-[10px] text-theme-muted">{{ key }}</div>
                  </div>
                </div>
                <span
                  class="text-[10px] px-2 py-0.5 rounded-full"
                  :class="cfg.type === 'primary' 
                    ? 'bg-green-500/20 text-green-400' 
                    : 'bg-gray-500/20 text-gray-400'"
                >
                  {{ cfg.type === 'primary' ? '⭐ 主源' : '📋 备用' }}
                </span>
              </div>
              
              <div class="flex flex-wrap gap-2 mb-3">
                <span 
                  class="text-[10px] px-2 py-0.5 rounded flex items-center gap-1"
                  :class="cfg.proxy ? 'bg-orange-500/20 text-orange-400' : 'bg-green-500/20 text-green-400'"
                >
                  {{ cfg.proxy ? '🌐 需代理' : '🚀 直连' }}
                </span>
                <span v-if="cfg.has_pepb" class="text-[10px] px-2 py-0.5 rounded bg-blue-500/20 text-blue-400">
                  📊 PE/PB
                </span>
                <span v-if="cfg.has_realtime" class="text-[10px] px-2 py-0.5 rounded bg-purple-500/20 text-purple-400">
                  ⚡ 实时
                </span>
              </div>
              
              <div class="flex items-center justify-between pt-2 border-t border-theme/50">
                <div class="flex items-center gap-2">
                  <span 
                    class="w-2 h-2 rounded-full"
                    :class="getSourceStatus(key) === 'ok' ? 'bg-green-400' : getSourceStatus(key) === 'fail' ? 'bg-red-400' : 'bg-gray-400'"
                  ></span>
                  <span class="text-xs" :class="getSourceStatus(key) === 'ok' ? 'text-green-400' : getSourceStatus(key) === 'fail' ? 'text-red-400' : 'text-gray-400'">
                    {{ getSourceStatus(key) === 'ok' ? '在线' : getSourceStatus(key) === 'fail' ? '离线' : '未知' }}
                  </span>
                </div>
                <span v-if="sourceStatus.sources[key]?.latency" class="text-xs text-theme-muted">
                  {{ sourceStatus.sources[key].latency }}ms
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ═══ 系统信息 ══════════════════════════════════════════ -->
      <div v-else-if="activeAdminTab === 'system'" class="space-y-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-bold text-theme-primary">💻 系统信息</h2>
            <p class="text-xs text-theme-muted mt-1">当前系统运行状态和版本信息</p>
          </div>
          <button
            class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-lg text-sm hover:bg-terminal-accent/25 transition-all"
            @click="refreshSystemInfo"
            :disabled="loadingSystem"
          >
            🔄 刷新
          </button>
        </div>

        <!-- 版本卡片 -->
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
            <div class="text-xs text-theme-muted mb-1">前端版本</div>
            <div class="text-xl font-bold text-terminal-accent">{{ systemInfo.frontendVersion || version }}</div>
          </div>
          <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
            <div class="text-xs text-theme-muted mb-1">后端版本</div>
            <div class="text-xl font-bold text-terminal-accent">{{ systemInfo.backendVersion || 'v0.4.137' }}</div>
          </div>
          <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
            <div class="text-xs text-theme-muted mb-1">当前数据源</div>
            <div class="text-xl font-bold text-green-400">{{ sourceStatus.current || 'tencent' }}</div>
          </div>
          <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
            <div class="text-xs text-theme-muted mb-1">最后更新</div>
            <div class="text-sm font-medium text-theme-primary">{{ lastUpdate || 'N/A' }}</div>
          </div>
        </div>

        <!-- 详细状态 -->
        <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
          <h3 class="text-sm font-bold text-theme-primary mb-4">📊 服务状态</h3>
          <div class="grid grid-cols-2 gap-4">
            <div class="flex items-center justify-between p-3 bg-theme-panel/50 rounded">
              <span class="text-sm text-theme-secondary">后端服务</span>
              <span class="flex items-center gap-1 text-green-400">
                <span class="w-2 h-2 rounded-full bg-green-400 animate-pulse"></span>
                运行中
              </span>
            </div>
            <div class="flex items-center justify-between p-3 bg-theme-panel/50 rounded">
              <span class="text-sm text-theme-secondary">调度器</span>
              <span class="flex items-center gap-1" :class="systemInfo.schedulerStatus === 'running' ? 'text-green-400' : 'text-gray-400'">
                <span class="w-2 h-2 rounded-full" :class="systemInfo.schedulerStatus === 'running' ? 'bg-green-400 animate-pulse' : 'bg-gray-400'"></span>
                {{ systemInfo.schedulerStatus === 'running' ? '运行中' : '已停止' }}
              </span>
            </div>
            <div class="flex items-center justify-between p-3 bg-theme-panel/50 rounded">
              <span class="text-sm text-theme-secondary">板块缓存</span>
              <span class="flex items-center gap-1" :class="systemInfo.sectorsCache === 'ready' ? 'text-green-400' : 'text-orange-400'">
                <span class="w-2 h-2 rounded-full" :class="systemInfo.sectorsCache === 'ready' ? 'bg-green-400' : 'bg-orange-400'"></span>
                {{ systemInfo.sectorsCache === 'ready' ? '已就绪' : '初始化中' }}
              </span>
            </div>
            <div class="flex items-center justify-between p-3 bg-theme-panel/50 rounded">
              <span class="text-sm text-theme-secondary">新闻缓存</span>
              <span class="flex items-center gap-1" :class="systemInfo.newsCache === 'ready' ? 'text-green-400' : 'text-orange-400'">
                <span class="w-2 h-2 rounded-full" :class="systemInfo.newsCache === 'ready' ? 'bg-green-400' : 'bg-orange-400'"></span>
                {{ systemInfo.newsCache === 'ready' ? '已就绪' : '初始化中' }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- ═══ API 文档 ══════════════════════════════════════════ -->
      <div v-else-if="activeAdminTab === 'docs'" class="space-y-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-bold text-theme-primary">📚 API 文档</h2>
            <p class="text-xs text-theme-muted mt-1">AlphaTerminal API 接口文档 v{{ version }}</p>
          </div>
        </div>

        <!-- 文档分类 -->
        <div class="space-y-6">
          <!-- 市场数据 -->
          <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
            <h3 class="text-sm font-bold text-terminal-accent mb-3 flex items-center gap-2">
              📈 市场数据 API
            </h3>
            <div class="space-y-3">
              <div v-for="api in marketApis" :key="api.path" class="p-3 bg-theme-panel/50 rounded border border-theme/50">
                <div class="flex items-center gap-2 mb-2">
                  <span 
                    class="px-2 py-0.5 rounded text-[10px] font-bold"
                    :class="api.method === 'GET' ? 'bg-green-500/20 text-green-400' : 'bg-blue-500/20 text-blue-400'"
                  >
                    {{ api.method }}
                  </span>
                  <code class="text-xs text-terminal-accent">{{ api.path }}</code>
                </div>
                <p class="text-xs text-theme-secondary">{{ api.desc }}</p>
              </div>
            </div>
          </div>

          <!-- 新闻 API -->
          <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
            <h3 class="text-sm font-bold text-terminal-accent mb-3 flex items-center gap-2">
              📰 新闻 API
            </h3>
            <div class="space-y-3">
              <div v-for="api in newsApis" :key="api.path" class="p-3 bg-theme-panel/50 rounded border border-theme/50">
                <div class="flex items-center gap-2 mb-2">
                  <span 
                    class="px-2 py-0.5 rounded text-[10px] font-bold"
                    :class="api.method === 'GET' ? 'bg-green-500/20 text-green-400' : 'bg-blue-500/20 text-blue-400'"
                  >
                    {{ api.method }}
                  </span>
                  <code class="text-xs text-terminal-accent">{{ api.path }}</code>
                </div>
                <p class="text-xs text-theme-secondary">{{ api.desc }}</p>
              </div>
            </div>
          </div>

          <!-- 数据源管理 API -->
          <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
            <h3 class="text-sm font-bold text-terminal-accent mb-3 flex items-center gap-2">
              ⚙️ 数据源管理 API
            </h3>
            <div class="space-y-3">
              <div v-for="api in sourceApis" :key="api.path" class="p-3 bg-theme-panel/50 rounded border border-theme/50">
                <div class="flex items-center gap-2 mb-2">
                  <span 
                    class="px-2 py-0.5 rounded text-[10px] font-bold"
                    :class="api.method === 'GET' ? 'bg-green-500/20 text-green-400' : api.method === 'POST' ? 'bg-blue-500/20 text-blue-400' : 'bg-orange-500/20 text-orange-400'"
                  >
                    {{ api.method }}
                  </span>
                  <code class="text-xs text-terminal-accent">{{ api.path }}</code>
                </div>
                <p class="text-xs text-theme-secondary">{{ api.desc }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ═══ 关于 ══════════════════════════════════════════ -->
      <div v-else-if="activeAdminTab === 'about'" class="space-y-6">
        <div class="text-center py-12">
          <div class="text-6xl mb-4">📈</div>
          <div class="text-2xl font-bold text-theme-primary mb-2">AlphaTerminal</div>
          <div class="text-lg text-theme-secondary mb-4">A股/港股/美股投研终端</div>
          <div class="text-sm text-theme-muted mb-8">
            专业的金融投研平台 · Phase 7
          </div>
          
          <div class="grid grid-cols-3 gap-4 max-w-md mx-auto">
            <div class="p-4 bg-theme-secondary/20 rounded-lg">
              <div class="text-2xl font-bold text-terminal-accent">{{ version }}</div>
              <div class="text-xs text-theme-muted">版本号</div>
            </div>
            <div class="p-4 bg-theme-secondary/20 rounded-lg">
              <div class="text-2xl font-bold text-green-400">6</div>
              <div class="text-xs text-theme-muted">数据源</div>
            </div>
            <div class="p-4 bg-theme-secondary/20 rounded-lg">
              <div class="text-2xl font-bold text-blue-400">4</div>
              <div class="text-xs text-theme-muted">API分类</div>
            </div>
          </div>
          
          <div class="mt-8 text-xs text-theme-muted">
            <p>基于 FastAPI + Vue3 + ECharts 构建</p>
            <p class="mt-1">使用 AkShare 获取免费市场数据</p>
          </div>
        </div>
      </div>

    </main>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { apiFetch } from '../utils/api.js'

const version = ref('0.4.137') // 默认值，实际从后端获取
const activeAdminTab = ref('source')

// 导航项
const adminNavItems = computed(() => [
  { id: 'source', label: '数据源管理', icon: '📡' },
  { id: 'system', label: '系统信息', icon: '💻' },
  { id: 'docs', label: 'API 文档', icon: '📚' },
  { id: 'about', label: '关于', icon: 'ℹ️' },
])

// 状态
const sourceStatus = ref({
  current: 'tencent',
  sources: {},
  config: {}
})
const testResults = ref(null)
const testTime = ref('')
const lastUpdate = ref('')
const refreshing = ref(false)
const testing = ref(false)
const savingProxy = ref(false)
const savingKey = ref(false)
const loadingSystem = ref(false)

// 系统信息
const systemInfo = reactive({
  frontendVersion: version,
  backendVersion: 'v0.4.137',
  schedulerStatus: 'running',
  sectorsCache: 'ready',
  newsCache: 'ready',
})

// 编辑状态
const proxyAddress = ref('')
const editingProxy = ref(false)
const alphaVKey = ref('')
const editingAlphaVKey = ref(false)

// 图标映射
const sourceIcons = {
  tencent: '🐧',
  eastmoney: '📊',
  sina: '📰',
  sina_finance: '💰',
  netEase: '📓',
  investing: '📈',
  alpha_vantage: '🔷',
  finnhub: '🔶',
  twelvedata: '🕐',
  polygon: '⬡',
  yahoo: '🦅',
}

// API 文档数据
const marketApis = [
  { method: 'GET', path: '/api/v1/market/overview', desc: '获取市场概览（风向标指数）' },
  { method: 'GET', path: '/api/v1/market/sectors', desc: '获取行业板块数据（Top 20）' },
  { method: 'GET', path: '/api/v1/market/china_all', desc: '获取A股全部指数' },
  { method: 'GET', path: '/api/v1/market/global', desc: '获取全球指数（港美股）' },
  { method: 'GET', path: '/api/v1/market/macro', desc: '获取宏观经济数据（SHIBOR/LPR）' },
  { method: 'GET', path: '/api/v1/market/rates', desc: '获取利率数据' },
  { method: 'GET', path: '/api/v1/market/derivatives', desc: '获取期货行情' },
]

const newsApis = [
  { method: 'GET', path: '/api/v1/news/flash', desc: '获取快讯新闻（150条）' },
  { method: 'POST', path: '/api/v1/news/force_refresh', desc: '强制刷新新闻缓存' },
]

const sourceApis = [
  { method: 'GET', path: '/api/v1/source/status', desc: '获取数据源状态和配置' },
  { method: 'GET', path: '/api/v1/source/ping', desc: 'Ping 所有数据源检测连通性' },
  { method: 'GET', path: '/api/v1/source/test', desc: '测试所有数据源（带延迟）' },
  { method: 'POST', path: '/api/v1/source/switch', desc: '切换主数据源' },
  { method: 'GET', path: '/api/v1/source/proxy', desc: '获取当前代理设置' },
  { method: 'POST', path: '/api/v1/source/proxy', desc: '设置代理地址' },
  { method: 'GET', path: '/api/v1/source/alpha_vantage_key', desc: '获取 AlphaVantage API Key' },
  { method: 'POST', path: '/api/v1/source/alpha_vantage_key', desc: '设置 AlphaVantage API Key' },
]

function getSourceStatus(key) {
  return sourceStatus.value.sources[key]?.status || 'unknown'
}

async function refreshStatus() {
  refreshing.value = true
  lastUpdate.value = new Date().toLocaleTimeString('zh-CN')
  try {
    const statusData = await apiFetch('/api/v1/source/status', { timeoutMs: 5000 })
    if (statusData) {
      sourceStatus.value = statusData
    }
    
    // 后台 ping
    apiFetch('/api/v1/source/ping', { timeoutMs: 25000 })
      .then(pingData => {
        if (pingData && sourceStatus.value.sources) {
          for (const [key, val] of Object.entries(pingData)) {
            if (sourceStatus.value.sources[key]) {
              sourceStatus.value.sources[key].status = val.status || 'unknown'
              sourceStatus.value.sources[key].latency = val.latency || null
            }
          }
        }
      })
      .catch(() => {})
  } catch (e) {
    console.warn('刷新失败:', e.message)
  } finally {
    refreshing.value = false
  }
}

async function refreshSystemInfo() {
  loadingSystem.value = true
  try {
    // 获取后端系统信息
    const [statusData, pingData] = await Promise.all([
      apiFetch('/api/v1/source/status', { timeoutMs: 5000 }),
      apiFetch('/api/v1/market/sectors', { timeoutMs: 5000 }),
    ])
    
    systemInfo.sectorsCache = statusData ? 'ready' : 'initializing'
    systemInfo.newsCache = pingData ? 'ready' : 'initializing'
  } catch (e) {
    console.warn('获取系统信息失败:', e.message)
  } finally {
    loadingSystem.value = false
  }
}

async function testAllSources() {
  testing.value = true
  testResults.value = null
  try {
    const data = await apiFetch('/api/v1/source/test?symbol=sh000001', { timeoutMs: 30000 })
    if (data) {
      testResults.value = data
      testTime.value = new Date().toLocaleTimeString('zh-CN')
    }
  } catch (e) {
    console.error('测试失败:', e.message)
    alert('测试失败: ' + e.message)
  } finally {
    testing.value = false
  }
}

async function switchSource(sourceId) {
  try {
    await apiFetch(`/api/v1/source/switch?source=${sourceId}`, { method: 'POST' })
    await refreshStatus()
  } catch (e) {
    console.error('切换失败:', e.message)
    alert('切换失败: ' + (e.message || '请检查网络连接'))
  }
}

async function saveProxy() {
  savingProxy.value = true
  try {
    await apiFetch('/api/v1/source/proxy', {
      method: 'POST',
      body: JSON.stringify({ proxy: proxyAddress.value }),
      headers: { 'Content-Type': 'application/json' }
    })
    editingProxy.value = false
  } catch (e) {
    console.error('保存失败:', e.message)
    alert('保存失败: ' + (e.message || '请检查网络连接'))
  } finally {
    savingProxy.value = false
  }
}

async function saveAlphaVKey() {
  savingKey.value = true
  try {
    await apiFetch('/api/v1/source/alpha_vantage_key', {
      method: 'POST',
      body: JSON.stringify({ api_key: alphaVKey.value }),
      headers: { 'Content-Type': 'application/json' }
    })
    editingAlphaVKey.value = false
  } catch (e) {
    console.error('保存失败:', e.message)
    alert('保存失败: ' + (e.message || '请检查网络连接'))
  } finally {
    savingKey.value = false
  }
}

let refreshTimer = null

onMounted(async () => {
  // 获取版本信息
  try {
    const verData = await apiFetch('/api/v1/system/version', { timeoutMs: 5000 })
    if (verData) {
      version.value = verData.backend || verData.frontend || '0.4.133'
      systemInfo.backendVersion = verData.backend ? `v${verData.backend}` : 'v0.4.137'
      systemInfo.frontendVersion = verData.frontend || '0.4.137'
    }
  } catch (e) {}
  
  await refreshStatus()
  
  // 获取代理设置
  try {
    const data = await apiFetch('/api/v1/source/proxy', { timeoutMs: 5000 })
    if (data?.proxy_url) proxyAddress.value = data.proxy_url
  } catch (e) {}
  
  // 获取 AlphaVantage Key
  try {
    const keyData = await apiFetch('/api/v1/source/alpha_vantage_key', { timeoutMs: 5000 })
    if (keyData?.api_key) alphaVKey.value = keyData.api_key
  } catch (e) {}
  
  refreshTimer = setInterval(refreshStatus, 30000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
