<template>
  <div class="flex h-full">
    <!-- 移动端遮罩 -->
    <div
      v-if="mobileNavOpen"
      class="fixed inset-0 bg-black/50 z-[9998] md:hidden"
      @click="mobileNavOpen = false"
    />
    <!-- 左侧导航 -->
    <aside
      class="border-r border-theme bg-terminal-panel flex-shrink-0 transition-all duration-300 z-[9999] md:relative fixed left-0 top-0 h-full"
      :class="mobileNavOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0 w-64'"
    >
      <div class="p-4 border-b border-theme flex items-center justify-between">
        <div>
          <span class="text-sm font-bold text-terminal-accent">⚙️ 系统管理</span>
          <div class="text-xs text-theme-muted mt-1">v{{ version }}</div>
        </div>
        <button class="md:hidden text-theme-secondary hover:text-theme-primary" @click="mobileNavOpen = false">✕</button>
      </div>
      <div class="px-4 py-2 text-xs text-[var(--color-warning)] bg-[var(--color-warning-bg)]/30">⚠️ 以下功能会影响系统运行，请谨慎操作</div>
      <nav class="py-2">
        <button
          v-for="item in navItems"
          :key="item.id"
          class="w-full flex items-center gap-3 px-4 py-3 text-sm transition-all text-left"
          :class="activeTab === item.id
            ? 'bg-terminal-accent/15 text-terminal-accent border-r-2 border-terminal-accent'
            : 'text-theme-secondary hover:bg-theme-hover hover:text-theme-primary'"
          @click="activeTab = item.id; mobileNavOpen = false"
        >
          <span class="text-base">{{ item.icon }}</span>
          <div class="flex-1">
            <div class="font-medium">{{ item.label }}</div>
            <div class="text-xs text-theme-muted leading-tight">{{ item.desc }}</div>
          </div>
          <span v-if="item.status" class="w-2 h-2 rounded-full flex-shrink-0" :class="item.statusClass"></span>
        </button>
      </nav>
    </aside>

    <!-- 右侧内容 -->
    <main class="flex-1 overflow-auto p-4 md:p-6">
      <!-- 移动端菜单按钮 -->
      <button
        class="md:hidden mb-4 flex items-center gap-2 px-3 py-2 rounded-sm bg-terminal-panel border border-theme-secondary text-theme-primary text-sm"
        @click="mobileNavOpen = true"
      >
        <span>☰</span> 菜单
      </button>

      <!-- 数据源控制 -->
      <DataSourcePanel
        v-if="activeTab === 'sources'"
        :source-status="sourceStatus"
        :probe-data="probeData"
        :source-health-data="sourceHealthData"
        :proxy-url="proxyUrl"
        @refresh="refreshSourceStatus"
        @save-proxy="saveProxy"
        @confirm-action="confirmAction"
        @control-circuit="controlCircuit"
      />

      <!-- 调度器控制 -->
      <SchedulerPanel
        v-else-if="activeTab === 'scheduler'"
        :jobs="schedulerJobs"
        @refresh="refreshScheduler"
        @confirm-action="confirmAction"
        @control-job="controlJob"
      />

      <!-- 进程保活 -->
      <WatchdogPanel
        v-else-if="activeTab === 'watchdog'"
        :status="watchdogStatus"
        :loading="watchdogLoading"
        :error="watchdogError"
        @refresh="refreshWatchdog"
        @toggle="toggleWatchdog"
        @manual-restart="manualRestart"
        @confirm-action="confirmAction"
      />

      <!-- 缓存管理 -->
      <CachePanel
        v-else-if="activeTab === 'cache'"
        :status="cacheStatus"
        @confirm-action="confirmAction"
        @invalidate="invalidateCache"
        @warmup="warmupCache"
      />

      <!-- 数据库管理 -->
      <DatabasePanel
        v-else-if="activeTab === 'database'"
        :status="dbStatus"
        @confirm-action="confirmAction"
        @maintenance="dbMaintenance"
      />

      <!-- 系统监控 -->
      <MonitorPanel
        v-else-if="activeTab === 'monitor'"
        :metrics="systemMetrics"
        @refresh="refreshSystemMetrics"
      />

      <!-- 布局设置 -->
      <LayoutPanel
        v-else-if="activeTab === 'layout'"
        @clear-layout="$emit('clear-layout')"
      />

      <!-- LLM 配置 -->
      <LLMConfigPanel
        v-else-if="activeTab === 'llm'"
        :providers="llmProviders"
        @refresh="loadLlmConfig"
        @test="testLlmConnection"
        @save="saveLlmConfig"
      />

      <!-- API密钥管理 -->
      <AgentTokensPanel
        v-else-if="activeTab === 'agent_tokens'"
        @refresh="refreshAgentTokens"
        @navigate="(tab) => $emit('navigate', tab)"
      />

      <!-- AI工具配置 (MCP) -->
      <McpPanel
        v-else-if="activeTab === 'mcp'"
        @refresh="refreshMcpConfig"
        @navigate="(tab) => $emit('navigate', tab)"
      />

      <!-- 日志查看 -->
      <LogsPanel
        v-else-if="activeTab === 'logs'"
        :logs="logs"
        :log-level="logLevel"
        :ws-connected="wsConnected"
        @refresh="refreshLogs"
        @update:logLevel="logLevel = $event"
      />
    </main>

    <!-- 确认对话框 -->
    <div v-if="showConfirm" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-terminal-panel border border-theme rounded-sm p-6 max-w-md w-full mx-4">
        <h3 class="text-lg font-bold text-theme-primary mb-2">⚠️ 确认操作</h3>
        <p class="text-sm text-theme-secondary mb-4">{{ confirmMessage }}</p>
        <div class="flex gap-3 justify-end">
          <button
            class="px-4 py-2 bg-theme-secondary/50 text-theme-secondary rounded-sm text-sm cursor-not-allowed"
            :class="{ 'opacity-50': isSubmitting }"
            :disabled="isSubmitting"
            @click="showConfirm = false"
          >取消</button>
          <button
            class="px-4 py-2 bg-[var(--color-danger-bg)] text-[var(--color-danger)] rounded-sm text-sm"
            :class="{ 'opacity-50 cursor-not-allowed': isSubmitting }"
            :disabled="isSubmitting"
            @click="executeConfirm"
          >
            <span v-if="isSubmitting">执行中...</span>
            <span v-else>确定执行</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, watch, computed } from 'vue'
import { logger } from '../utils/logger.js'
import { apiFetch } from '../utils/api.js'
import { toast } from '../composables/useToast.js'

// Import sub-components
import DataSourcePanel from './admin/DataSourcePanel.vue'
import SchedulerPanel from './admin/SchedulerPanel.vue'
import WatchdogPanel from './admin/WatchdogPanel.vue'
import CachePanel from './admin/CachePanel.vue'
import DatabasePanel from './admin/DatabasePanel.vue'
import MonitorPanel from './admin/MonitorPanel.vue'
import LLMConfigPanel from './admin/LLMConfigPanel.vue'
import LogsPanel from './admin/LogsPanel.vue'
import AgentTokensPanel from './admin/AgentTokensPanel.vue'
import McpPanel from './admin/McpPanel.vue'
import LayoutPanel from './admin/LayoutPanel.vue'

const emit = defineEmits(['navigate', 'clear-layout'])

const version = __APP_VERSION__
const activeTab = ref('sources')
const mobileNavOpen = ref(false)
const logLevel = ref('ALL')
const proxyUrl = ref('')
const probeData = ref(null)

// Placeholder functions for agent_tokens and mcp
function refreshAgentTokens() {
  toast.info('提示', '请切换到主界面的API密钥管理模块')
}

function refreshMcpConfig() {
  toast.info('提示', '请切换到主界面的AI工具配置模块')
}

const navItems = [
  { id: 'sources', label: '数据源', desc: '控制行情数据来源的熔断和恢复', icon: '📡', status: true, statusClass: 'bg-[var(--color-success-light)]' },
  { id: 'scheduler', label: '定时任务', desc: '管理自动数据更新任务的启停', icon: '⏱️', status: true, statusClass: 'bg-[var(--color-success-light)]' },
  { id: 'watchdog', label: '进程保活', desc: '监控后端进程状态，自动重启', icon: '🛡️', status: true, statusClass: 'bg-[var(--color-success-light)]' },
  { id: 'cache', label: '缓存管理', desc: '清理和预热系统数据缓存', icon: '💾', status: true, statusClass: 'bg-[var(--color-success-light)]' },
  { id: 'database', label: '数据库', desc: 'SQLite数据库维护和优化', icon: '🗄️', status: true, statusClass: 'bg-[var(--color-success-light)]' },
  { id: 'monitor', label: '系统监控', desc: '查看服务器CPU内存等资源使用', icon: '📊', status: true, statusClass: 'bg-[var(--color-success-light)]' },
  { id: 'layout', label: '布局设置', desc: '管理仪表盘布局和组件位置', icon: '📐', status: true, statusClass: 'bg-[var(--color-success-light)]' },
  { id: 'llm', label: '模型配置', desc: 'LLM API Key 和连接配置', icon: '🤖', status: true, statusClass: 'bg-[var(--color-success-light)]' },
  { id: 'agent_tokens', label: 'API密钥', desc: '管理Agent和第三方API密钥', icon: '🔑', status: true, statusClass: 'bg-[var(--color-success-light)]' },
  { id: 'mcp', label: 'AI工具配置', desc: '配置MCP工具和外部服务', icon: '🔌', status: true, statusClass: 'bg-[var(--color-success-light)]' },
  { id: 'logs', label: '日志查看', desc: '查看系统运行日志和错误信息', icon: '📝', status: false, statusClass: 'bg-gray-400' },
]

// ── 确认对话框 ──────────────────────────────────────────────────────────
const showConfirm = ref(false)
const confirmMessage = ref('')
const confirmCallback = ref(null)
const isSubmitting = ref(false)

function confirmAction(title, message, callback) {
  confirmMessage.value = message
  confirmCallback.value = callback
  showConfirm.value = true
}

async function executeConfirm() {
  if (!confirmCallback.value) return
  if (isSubmitting.value) return
  isSubmitting.value = true
  try {
    await confirmCallback.value()
  } finally {
    isSubmitting.value = false
    showConfirm.value = false
  }
}

// ── 数据源状态 ──────────────────────────────────────────────────────────
const sourceStatus = reactive({
  sources: {
    tencent: { state: 'unknown', fail_count: 0, latency_ms: null, health: 'unknown', description: '腾讯财经 - 主数据源' },
    sina_kline: { state: 'unknown', fail_count: 0, latency_ms: null, health: 'unknown', description: '新浪K线 - 备用源' },
    sina: { state: 'unknown', fail_count: 0, latency_ms: null, health: 'unknown', description: '新浪财经 - 备用源' },
    eastmoney: { state: 'unknown', fail_count: 0, latency_ms: null, health: 'unknown', description: '东方财富 - 备用源' },
    tencent_hk: { state: 'unknown', fail_count: 0, latency_ms: null, health: 'unknown', description: '腾讯港股 - 备用源' },
    alpha_vantage: { state: 'unknown', fail_count: 0, latency_ms: null, health: 'unknown', description: 'AlphaVantage - 美股源' }
  }
})

const sourceHealthData = ref({})

// ── 调度器 ──────────────────────────────────────────────────────────
const schedulerJobs = ref([])

// ── 缓存状态 ──────────────────────────────────────────────────────────
const cacheStatus = reactive({ market: 5497, sectors: 20, news: 150, db: 22 })

// ── 数据库状态 ──────────────────────────────────────────────────────────
const dbStatus = reactive({ size: '12.5', realtime: 22, daily: 12500, stocks: 5497 })

// ── 系统监控 ──────────────────────────────────────────────────────────
const systemMetrics = reactive({
  cpu_percent: 5.4,
  memory: { percent: 56.2, used_gb: 4.3, total_gb: 7.65 },
  disk: { percent: 29.0, used_gb: 17.22, total_gb: 62.6 },
  process: { memory_mb: 167, threads: 12 },
  network: { connections: 471, io_counters: { bytes_sent: 74188244056, bytes_recv: 82540093634 } }
})

// ── Watchdog 进程保活 ──────────────────────────────────────────────────────────
const watchdogStatus = reactive({
  enabled: false,
  running: false,
  last_check: null,
  last_restart: null,
  restart_count: 0,
  total_restarts: 0,
  recent_errors: []
})
const watchdogLoading = ref(false)
const watchdogError = ref(null)

// ── 日志数据 + WebSocket 实时流 ──────────────────────────────────────────────────
const MAX_LOGS = 300
const logs = ref([])
let ws = null
let wsConnected = false

function buildWsUrl() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/api/v1/admin/logs/stream`
}

function pushLog(log) {
  logs.value.push(log)
  if (logs.value.length > MAX_LOGS) logs.value.shift()
}

function connectLogWs() {
  if (ws) {
    ws.close()
    ws = null
  }
  try {
    ws = new WebSocket(buildWsUrl())
    ws.onopen = () => {
      wsConnected = true
      logger.info('[WS] Log stream connected')
    }
    ws.onmessage = (evt) => {
      try {
        const log = JSON.parse(evt.data)
        if (log.level === 'HEARTBEAT') return
        pushLog(log)
      } catch { /* ignore parse errors */ }
    }
    ws.onerror = (e) => { logger.warn('[WS] Log stream error', e) }
    ws.onclose = () => {
      wsConnected = false
      ws = null
    }
  } catch (e) { logger.warn('[WS] Log stream connect failed', e) }
}

function disconnectLogWs() {
  if (ws) { ws.close(); ws = null; wsConnected = false }
}

// 切换到 logs tab 时建立 WS
watch(activeTab, (tab) => {
  if (tab === 'logs' && !wsConnected) connectLogWs()
  else if (tab !== 'logs') disconnectLogWs()
  if (tab === 'sources') refreshSourceHealth()
})

onUnmounted(() => { disconnectLogWs() })

// ── LLM 配置 ──────────────────────────────────────────────────────────
const llmProviders = reactive({
  deepseek: {
    label: 'DeepSeek', icon: '🧠', desc: 'DeepSeek-V3 / DeepSeek-R1',
    default_base: 'https://api.deepseek.com', default_model: 'deepseek-chat',
    api_key: '', base_url: '', model: '', has_db_config: false,
    input_key: '', input_base: '', input_model: '',
    show_key: false, saving: false, testing: false, message: '', message_ok: false,
    show_model_info: false,
    modelGroups: [
      { label: '💬 对话模型 (Chat)', models: [
        { id: 'deepseek-chat', name: 'DeepSeek V3', pricing: '¥2-6/百万Token', finance: '金融分析强，逻辑推理优秀，支持长上下文32K' },
        { id: 'deepseek-reasoner', name: 'DeepSeek R1', pricing: '¥16-32/百万Token', finance: '深度推理能力强，适合复杂金融决策场景' },
      ]},
      { label: '🔧 专用模型', models: [
        { id: 'deepseek-coder', name: 'DeepSeek Coder', pricing: '¥2-6/百万Token', finance: '代码能力突出，可辅助量化策略开发' },
      ]}
    ],
  },
  qianwen: {
    label: '通义千问', icon: '🌐', desc: 'Qwen Plus / Max / VL',
    default_base: 'https://dashscope.aliyuncs.com/compatible-mode/v1', default_model: 'qwen-plus',
    api_key: '', base_url: '', model: '', has_db_config: false,
    input_key: '', input_base: '', input_model: '',
    show_key: false, saving: false, testing: false, message: '', message_ok: false,
    show_model_info: false,
    modelGroups: [
      { label: '💬 对话模型 (Chat)', models: [
        { id: 'qwen-plus', name: 'Qwen Plus', pricing: '¥0.04-0.12/千Token', finance: '中文理解强，股市新闻分析速度快' },
        { id: 'qwen-max', name: 'Qwen Max', pricing: '¥0.2-0.6/千Token', finance: '旗舰模型，金融研报综合分析能力强' },
        { id: 'qwen-turbo', name: 'Qwen Turbo', pricing: '¥0.015-0.045/千Token', finance: '快速响应，适合实时行情解读' },
      ]},
      { label: '👁️ 视觉模型 (VL)', models: [
        { id: 'qwen-vl-plus', name: 'Qwen VL Plus', pricing: '¥0.06-0.18/千Token', finance: '可解析K线图、财报图片等视觉信息' },
      ]}
    ],
  },
  openai: {
    label: 'OpenAI', icon: '🤖', desc: 'GPT-3.5 / GPT-4 / GPT-4o',
    default_base: 'https://api.openai.com/v1', default_model: 'gpt-3.5-turbo',
    api_key: '', base_url: '', model: '', has_db_config: false,
    input_key: '', input_base: '', input_model: '',
    show_key: false, saving: false, testing: false, message: '', message_ok: false,
    show_model_info: false,
    modelGroups: [
      { label: '💬 对话模型 (Chat)', models: [
        { id: 'gpt-4o', name: 'GPT-4o', pricing: '$6-18/百万Token', finance: '综合能力最强，多模态支持好，国际市场分析首选' },
        { id: 'gpt-4-turbo', name: 'GPT-4 Turbo', pricing: '$10-30/百万Token', finance: '上下文128K，适合长篇金融报告分析' },
        { id: 'gpt-3.5-turbo', name: 'GPT-3.5 Turbo', pricing: '$0.5-1.5/百万Token', finance: '低成本快速响应，适合简单行情查询' },
      ]},
      { label: '🎨 视觉模型 (Vision)', models: [
        { id: 'gpt-4o-mini', name: 'GPT-4o Mini', pricing: '$0.15-0.6/百万Token', finance: '性价比高，轻量级图表解析' },
      ]}
    ],
  },
  siliconflow: {
    label: '硅基流动', icon: '💎', desc: 'SiliconFlow - DeepSeek/Qwen 等模型聚合平台',
    default_base: 'https://api.siliconflow.cn/v1', default_model: 'deepseek-ai/DeepSeek-V3',
    api_key: '', base_url: '', model: '', has_db_config: false,
    input_key: '', input_base: '', input_model: '',
    show_key: false, saving: false, testing: false, message: '', message_ok: false,
    show_model_info: false,
    modelGroups: [
      { label: '🔥 热门模型', models: [
        { id: 'deepseek-ai/DeepSeek-V3', name: 'DeepSeek V3 (SF)', pricing: '¥1-3/百万Token', finance: '性价比极高，金融分析首选', best_for: '⭐ 性价比之选' },
        { id: 'deepseek-ai/DeepSeek-R1', name: 'DeepSeek R1 (SF)', pricing: '¥6-18/百万Token', finance: '深度推理强，复杂量化策略分析' },
        { id: 'Qwen/Qwen2.5-72B-Instruct', name: 'Qwen2.5-72B', pricing: '¥2-8/百万Token', finance: '中文理解出色，财报解读快速' },
      ]},
      { label: '🆓 Free模型 (硅基流动)', models: [
        { id: 'Pro/Qwen2.5-7B-Instruct', name: 'Qwen2.5-7B (Free)', pricing: '🆓 免费', finance: '免费额度充足，日常行情分析完全够用', best_for: '⭐ 免费首选' },
        { id: 'Pro/Qwen2.5-14B-Instruct', name: 'Qwen2.5-14B (Free)', pricing: '🆓 免费', finance: '更强理解力，复杂财经新闻解读' },
        { id: 'Pro/deepseek-ai/DeepSeek-V3', name: 'DeepSeek V3 (Free)', pricing: '🆓 免费', finance: '免费版DeepSeek V3，金融分析无压力' },
        { id: 'Pro/THUDM/glm-4-flash', name: 'GLM-4-Flash (Free)', pricing: '🆓 免费', finance: '极速响应，实时K线解读无延迟' },
        { id: 'Pro/Qwen/Qwen2.5-32B-Instruct', name: 'Qwen2.5-32B (Free)', pricing: '🆓 免费', finance: '中等规模，完全免费，财报分析' },
      ]},
      { label: '💰 低价模型', models: [
        { id: 'THUDM/glm-4-flash', name: 'GLM-4-Flash', pricing: '¥0.1-0.3/百万Token', finance: '超低价格，适合高频行情查询' },
        { id: 'Qwen/Qwen2.5-7B-Instruct', name: 'Qwen2.5-7B', pricing: '¥0.3-1/百万Token', finance: '轻量快速，实时K线解读' },
      ]}
    ],
  },
  opencode_go: {
    label: 'OpenCode Go', icon: '🚀', desc: 'OpenCode Go - 开源编程模型订阅服务（首月$5，之后$10/月）',
    default_base: 'https://opencode.ai/zen/go/v1', default_model: 'opencode-go/minimax-m2.7',
    api_key: '', base_url: '', model: '', has_db_config: false,
    input_key: '', input_base: '', input_model: '',
    show_key: false, saving: false, testing: false, message: '', message_ok: false,
    show_model_info: false,
    modelGroups: [
      { label: '🤖 旗舰模型', models: [
        { id: 'opencode-go/glm-5.1', name: 'GLM-5.1', pricing: '$10/月订阅', finance: '最新旗舰，开源最强编程模型' },
        { id: 'opencode-go/glm-5', name: 'GLM-5', pricing: '$10/月订阅', finance: '高性能开源编程模型' },
        { id: 'opencode-go/kimi-k2.6', name: 'Kimi K2.6', pricing: '$10/月订阅', finance: 'Kimi旗舰，开源编程能力强' },
        { id: 'opencode-go/kimi-k2.5', name: 'Kimi K2.5', pricing: '$10/月订阅', finance: '高性价比，编程任务首选' },
      ]},
      { label: '🔵 MiniMax 系列', models: [
        { id: 'opencode-go/minimax-m2.7', name: 'MiniMax M2.7', pricing: '$10/月订阅', finance: '当前模型，高性能低成本', best_for: '⭐ 推荐' },
        { id: 'opencode-go/minimax-m2.5', name: 'MiniMax M2.5', pricing: '$10/月订阅', finance: '最高请求额度，约3.3万次/月', best_for: '⭐ 高频使用首选' },
      ]},
      { label: '💚 Qwen 系列', models: [
        { id: 'opencode-go/qwen3.6-plus', name: 'Qwen3.6 Plus', pricing: '$10/月订阅', finance: '中文理解强，约1.6万次/月' },
        { id: 'opencode-go/qwen3.5-plus', name: 'Qwen3.5 Plus', pricing: '$10/月订阅', finance: '最高请求额度，约5万次/月', best_for: '⭐ 最高性价比' },
      ]},
      { label: '🔷 MiMo 系列', models: [
        { id: 'opencode-go/mimo-v2.5', name: 'MiMo-V2.5', pricing: '$10/月订阅', finance: '高请求额度，约1万次/月' },
        { id: 'opencode-go/mimo-v2-pro', name: 'MiMo-V2-Pro', pricing: '$10/月订阅', finance: '编程能力强' },
        { id: 'opencode-go/mimo-v2-omni', name: 'MiMo-V2-Omni', pricing: '$10/月订阅', finance: '全能型，高请求额度' },
        { id: 'opencode-go/mimo-v2.5-pro', name: 'MiMo-V2.5-Pro', pricing: '$10/月订阅', finance: '专业版编程模型' },
      ]},
      { label: '🟣 DeepSeek 系列', models: [
        { id: 'opencode-go/deepseek-v4-pro', name: 'DeepSeek V4 Pro', pricing: '$10/月订阅', finance: '高性能推理，约1.7万次/月' },
        { id: 'opencode-go/deepseek-v4-flash', name: 'DeepSeek V4 Flash', pricing: '$10/月订阅', finance: '最高请求额度，约15.8万次/月', best_for: '⭐ 超高频首选' },
      ]},
    ],
  },
  opencode_zen: {
    label: 'OpenCode Zen', icon: '⚡', desc: 'OpenCode Zen - 精选模型付费网关（含大量免费额度）',
    default_base: 'https://opencode.ai/zen/v1', default_model: 'opencode/minimax-m2.7',
    api_key: '', base_url: '', model: '', has_db_config: false,
    input_key: '', input_base: '', input_model: '',
    show_key: false, saving: false, testing: false, message: '', message_ok: false,
    show_model_info: false,
    modelGroups: [
      { label: '🆓 免费模型 (Zen)', models: [
        { id: 'opencode/big-pickle', name: 'Big Pickle', pricing: '🆓 完全免费', finance: '限时免费，隐身模型，日常分析首选', best_for: '⭐ 完全免费首选' },
        { id: 'opencode/minimax-m2.5-free', name: 'MiniMax M2.5 Free', pricing: '🆓 免费', finance: '限时免费，国产高性能模型' },
        { id: 'opencode/ling-2.6-flash', name: 'Ling 2.6 Flash', pricing: '🆓 免费', finance: '限时免费，极速响应' },
        { id: 'opencode/hy3-preview-free', name: 'Hy3 Preview', pricing: '🆓 免费', finance: '限时免费，预览版本' },
        { id: 'opencode/nemotron-3-super-free', name: 'Nemotron 3 Super', pricing: '🆓 免费', finance: 'NVIDIA提供，免费额度' },
        { id: 'opencode/gpt-5-nano', name: 'GPT-5 Nano', pricing: '🆓 免费', finance: 'OpenAI免费模型，轻量快速' },
      ]},
      { label: '💬 GPT-5 系列 (Zen)', models: [
        { id: 'opencode/gpt-5.5', name: 'GPT 5.5', pricing: '$5-45/百万Token', finance: '最新旗舰，≤272K: $5 in/$30 out', best_for: '⭐ 综合最强' },
        { id: 'opencode/gpt-5.5-pro', name: 'GPT 5.5 Pro', pricing: '$30-180/百万Token', finance: 'GPT-5.5专业版，性能最强' },
        { id: 'opencode/gpt-5.4', name: 'GPT 5.4', pricing: '$2.5-22.5/百万Token', finance: '≤272K: $2.5 in/$15 out，高性价比' },
        { id: 'opencode/gpt-5.4-pro', name: 'GPT 5.4 Pro', pricing: '$30-180/百万Token', finance: 'GPT-5.4专业版' },
        { id: 'opencode/gpt-5.4-mini', name: 'GPT 5.4 Mini', pricing: '$0.75-4.5/百万Token', finance: '轻量高性价比，日常分析首选' },
        { id: 'opencode/gpt-5.4-nano', name: 'GPT 5.4 Nano', pricing: '$0.2-1.25/百万Token', finance: '超低成本，简单查询' },
        { id: 'opencode/gpt-5.3-codex-spark', name: 'GPT 5.3 Codex Spark', pricing: '$1.75-14/百万Token', finance: '代码能力增强版' },
        { id: 'opencode/gpt-5.3-codex', name: 'GPT 5.3 Codex', pricing: '$1.75-14/百万Token', finance: '代码专用模型' },
        { id: 'opencode/gpt-5.2', name: 'GPT 5.2', pricing: '$1.75-14/百万Token', finance: '高性能代码模型' },
        { id: 'opencode/gpt-5.1', name: 'GPT 5.1', pricing: '$1.07-8.5/百万Token', finance: '稳定版代码模型' },
        { id: 'opencode/gpt-5', name: 'GPT 5', pricing: '$1.07-8.5/百万Token', finance: '基础版GPT-5' },
      ]},
      { label: '🧠 Claude 系列 (Zen)', models: [
        { id: 'opencode/claude-opus-4-7', name: 'Claude Opus 4.7', pricing: '$5-25/百万Token', finance: '最强推理，复杂金融决策', best_for: '⭐ 推理最强' },
        { id: 'opencode/claude-opus-4-6', name: 'Claude Opus 4.6', pricing: '$5-25/百万Token', finance: '旗舰推理模型' },
        { id: 'opencode/claude-opus-4-5', name: 'Claude Opus 4.5', pricing: '$5-25/百万Token', finance: '高性能推理' },
        { id: 'opencode/claude-opus-4-1', name: 'Claude Opus 4.1', pricing: '$15-75/百万Token', finance: '超长上下文推理' },
        { id: 'opencode/claude-sonnet-4-6', name: 'Claude Sonnet 4.6', pricing: '$3-15/百万Token', finance: '平衡之选，代码分析兼备' },
        { id: 'opencode/claude-sonnet-4-5', name: 'Claude Sonnet 4.5', pricing: '$3-15/百万Token', finance: '≤200K: $3 in/$15 out' },
        { id: 'opencode/claude-haiku-4-5', name: 'Claude Haiku 4.5', pricing: '$1-5/百万Token', finance: '快速响应，实时行情解读' },
      ]},
      { label: '🌟 Gemini 系列 (Zen)', models: [
        { id: 'opencode/gemini-3.1-pro', name: 'Gemini 3.1 Pro', pricing: '$2-18/百万Token', finance: '≤200K: $2 in/$12 out，上下文128K' },
        { id: 'opencode/gemini-3-flash', name: 'Gemini 3 Flash', pricing: '$0.5-3/百万Token', finance: '快速低价，实时K线解读' },
      ]},
      { label: '🇨🇳 国产模型 (Zen)', models: [
        { id: 'opencode/minimax-m2.7', name: 'MiniMax M2.7', pricing: '$0.30-1.2/百万Token', finance: '当前模型，高性能低成本' },
        { id: 'opencode/minimax-m2.5', name: 'MiniMax M2.5', pricing: '$0.30-1.2/百万Token', finance: '高性价比，国产首选' },
        { id: 'opencode/qwen3.6-plus', name: 'Qwen3.6 Plus', pricing: '$0.50-3/百万Token', finance: '中文理解强，财报解读' },
        { id: 'opencode/qwen3.5-plus', name: 'Qwen3.5 Plus', pricing: '$0.20-1.2/百万Token', finance: '高性价比，中文场景' },
        { id: 'opencode/kimi-k2.6', name: 'Kimi K2.6', pricing: '$0.95-4/百万Token', finance: '长上下文优秀，旗舰模型' },
        { id: 'opencode/kimi-k2.5', name: 'Kimi K2.5', pricing: '$0.60-3/百万Token', finance: '高性价比，编程能力强' },
        { id: 'opencode/glm-5.1', name: 'GLM-5.1', pricing: '$1.40-4.4/百万Token', finance: '国产旗舰，开源最强编程模型' },
        { id: 'opencode/glm-5', name: 'GLM-5', pricing: '$1.00-3.2/百万Token', finance: '国产高性能，开源模型' },
      ]},
    ],
  },
})

// ── API Functions ──────────────────────────────────────────────────────────

async function loadLlmConfig() {
  try {
    const res = await fetch('/api/v1/admin/settings/llm')
    const json = await res.json()
    if (json.code !== 0) return
    for (const [p, data] of Object.entries(json.data)) {
      const cfg = llmProviders[p]
      if (!cfg) continue
      cfg.api_key  = data.api_key || ''
      cfg.base_url = data.base_url || cfg.default_base
      cfg.model    = data.model || cfg.default_model
      cfg.has_db_config = data.has_db_config || false
      cfg.input_key  = data.api_key || ''
      cfg.input_base = data.base_url || cfg.default_base
      cfg.input_model = data.model || cfg.default_model
      cfg.message = ''
    }
  } catch (e) { console.error('[Admin] loadLlmConfig:', e) }
}

async function saveLlmConfig(provider) {
  const cfg = llmProviders[provider]
  cfg.saving = true; cfg.message = ''
  try {
    const res = await fetch('/api/v1/admin/settings/llm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, api_key: cfg.input_key, base_url: cfg.input_base, model: cfg.input_model }),
    })
    const json = await res.json()
    if (json.code === 0) {
      cfg.has_db_config = true; cfg.api_key = cfg.input_key; cfg.base_url = cfg.input_base; cfg.model = cfg.input_model
      cfg.message = '✅ 已保存'; cfg.message_ok = true
      setTimeout(() => { cfg.message = '' }, 4000)
    } else { cfg.message = '❌ ' + (json.error || '保存失败'); cfg.message_ok = false }
  } catch (e) { cfg.message = '❌ ' + e.message; cfg.message_ok = false }
  finally { cfg.saving = false }
}

async function testLlmConnection(provider) {
  const cfg = llmProviders[provider]
  if (!cfg.input_key) { cfg.message = '⚠️ 请先输入 API Key'; return }
  cfg.testing = true; cfg.message = ''
  try {
    const res = await fetch('/api/v1/admin/settings/llm/test', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, api_key: cfg.input_key, base_url: cfg.input_base, model: cfg.input_model }),
    })
    const json = await res.json()
    cfg.message = json.code === 0 ? '✅ 连接成功' : '❌ ' + (json.error || '连接失败')
    cfg.message_ok = json.code === 0
    setTimeout(() => { cfg.message = '' }, 6000)
  } catch (e) { cfg.message = '❌ ' + e.message; cfg.message_ok = false }
  finally { cfg.testing = false }
}

async function refreshSourceHealth() {
  try {
    const [statusData, configData] = await Promise.all([
      apiFetch('/api/v1/admin/sources/status'),
      apiFetch('/api/v1/admin/data-sources'),
    ])
    const sources = statusData?.data?.sources || statusData?.sources || {}
    const converted = {}
    for (const [key, info] of Object.entries(sources)) {
      converted[key] = {
        status: info.status === 'ok' ? 'ok' : 'error',
        latency_ms: info.latency || 0,
        fail_count: info.fail_count || 0,
      }
    }
    sourceHealthData.value = converted
  } catch (e) {
    logger.error('[SourceHealth] refresh failed:', e)
  }
}

async function refreshLogs() {
  try {
    const data = await apiFetch('/api/v1/admin/logs/recent?lines=100')
    if (data?.logs) {
      logs.value = data.logs.slice(0, MAX_LOGS)
    }
  } catch (e) { logger.error('Refresh logs failed:', e) }
}

async function refreshSourceStatus() {
  try {
    const data = await apiFetch('/api/v1/admin/sources/probe', { method: 'POST' })
    probeData.value = data

    if (data?.sources) {
      for (const [key, result] of Object.entries(data.sources)) {
        if (!sourceStatus.sources[key]) sourceStatus.sources[key] = {}
        sourceStatus.sources[key].latency_ms = result.latency ?? null
        sourceStatus.sources[key].health = result.status === 'ok' ? 'healthy' : 'unhealthy'
        sourceStatus.sources[key].state = result.state || (result.status === 'ok' ? 'closed' : 'open')
        sourceStatus.sources[key].fail_count = result.fail_count ?? 0
        sourceStatus.sources[key].status = result.status
        sourceStatus.sources[key].is_primary = result.is_primary ?? false
        sourceStatus.sources[key].history = result.history ?? []
      }
    }
  } catch (e) { logger.error('刷新失败:', e) }
}

async function saveProxy(url) {
  try {
    const fullProxy = url.startsWith('http') ? url : `http://${url}`
    await apiFetch('/api/v1/source/proxy', {
      method: 'POST',
      body: JSON.stringify({ proxy: fullProxy })
    })
    toast.success('代理配置已保存，重启服务后生效')
  } catch (e) { toast.error('代理配置失败: ' + e.message) }
}

async function controlCircuit(source, action) {
  try {
    const data = await apiFetch('/api/v1/admin/sources/circuit_breaker', {
      method: 'POST',
      body: JSON.stringify({ source, action })
    })
    toast.success(data?.message || (action === 'open' ? '熔断成功' : '恢复成功'))
    await refreshSourceStatus()
  } catch (e) { alert('操作失败: ' + e.message) }
}

async function refreshScheduler() {
  try {
    const data = await apiFetch('/api/v1/admin/scheduler/jobs')
    if (data?.jobs) schedulerJobs.value = data.jobs
  } catch (e) { logger.error('刷新失败:', e) }
}

async function controlJob(jobId, action) {
  try {
    await apiFetch(`/api/v1/admin/scheduler/jobs/${jobId}/control`, {
      method: 'POST',
      body: JSON.stringify({ action })
    })
    await refreshScheduler()
  } catch (e) { alert('操作失败: ' + e.message) }
}

async function invalidateCache(type) {
  try {
    await apiFetch('/api/v1/admin/cache/invalidate', {
      method: 'POST',
      body: JSON.stringify({ cache_type: type })
    })
    alert('缓存已清空')
  } catch (e) { alert('操作失败: ' + e.message) }
}

async function warmupCache(type) {
  try {
    await apiFetch('/api/v1/admin/cache/warmup', {
      method: 'POST',
      body: JSON.stringify({ data_type: type })
    })
    alert('缓存预热已启动')
  } catch (e) { alert('操作失败: ' + e.message) }
}

async function refreshWatchdog() {
  watchdogLoading.value = true
  watchdogError.value = null
  try {
    const rawData = await apiFetch('/api/v1/admin/watchdog/status')
    const data = rawData && rawData.code !== undefined ? rawData.data ?? rawData : rawData
    if (data && typeof data.enabled === 'boolean') {
      watchdogStatus.enabled = data.enabled ?? false
      watchdogStatus.running = data.running ?? false
      watchdogStatus.last_check = data.last_check ?? null
      watchdogStatus.last_restart = data.last_restart ?? null
      watchdogStatus.restart_count = data.restart_count ?? 0
      watchdogStatus.total_restarts = data.total_restarts ?? 0
      watchdogStatus.recent_errors = data.recent_errors ?? []
    } else {
      watchdogError.value = '响应格式错误: ' + JSON.stringify(data)
    }
  } catch (e) {
    logger.error('[Watchdog] Refresh error:', e)
    watchdogError.value = e.message || '加载失败'
  } finally {
    watchdogLoading.value = false
  }
}

async function toggleWatchdog(enabled) {
  try {
    watchdogLoading.value = true
    watchdogStatus.enabled = enabled
    
    await apiFetch('/api/v1/admin/watchdog/toggle', {
      method: 'POST',
      body: JSON.stringify({ enabled })
    })
    
    setTimeout(async () => {
      await refreshWatchdog()
    }, 500)
    
    alert(enabled ? '进程保活已启用' : '进程保活已禁用')
  } catch (e) {
    logger.error('[Watchdog] Toggle failed:', e)
    watchdogError.value = e.message || '切换失败'
    await refreshWatchdog()
    alert('操作失败: ' + e.message)
  } finally {
    watchdogLoading.value = false
  }
}

async function manualRestart() {
  try {
    watchdogLoading.value = true
    await apiFetch('/api/v1/admin/watchdog/restart', { method: 'POST' })
    alert('后端重启指令已发送，请等待 5-10 秒后刷新页面')
    setTimeout(async () => {
      await refreshWatchdog()
    }, 3000)
  } catch (e) {
    watchdogError.value = e.message || '重启失败'
    alert('重启失败: ' + e.message)
  } finally {
    watchdogLoading.value = false
  }
}

async function dbMaintenance(action) {
  try {
    await apiFetch('/api/v1/admin/database/maintenance', {
      method: 'POST',
      body: JSON.stringify({ action })
    })
    alert('维护操作已执行')
  } catch (e) { alert('操作失败: ' + e.message) }
}

async function refreshDbStatus() {
  try {
    const data = await apiFetch('/api/v1/admin/database/stats')
    if (data) {
      dbStatus.size = data.db_size_mb || 0
      dbStatus.realtime = data.tables?.market_data_realtime || 0
      dbStatus.daily = data.tables?.market_data_daily || 0
      dbStatus.stocks = data.tables?.market_all_stocks || 0
    }
  } catch (e) { logger.error('Refresh db status failed:', e) }
}

async function refreshSystemMetrics() {
  try {
    const data = await apiFetch('/api/v1/admin/system/metrics')
    if (data) Object.assign(systemMetrics, data)
  } catch (e) { logger.error('Refresh failed:', e) }
}

// ── Lifecycle Hooks ──────────────────────────────────────────────────────────

onMounted(() => {
  refreshSourceStatus()
  refreshScheduler()
  refreshSystemMetrics()
  refreshLogs()
  refreshDbStatus()
  loadLlmConfig()
  refreshWatchdog().catch(e => logger.error('[AdminDashboard] refreshWatchdog failed:', e))
})
</script>
