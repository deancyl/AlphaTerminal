<template>
  <div class="p-4">
    <div class="flex flex-col sm:flex-row sm:items-center justify-between mb-3 gap-2">
      <span class="text-terminal-accent font-bold text-sm">🔑 API Token 管理</span>
      <div class="flex gap-2 flex-wrap">
        <button @click="loadTokens" class="text-terminal-dim hover:text-terminal-primary text-xs px-2 py-1">↺ 刷新</button>
        <button @click="showCreateModal = true" class="btn-primary text-xs px-3 py-1.5">+ 新建 Token</button>
      </div>
    </div>

    <div v-if="loading" class="text-center text-terminal-dim py-8">
      <div class="text-2xl mb-2 animate-pulse">⏳</div>
      <div class="text-xs">加载中...</div>
    </div>

    <div v-else-if="tokens.length === 0" class="text-center text-terminal-dim py-8">
      <div class="text-2xl mb-2">📭</div>
      <div>暂无 Token</div>
      <div class="text-xs text-theme-tertiary mt-1">点击"新建 Token"创建您的第一个 API Token</div>
    </div>

    <div v-else class="overflow-x-auto">
      <table class="w-full text-xs border-collapse">
        <thead>
          <tr class="border-b border-theme-secondary text-theme-tertiary">
            <th class="text-left py-2 px-2 font-normal">名称</th>
            <th class="text-left py-2 px-2 font-normal">前缀</th>
            <th class="text-left py-2 px-2 font-normal">权限</th>
            <th class="text-left py-2 px-2 font-normal">市场</th>
            <th class="text-left py-2 px-2 font-normal">过期时间</th>
            <th class="text-left py-2 px-2 font-normal">最后使用</th>
            <th class="text-left py-2 px-2 font-normal">状态</th>
            <th class="text-right py-2 px-2 font-normal">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="token in tokens" :key="token.id" class="border-b border-theme-secondary/50 hover:bg-theme-hover/30">
            <td class="py-2 px-2 text-terminal-primary">{{ token.name }}</td>
            <td class="py-2 px-2 text-terminal-dim font-mono text-[10px]">{{ token.token_prefix }}...</td>
            <td class="py-2 px-2">
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="scope in token.scopes"
                  :key="scope"
                  class="px-1.5 py-0.5 rounded text-[10px] border"
                  :class="SCOPE_COLORS[scope] || 'bg-gray-500/20 text-gray-400 border-gray-500/30'"
                  :title="SCOPE_LABELS[scope] || scope"
                >
                  {{ scope }}
                </span>
              </div>
            </td>
            <td class="py-2 px-2 text-terminal-dim">{{ formatMarkets(token.markets) }}</td>
            <td class="py-2 px-2">
              <span :class="getExpiryClass(token.expires_at)">
                {{ formatExpiry(token.expires_at) }}
              </span>
            </td>
            <td class="py-2 px-2 text-terminal-dim">{{ formatLastUsed(token.last_used_at) }}</td>
            <td class="py-2 px-2">
              <span :class="getStatusClass(token)" class="px-1.5 py-0.5 rounded text-[10px]">
                {{ getStatusText(token) }}
              </span>
            </td>
            <td class="py-2 px-2 text-right">
              <button
                v-if="!token.revoked_at"
                @click="handleRevoke(token)"
                class="text-[var(--color-danger)] hover:text-[var(--color-danger)]/80 px-2 py-0.5"
              >
                吊销
              </button>
              <span v-else class="text-theme-tertiary text-[10px]">已吊销</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="showCreateModal" class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" @click.self="showCreateModal = false">
      <div class="bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-sm p-6 w-full max-w-md mx-4">
        <h3 class="text-theme-primary font-bold mb-4">新建 API Token</h3>
        <div class="space-y-3">
          <div>
            <label class="text-[var(--text-secondary)] text-xs">Token 名称</label>
            <input
              v-model="newToken.name"
              class="w-full bg-[var(--bg-secondary)] border border-[var(--border-primary)] rounded-sm px-3 py-2 text-theme-primary mt-1"
              placeholder="如：量化策略A"
            />
          </div>
          <div>
            <label class="text-[var(--text-secondary)] text-xs">权限范围</label>
            <div class="flex flex-wrap gap-2 mt-2">
              <label
                v-for="(label, scope) in SCOPE_LABELS"
                :key="scope"
                class="flex items-center gap-1.5 cursor-pointer"
              >
                <input
                  type="checkbox"
                  :value="scope"
                  v-model="newToken.scopes"
                  class="w-3 h-3"
                />
                <span class="text-xs text-terminal-secondary">{{ scope }} - {{ label }}</span>
              </label>
            </div>
          </div>
          <div>
            <label class="text-[var(--text-secondary)] text-xs">可访问市场</label>
            <div class="flex flex-wrap gap-2 mt-2">
              <label
                v-for="market in availableMarkets"
                :key="market"
                class="flex items-center gap-1.5 cursor-pointer"
              >
                <input
                  type="checkbox"
                  :value="market"
                  v-model="newToken.markets"
                  class="w-3 h-3"
                />
                <span class="text-xs text-terminal-secondary">{{ market }}</span>
              </label>
            </div>
            <div class="text-[var(--text-muted)] text-[10px] mt-1">不选择则允许所有市场</div>
          </div>
          <div>
            <label class="text-[var(--text-secondary)] text-xs">请求频率限制 (次/分钟)</label>
            <input
              v-model.number="newToken.rate_limit"
              type="number"
              class="w-full bg-[var(--bg-secondary)] border border-[var(--border-primary)] rounded-sm px-3 py-2 text-theme-primary mt-1"
              placeholder="120"
            />
          </div>
          <div>
            <label class="text-[var(--text-secondary)] text-xs">有效期 (天)</label>
            <input
              v-model.number="newToken.expires_in_days"
              type="number"
              class="w-full bg-[var(--bg-secondary)] border border-[var(--border-primary)] rounded-sm px-3 py-2 text-theme-primary mt-1"
              placeholder="30 (留空或0表示永不过期)"
            />
          </div>
          <div v-if="createError" class="text-[var(--color-danger)] text-xs">{{ createError }}</div>
        </div>
        <div class="flex gap-2 mt-4 justify-end">
          <button @click="showCreateModal = false" class="px-4 py-2 text-[var(--text-secondary)] hover:text-theme-primary">取消</button>
          <button @click="handleCreate" class="btn-primary px-4 py-2" :disabled="creating">
            {{ creating ? '创建中...' : '创建' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="showTokenModal" class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" @click.self="showTokenModal = false">
      <div class="bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-sm p-6 w-full max-w-lg mx-4">
        <h3 class="text-theme-primary font-bold mb-2">✅ Token 创建成功</h3>
        <div class="text-[var(--color-warning)] text-xs mb-4">
          ⚠️ 请立即复制保存此 Token，关闭后将无法再次查看！
        </div>
        <div class="bg-[var(--bg-secondary)] border border-[var(--border-primary)] rounded-sm p-3 mb-4">
          <div class="flex items-center justify-between gap-2">
            <code class="text-terminal-accent text-xs break-all flex-1">{{ createdToken }}</code>
            <button
              @click="copyToken"
              class="px-2 py-1 text-xs bg-terminal-accent/20 text-terminal-accent rounded hover:bg-terminal-accent/30 shrink-0"
            >
              {{ copied ? '已复制' : '复制' }}
            </button>
          </div>
        </div>
        <div class="text-[var(--text-muted)] text-xs mb-4">
          <div>名称: {{ createdTokenInfo?.name }}</div>
          <div>权限: {{ createdTokenInfo?.scopes?.join(', ') }}</div>
          <div>过期: {{ createdTokenInfo?.expires_at || '永不过期' }}</div>
        </div>
        <div class="flex justify-end">
          <button @click="showTokenModal = false" class="btn-primary px-4 py-2">我已保存，关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { listTokens, createToken, revokeToken, SCOPE_LABELS, SCOPE_COLORS } from '../services/agentTokenService.js'
import { useToast } from '../composables/useToast.js'

const { success: toastSuccess, error: toastError, warning: toastWarning } = useToast()

const tokens = ref([])
const loading = ref(false)
const showCreateModal = ref(false)
const showTokenModal = ref(false)
const creating = ref(false)
const createError = ref('')
const createdToken = ref('')
const createdTokenInfo = ref(null)
const copied = ref(false)

const newToken = ref({
  name: '',
  scopes: ['R'],
  markets: [],
  rate_limit: 120,
  expires_in_days: 30,
})

const availableMarkets = ['AStock', 'HKStock', 'USStock', 'Crypto', 'Forex', 'Futures']

async function loadTokens() {
  loading.value = true
  try {
    const data = await listTokens(true)
    tokens.value = Array.isArray(data) ? data : (data.data || [])
  } catch (e) {
    toastError('加载失败', e.message)
    tokens.value = []
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  createError.value = ''
  if (!newToken.value.name.trim()) {
    createError.value = '请填写 Token 名称'
    return
  }
  if (newToken.value.scopes.length === 0) {
    createError.value = '请至少选择一个权限'
    return
  }

  creating.value = true
  try {
    const result = await createToken({
      name: newToken.value.name,
      scopes: newToken.value.scopes,
      markets: newToken.value.markets.length > 0 ? newToken.value.markets : null,
      rate_limit: newToken.value.rate_limit || 120,
      expires_in_days: newToken.value.expires_in_days || null,
    })

    createdToken.value = result.token
    createdTokenInfo.value = result
    showCreateModal.value = false
    showTokenModal.value = true
    copied.value = false

    newToken.value = {
      name: '',
      scopes: ['R'],
      markets: [],
      rate_limit: 120,
      expires_in_days: 30,
    }

    await loadTokens()
    toastSuccess('创建成功', 'Token 已创建，请妥善保管')
  } catch (e) {
    createError.value = e.message
    toastError('创建失败', e.message)
  } finally {
    creating.value = false
  }
}

async function handleRevoke(token) {
  if (!confirm(`确定要吊销 Token "${token.name}" 吗？此操作不可恢复。`)) {
    return
  }

  try {
    await revokeToken(token.id)
    toastSuccess('吊销成功', `Token "${token.name}" 已吊销`)
    await loadTokens()
  } catch (e) {
    toastError('吊销失败', e.message)
  }
}

function copyToken() {
  navigator.clipboard.writeText(createdToken.value).then(() => {
    copied.value = true
    toastSuccess('已复制', 'Token 已复制到剪贴板')
  }).catch(() => {
    toastError('复制失败', '请手动复制')
  })
}

function formatMarkets(markets) {
  if (!markets || markets.length === 0) return '全部'
  return markets.join(', ')
}

function formatExpiry(expiresAt) {
  if (!expiresAt) return '永不过期'
  const date = new Date(expiresAt)
  return date.toLocaleDateString('zh-CN')
}

function formatLastUsed(lastUsedAt) {
  if (!lastUsedAt) return '从未使用'
  const date = new Date(lastUsedAt)
  const now = new Date()
  const diffMs = now - date
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return '刚刚'
  if (diffMins < 60) return `${diffMins} 分钟前`
  if (diffHours < 24) return `${diffHours} 小时前`
  if (diffDays < 30) return `${diffDays} 天前`
  return date.toLocaleDateString('zh-CN')
}

function getExpiryClass(expiresAt) {
  if (!expiresAt) return 'text-green-400'

  const expiry = new Date(expiresAt)
  const now = new Date()
  const diffDays = Math.floor((expiry - now) / 86400000)

  if (diffDays < 0) return 'text-red-400'
  if (diffDays <= 7) return 'text-yellow-400'
  return 'text-terminal-dim'
}

function getStatusClass(token) {
  if (token.revoked_at) return 'bg-red-500/20 text-red-400'
  if (token.expires_at && new Date(token.expires_at) < new Date()) return 'bg-red-500/20 text-red-400'
  if (token.expires_at && (new Date(token.expires_at) - new Date()) < 7 * 86400000) return 'bg-yellow-500/20 text-yellow-400'
  return 'bg-green-500/20 text-green-400'
}

function getStatusText(token) {
  if (token.revoked_at) return '已吊销'
  if (token.expires_at && new Date(token.expires_at) < new Date()) return '已过期'
  if (token.expires_at && (new Date(token.expires_at) - new Date()) < 7 * 86400000) return '即将过期'
  return '正常'
}

onMounted(() => {
  loadTokens()
})

onUnmounted(() => {
})
</script>
