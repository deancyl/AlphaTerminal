<template>
  <div class="flex h-full">
    <div
      v-if="mobileNavOpen"
      class="fixed inset-0 bg-black/50 z-[9998] md:hidden"
      @click="mobileNavOpen = false"
    />
    <aside
      class="border-r border-theme bg-terminal-panel flex-shrink-0 transition-all duration-300 z-[9999] md:relative fixed left-0 top-0 h-full"
      :class="mobileNavOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0 w-64'"
    >
      <div class="p-4 border-b border-theme flex items-center justify-between">
        <div>
          <span class="text-sm font-bold text-terminal-accent">🔌 MCP Server</span>
          <div class="text-xs text-theme-muted mt-1">v1.0.0</div>
        </div>
        <button class="md:hidden text-theme-secondary hover:text-theme-primary" @click="mobileNavOpen = false">✕</button>
      </div>
      <div class="px-4 py-2 text-xs text-[var(--color-info)] bg-[var(--color-info-bg)]/30">ℹ️ MCP Server Configuration for AI Agent Integration</div>
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

    <main class="flex-1 overflow-auto p-4 md:p-6">
      <button
        class="md:hidden mb-4 flex items-center gap-2 px-3 py-2 rounded-sm bg-terminal-panel border border-theme-secondary text-theme-primary text-sm"
        @click="mobileNavOpen = true"
      >
        <span>☰</span> 菜单
      </button>

      <!-- Server Status -->
      <div v-if="activeTab === 'status'" class="space-y-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-bold text-theme-primary">📊 Server Status</h2>
            <p class="text-xs text-theme-muted mt-1">Monitor MCP server health and performance</p>
          </div>
          <button class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm" @click="refreshStatus">🔄 Refresh</button>
        </div>

        <div class="p-4 bg-[var(--info-bg)] border border-[var(--color-info-border)] rounded-sm">
          <h3 class="text-sm font-bold text-[var(--color-info)] mb-2">💡 What is MCP?</h3>
          <p class="text-xs text-theme-secondary leading-relaxed">
            <strong class="text-terminal-accent">Model Context Protocol (MCP)</strong> is a protocol for AI agents to interact with external tools and data sources.
            QuantDinger MCP Server provides financial data access, technical analysis, and trading capabilities.
          </p>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div class="p-4 rounded-sm border" :class="serverStatus.running ? 'bg-[var(--color-success-bg)] border-[var(--color-success-border)]' : 'bg-[var(--color-danger-bg)] border-[var(--color-danger-border)]'">
            <div class="flex items-center justify-between mb-3">
              <span class="font-medium text-theme-primary">Server Status</span>
              <span class="w-3 h-3 rounded-full" :class="serverStatus.running ? 'bg-[var(--color-success-light)] animate-pulse' : 'bg-[var(--color-danger-light)]'"></span>
            </div>
            <div class="text-2xl font-bold" :class="serverStatus.running ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]'">
              {{ serverStatus.running ? 'Running' : 'Stopped' }}
            </div>
            <div class="text-[10px] text-theme-muted mt-1">
              {{ serverStatus.running ? 'Server is operational' : 'Server is not running' }}
            </div>
          </div>

          <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">Uptime</div>
            <div class="text-xl font-bold text-terminal-accent">
              {{ formatUptime(serverStatus.uptime) }}
            </div>
            <div class="text-[10px] text-theme-muted mt-1">
              Last heartbeat: {{ serverStatus.last_heartbeat ? formatTime(serverStatus.last_heartbeat) : 'N/A' }}
            </div>
          </div>

          <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">Connection Test</div>
            <div class="flex items-center gap-2">
              <div class="text-xl font-bold" :class="connectionTest.connected ? 'text-[var(--color-success)]' : 'text-[var(--color-warning)]'">
                {{ connectionTest.latency_ms || 0 }}ms
              </div>
              <button class="px-3 py-1 bg-terminal-accent/15 text-terminal-accent rounded-sm text-xs" @click="testConnection" :disabled="testingConnection">
                {{ testingConnection ? '⏳ Testing...' : '🔗 Test' }}
              </button>
            </div>
            <div class="text-[10px] text-theme-muted mt-1">
              {{ connectionTest.connected ? 'Connected' : 'Disconnected' }}
            </div>
          </div>
        </div>

        <div class="flex gap-3">
          <button
            v-if="!serverStatus.running"
            class="px-4 py-2 bg-[var(--color-success-bg)] text-[var(--color-success)] rounded-sm text-sm"
            @click="startServer"
            :disabled="startingServer"
          >
            {{ startingServer ? '⏳ Starting...' : '▶️ Start Server' }}
          </button>
          <button
            v-else
            class="px-4 py-2 bg-[var(--color-danger-bg)] text-[var(--color-danger)] rounded-sm text-sm"
            @click="stopServer"
            :disabled="stoppingServer"
          >
            {{ stoppingServer ? '⏳ Stopping...' : '⏹️ Stop Server' }}
          </button>
        </div>

        <div v-if="serverStatus.error" class="p-3 bg-[var(--color-danger-bg)] border border-[var(--color-danger-border)] rounded-sm text-xs text-[var(--color-danger)]">
          <strong>Error:</strong> {{ serverStatus.error }}
        </div>
      </div>

      <!-- Configuration -->
      <div v-else-if="activeTab === 'config'" class="space-y-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-bold text-theme-primary">⚙️ Configuration</h2>
            <p class="text-xs text-theme-muted mt-1">Manage MCP server settings</p>
          </div>
          <button class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm" @click="loadConfig">🔄 Reload</button>
        </div>

        <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
          <h3 class="text-sm font-bold text-theme-primary mb-4">Server Settings</h3>
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div>
              <label class="text-[11px] text-theme-muted mb-1.5 block">Base URL</label>
              <input
                v-model="configForm.base_url"
                class="w-full bg-terminal-bg border border-theme rounded-sm px-3 py-2 text-sm text-theme-primary focus:outline-none focus:border-terminal-accent/60"
                placeholder="http://localhost:8765"
              >
            </div>
            <div>
              <label class="text-[11px] text-theme-muted mb-1.5 block">Transport Mode</label>
              <select
                v-model="configForm.transport_mode"
                class="w-full bg-terminal-bg border border-theme rounded-sm px-3 py-2 text-sm text-theme-primary focus:outline-none focus:border-terminal-accent/60 cursor-pointer"
              >
                <option value="sse">SSE (Server-Sent Events)</option>
                <option value="stdio">Stdio (Standard I/O)</option>
                <option value="websocket">WebSocket</option>
              </select>
            </div>
            <div>
              <label class="text-[11px] text-theme-muted mb-1.5 block">Port</label>
              <input
                v-model.number="configForm.port"
                type="number"
                min="1"
                max="65535"
                class="w-full bg-terminal-bg border border-theme rounded-sm px-3 py-2 text-sm text-theme-primary focus:outline-none focus:border-terminal-accent/60"
              >
            </div>
            <div>
              <label class="text-[11px] text-theme-muted mb-1.5 block">Timeout (seconds)</label>
              <input
                v-model.number="configForm.timeout"
                type="number"
                min="1"
                max="300"
                class="w-full bg-terminal-bg border border-theme rounded-sm px-3 py-2 text-sm text-theme-primary focus:outline-none focus:border-terminal-accent/60"
              >
            </div>
            <div>
              <label class="text-[11px] text-theme-muted mb-1.5 block">Log Level</label>
              <select
                v-model="configForm.log_level"
                class="w-full bg-terminal-bg border border-theme rounded-sm px-3 py-2 text-sm text-theme-primary focus:outline-none focus:border-terminal-accent/60 cursor-pointer"
              >
                <option value="DEBUG">DEBUG</option>
                <option value="INFO">INFO</option>
                <option value="WARNING">WARNING</option>
                <option value="ERROR">ERROR</option>
              </select>
            </div>
            <div class="flex items-center pt-5">
              <label class="flex items-center gap-2 cursor-pointer">
                <input
                  v-model="configForm.auto_start"
                  type="checkbox"
                  class="w-4 h-4 rounded border-theme bg-terminal-bg text-terminal-accent focus:ring-terminal-accent/50"
                >
                <span class="text-sm text-theme-primary">Auto-start on system boot</span>
              </label>
            </div>
          </div>
          <div class="flex gap-3 mt-6">
            <button
              class="px-4 py-2 bg-terminal-accent rounded-sm text-sm text-theme-primary hover:bg-terminal-accent/80 transition-colors"
              :disabled="savingConfig"
              @click="saveConfig"
            >
              {{ savingConfig ? '💾 Saving...' : '💾 Save Configuration' }}
            </button>
            <button
              class="px-4 py-2 bg-[var(--color-danger-bg)] text-[var(--color-danger)] rounded-sm text-sm"
              @click="resetConfig"
            >
              🔄 Reset to Defaults
            </button>
          </div>
          <div v-if="configMessage" class="mt-3 text-[11px]" :class="configMessageOk ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]'">
            {{ configMessage }}
          </div>
        </div>
      </div>

      <!-- Tools Registry -->
      <div v-else-if="activeTab === 'tools'" class="space-y-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-bold text-theme-primary">🔧 Tool Registry</h2>
            <p class="text-xs text-theme-muted mt-1">Browse available MCP tools and their capabilities</p>
          </div>
          <button class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm" @click="loadTools">🔄 Refresh</button>
        </div>

        <div class="p-4 bg-[var(--info-bg)] border border-[var(--color-info-border)] rounded-sm">
          <h3 class="text-sm font-bold text-[var(--color-info)] mb-2">💡 Tool Scopes</h3>
          <p class="text-xs text-theme-secondary leading-relaxed">
            <strong class="text-[var(--color-success)]">Read</strong>: Query data without side effects |
            <strong class="text-[var(--color-warning)]">Write</strong>: Modify data or execute actions |
            <strong class="text-[var(--color-danger)]">Admin</strong>: Administrative operations
          </p>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div v-for="tool in tools" :key="tool.name" class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
            <div class="flex items-center justify-between mb-2">
              <div class="flex items-center gap-2">
                <span class="font-medium text-theme-primary">{{ tool.name }}</span>
                <span class="text-[10px] px-1.5 py-0.5 rounded-sm" :class="getScopeClass(tool.scope)">
                  {{ tool.scope }}
                </span>
              </div>
            </div>
            <p class="text-xs text-theme-secondary mb-3">{{ tool.description }}</p>
            <div v-if="tool.input_schema && tool.input_schema.properties" class="p-2 bg-terminal-bg/50 rounded-sm text-[10px]">
              <div class="text-theme-muted mb-1">Parameters:</div>
              <div class="space-y-1">
                <div v-for="(prop, key) in tool.input_schema.properties" :key="key" class="flex gap-2">
                  <span class="text-terminal-accent">{{ key }}</span>
                  <span class="text-theme-muted">{{ prop.type }}</span>
                  <span v-if="tool.input_schema.required && tool.input_schema.required.includes(key)" class="text-[var(--color-danger)]">*</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Environment Variables -->
      <div v-else-if="activeTab === 'env'" class="space-y-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-bold text-theme-primary">🌐 Environment Variables</h2>
            <p class="text-xs text-theme-muted mt-1">View MCP-related environment configuration</p>
          </div>
          <button class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm" @click="loadEnv">🔄 Refresh</button>
        </div>

        <div class="p-4 bg-[var(--color-warning-bg)] border border-[var(--color-warning-border)] rounded-sm">
          <h3 class="text-sm font-bold text-[var(--color-warning)] mb-2">⚠️ Read-Only</h3>
          <p class="text-xs text-theme-secondary leading-relaxed">
            Environment variables are read-only in this dashboard. To modify, update your system environment or <code class="bg-terminal-bg px-1 rounded">.env</code> file and restart the service.
          </p>
        </div>

        <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
          <div class="space-y-3">
            <div v-for="(value, key) in envVars" :key="key" class="flex items-center justify-between p-2 bg-terminal-bg/50 rounded-sm">
              <span class="text-sm font-mono text-terminal-accent">{{ key }}</span>
              <span class="text-sm text-theme-secondary font-mono">{{ value || '(not set)' }}</span>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { apiFetch } from '../utils/api.js'
import { toast } from '../composables/useToast.js'

const activeTab = ref('status')
const mobileNavOpen = ref(false)

const navItems = [
  { id: 'status', label: 'Server Status', desc: 'Monitor server health', icon: '📊', status: true, statusClass: 'bg-[var(--color-success-light)]' },
  { id: 'config', label: 'Configuration', desc: 'Manage server settings', icon: '⚙️', status: false, statusClass: 'bg-gray-400' },
  { id: 'tools', label: 'Tool Registry', desc: 'Browse available tools', icon: '🔧', status: false, statusClass: 'bg-gray-400' },
  { id: 'env', label: 'Environment', desc: 'View environment vars', icon: '🌐', status: false, statusClass: 'bg-gray-400' },
]

const serverStatus = reactive({
  running: false,
  uptime: null,
  last_heartbeat: null,
  error: null
})

const connectionTest = reactive({
  connected: false,
  latency_ms: null,
  error: null
})

const configForm = reactive({
  base_url: 'http://localhost:8765',
  transport_mode: 'sse',
  port: 8765,
  timeout: 30,
  auto_start: false,
  log_level: 'INFO'
})

const tools = ref([])
const envVars = ref({})

const testingConnection = ref(false)
const startingServer = ref(false)
const stoppingServer = ref(false)
const savingConfig = ref(false)
const configMessage = ref('')
const configMessageOk = ref(false)

function formatTime(isoTime) {
  if (!isoTime) return 'N/A'
  const date = new Date(isoTime)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function formatUptime(seconds) {
  if (!seconds) return '0s'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

function getScopeClass(scope) {
  const classes = {
    read: 'bg-[var(--color-success-bg)] text-[var(--color-success)]',
    write: 'bg-[var(--color-warning-bg)] text-[var(--color-warning)]',
    admin: 'bg-[var(--color-danger-bg)] text-[var(--color-danger)]'
  }
  return classes[scope] || 'bg-[var(--color-info-bg)] text-[var(--color-info)]'
}

async function refreshStatus() {
  try {
    const data = await apiFetch('/api/v1/mcp/status')
    if (data) {
      serverStatus.running = data.running || false
      serverStatus.uptime = data.uptime || null
      serverStatus.last_heartbeat = data.last_heartbeat || null
      serverStatus.error = data.error || null
    }
  } catch (err) {
    toast('Error', 'Failed to load server status', 'error')
  }
}

async function testConnection() {
  testingConnection.value = true
  try {
    const data = await apiFetch('/api/v1/mcp/test')
    if (data) {
      connectionTest.connected = data.connected || false
      connectionTest.latency_ms = data.latency_ms || null
      connectionTest.error = data.error || null
      if (data.connected) {
        toast('Success', `Connection successful (${data.latency_ms}ms)`, 'success')
      } else {
        toast('Warning', data.error || 'Connection failed', 'warning')
      }
    }
  } catch (err) {
    connectionTest.connected = false
    connectionTest.error = err.message
    toast('Error', 'Connection test failed', 'error')
  } finally {
    testingConnection.value = false
  }
}

async function startServer() {
  startingServer.value = true
  try {
    const data = await apiFetch('/api/v1/mcp/start', { method: 'POST' })
    if (data) {
      toast('Success', 'MCP server started', 'success')
      await refreshStatus()
    }
  } catch (err) {
    toast('Error', 'Failed to start server', 'error')
  } finally {
    startingServer.value = false
  }
}

async function stopServer() {
  stoppingServer.value = true
  try {
    const data = await apiFetch('/api/v1/mcp/stop', { method: 'POST' })
    if (data) {
      toast('Success', 'MCP server stopped', 'success')
      await refreshStatus()
    }
  } catch (err) {
    toast('Error', 'Failed to stop server', 'error')
  } finally {
    stoppingServer.value = false
  }
}

async function loadConfig() {
  try {
    const data = await apiFetch('/api/v1/mcp/config')
    if (data) {
      configForm.base_url = data.base_url || 'http://localhost:8765'
      configForm.transport_mode = data.transport_mode || 'sse'
      configForm.port = data.port || 8765
      configForm.timeout = data.timeout || 30
      configForm.auto_start = data.auto_start || false
      configForm.log_level = data.log_level || 'INFO'
    }
  } catch (err) {
    toast('Error', 'Failed to load configuration', 'error')
  }
}

async function saveConfig() {
  savingConfig.value = true
  configMessage.value = ''
  try {
    const data = await apiFetch('/api/v1/mcp/config', {
      method: 'POST',
      body: JSON.stringify(configForm)
    })
    if (data && data.code === 0) {
      configMessage.value = 'Configuration saved successfully'
      configMessageOk.value = true
      toast('Success', 'Configuration saved', 'success')
    } else {
      configMessage.value = data.message || 'Failed to save configuration'
      configMessageOk.value = false
    }
  } catch (err) {
    configMessage.value = err.message || 'Failed to save configuration'
    configMessageOk.value = false
    toast('Error', 'Failed to save configuration', 'error')
  } finally {
    savingConfig.value = false
  }
}

function resetConfig() {
  configForm.base_url = 'http://localhost:8765'
  configForm.transport_mode = 'sse'
  configForm.port = 8765
  configForm.timeout = 30
  configForm.auto_start = false
  configForm.log_level = 'INFO'
  toast('Info', 'Configuration reset to defaults', 'info')
}

async function loadTools() {
  try {
    const data = await apiFetch('/api/v1/mcp/tools')
    if (data && data.tools) {
      tools.value = data.tools
    }
  } catch (err) {
    toast('Error', 'Failed to load tools', 'error')
  }
}

async function loadEnv() {
  try {
    const data = await apiFetch('/api/v1/mcp/env')
    if (data && data.variables) {
      envVars.value = data.variables
    }
  } catch (err) {
    toast('Error', 'Failed to load environment variables', 'error')
  }
}

onMounted(() => {
  refreshStatus()
  loadConfig()
  loadTools()
  loadEnv()
})
</script>
