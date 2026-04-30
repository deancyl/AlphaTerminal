<template>
  <div class="alert-manager">
    <!-- 标题栏 -->
    <div class="flex items-center justify-between mb-3">
      <span class="text-terminal-accent font-bold text-sm">🔔 价格预警</span>
      <div class="flex gap-2">
        <button
          v-if="notificationPermission !== 'granted'"
          @click="requestPermission"
          class="bg-yellow-500/20 hover:bg-yellow-500/30 text-yellow-400 border border-yellow-500/30 text-xs px-2 py-1 rounded transition-colors"
        >
          启用通知
        </button>
        <button
          @click="showAddModal = true"
          class="bg-terminal-accent/20 hover:bg-terminal-accent/30 text-terminal-accent border border-terminal-accent/30 text-xs px-2 py-1 rounded transition-colors"
        >
          + 添加
        </button>
      </div>
    </div>

    <!-- 权限状态 -->
    <div v-if="notificationPermission === 'denied'" class="mb-3 p-2 bg-red-900/30 border border-red-500/30 rounded text-xs text-red-300">
      ⚠️ 浏览器通知权限被拒绝，请手动启用通知权限以接收预警
    </div>

    <!-- 预警规则列表 -->
    <div class="space-y-2 max-h-60 overflow-y-auto">
      <div v-if="alertRules.length === 0" class="text-center text-gray-500 text-xs py-4">
        暂无预警规则，点击"添加"创建
      </div>
      
      <div
        v-for="rule in alertRules"
        :key="rule.id"
        class="p-2 bg-terminal-panel border border-theme rounded text-xs"
        :class="{ 'opacity-50': !rule.enabled }"
      >
        <div class="flex items-center justify-between">
          <div class="flex-1">
            <div class="font-medium text-cyan-400">{{ rule.symbol }}</div>
            <div class="text-gray-400 mt-0.5">
              {{ formatCondition(rule) }}
            </div>
            <div v-if="rule.triggeredAt" class="text-yellow-400 text-[10px] mt-0.5">
              上次触发: {{ formatTime(rule.triggeredAt) }}
              <span v-if="rule.triggerCount > 1">({{ rule.triggerCount }}次)</span>
            </div>
          </div>
          <div class="flex items-center gap-1">
            <button
              @click="toggleRule(rule.id)"
              class="w-6 h-6 rounded flex items-center justify-center transition-colors"
              :class="rule.enabled ? 'bg-green-600/30 text-green-400' : 'bg-gray-600/30 text-gray-400'"
            >
              {{ rule.enabled ? '✓' : '○' }}
            </button>
            <button
              @click="deleteRule(rule.id)"
              class="w-6 h-6 rounded flex items-center justify-center bg-red-600/30 text-red-400 hover:bg-red-600/50 transition-colors"
            >
              ×
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 添加预警弹窗 -->
    <div v-if="showAddModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60" @click.self="showAddModal = false">
      <div class="bg-terminal-panel border border-theme rounded-lg p-4 w-80 max-w-[90vw]">
        <h3 class="text-sm font-bold text-terminal-accent mb-3">添加价格预警</h3>
        
        <div class="space-y-3">
          <div>
            <label class="block text-xs text-gray-400 mb-1">股票代码</label>
            <input
              v-model="newRule.symbol"
              type="text"
              placeholder="如: sh600519"
              class="w-full bg-black/40 border border-gray-600 rounded px-2 py-1 text-xs text-white focus:border-cyan-400 focus:outline-none"
            />
          </div>
          
          <div>
            <label class="block text-xs text-gray-400 mb-1">预警条件</label>
            <select
              v-model="newRule.condition"
              class="w-full bg-black/40 border border-gray-600 rounded px-2 py-1 text-xs text-white focus:border-cyan-400 focus:outline-none"
            >
              <option value="above">价格高于</option>
              <option value="below">价格低于</option>
              <option value="equals">价格等于</option>
            </select>
          </div>
          
          <div>
            <label class="block text-xs text-gray-400 mb-1">目标价格</label>
            <input
              v-model.number="newRule.targetPrice"
              type="number"
              step="0.01"
              placeholder="输入目标价格"
              class="w-full bg-black/40 border border-gray-600 rounded px-2 py-1 text-xs text-white focus:border-cyan-400 focus:outline-none"
            />
          </div>
          
          <div>
            <label class="block text-xs text-gray-400 mb-1">备注（可选）</label>
            <input
              v-model="newRule.note"
              type="text"
              placeholder="添加备注说明"
              class="w-full bg-black/40 border border-gray-600 rounded px-2 py-1 text-xs text-white focus:border-cyan-400 focus:outline-none"
            />
          </div>
        </div>
        
        <div class="flex justify-end gap-2 mt-4">
          <button
            @click="showAddModal = false"
            class="px-3 py-1 text-xs text-gray-400 hover:text-white transition-colors"
          >
            取消
          </button>
          <button
            @click="addRule"
            :disabled="!canAdd"
            class="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            添加
          </button>
        </div>
      </div>
    </div>

    <!-- 预警历史 -->
    <div v-if="alertHistory.length > 0" class="mt-4 pt-3 border-t border-theme">
      <div class="flex items-center justify-between mb-2">
        <span class="text-xs text-gray-400">预警历史</span>
        <button
          @click="clearHistory"
          class="text-[10px] text-red-400 hover:text-red-300"
        >
          清空
        </button>
      </div>
      <div class="space-y-1 max-h-32 overflow-y-auto">
        <div
          v-for="record in recentHistory"
          :key="record.id"
          class="text-[10px] p-1.5 bg-black/20 rounded"
        >
          <div class="flex items-center justify-between">
            <span class="text-cyan-400">{{ record.symbol }}</span>
            <span class="text-gray-500">{{ formatTime(record.triggeredAt) }}</span>
          </div>
          <div class="text-gray-400 mt-0.5">
            {{ formatCondition(record) }} → ¥{{ record.triggeredPrice }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  notificationPermission,
  alertRules,
  alertHistory,
  requestNotificationPermission,
  checkNotificationPermission,
  addAlertRule,
  removeAlertRule,
  toggleAlertRule,
  loadAlertRules,
  loadAlertHistory,
  formatAlertCondition
} from '../composables/useNotifications.js'

// 状态
const showAddModal = ref(false)
const newRule = ref({
  symbol: '',
  condition: 'above',
  targetPrice: null,
  note: ''
})

// 计算属性
const canAdd = computed(() => {
  return newRule.value.symbol && 
         newRule.value.targetPrice && 
         newRule.value.targetPrice > 0
})

const recentHistory = computed(() => {
  return alertHistory.value.slice(0, 10)
})

// 方法
function requestPermission() {
  requestNotificationPermission()
}

function addRule() {
  if (!canAdd.value) return
  
  addAlertRule({
    symbol: newRule.value.symbol.trim(),
    condition: newRule.value.condition,
    targetPrice: newRule.value.targetPrice,
    note: newRule.value.note
  })
  
  // 重置表单
  newRule.value = {
    symbol: '',
    condition: 'above',
    targetPrice: null,
    note: ''
  }
  
  showAddModal.value = false
}

function deleteRule(ruleId) {
  removeAlertRule(ruleId)
}

function toggleRule(ruleId) {
  toggleAlertRule(ruleId)
}

function clearHistory() {
  alertHistory.value = []
  try {
    localStorage.removeItem('alphaterminal_alert_history')
  } catch (error) {
    console.error('[AlertManager] Failed to clear history:', error)
  }
}

function formatCondition(rule) {
  const conditionMap = {
    'above': '高于',
    'below': '低于',
    'equals': '等于'
  }
  return `价格${conditionMap[rule.condition] || rule.condition} ¥${rule.targetPrice}`
}

function formatTime(isoString) {
  if (!isoString) return ''
  const date = new Date(isoString)
  const now = new Date()
  const diff = now - date
  
  // 小于1小时显示分钟前
  if (diff < 60 * 60 * 1000) {
    const minutes = Math.floor(diff / (60 * 1000))
    return minutes < 1 ? '刚刚' : `${minutes}分钟前`
  }
  
  // 小于24小时显示小时前
  if (diff < 24 * 60 * 60 * 1000) {
    const hours = Math.floor(diff / (60 * 60 * 1000))
    return `${hours}小时前`
  }
  
  // 否则显示日期
  return date.toLocaleDateString('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 初始化
onMounted(() => {
  checkNotificationPermission()
  loadAlertRules()
  loadAlertHistory()
})
</script>

<style scoped>
.alert-manager {
  @apply p-3 rounded-lg;
  background-color: var(--panel-bg);
  border: 1px solid var(--border-primary);
}
</style>
