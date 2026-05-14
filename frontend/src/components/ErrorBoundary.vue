<template>
  <div v-if="error" class="error-fallback" :class="{ 'error-fallback-inline': inline }" role="alert" aria-live="assertive">
    <div class="error-container" :class="{ 'error-container-inline': inline }">
      <div class="error-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
      </div>
      
      <h2 class="error-title">{{ inline ? '组件错误' : '出错了' }}</h2>
      
      <p class="error-message">{{ displayMessage }}</p>
      
      <div v-if="suggestions.length > 0" class="error-suggestions">
        <p class="suggestions-title">建议操作:</p>
        <ul class="suggestions-list">
          <li v-for="(suggestion, index) in suggestions" :key="index">{{ suggestion }}</li>
        </ul>
      </div>
      
      <div v-if="errorDetails && showDetails" class="error-details">
        <pre>{{ errorDetails }}</pre>
      </div>
      
      <div class="error-actions">
        <button v-if="canReset" @click="reset" class="btn-primary" aria-label="重置组件" type="button">
          重置组件
        </button>
        <button @click="reload" class="btn-secondary" aria-label="重新加载页面" type="button">
          重新加载
        </button>
        <button v-if="!inline" @click="goHome" class="btn-secondary" aria-label="返回首页" type="button">
          返回首页
        </button>
        <button v-if="errorDetails" @click="toggleDetails" class="btn-text" :aria-expanded="showDetails" type="button">
          {{ showDetails ? '隐藏详情' : '查看详情' }}
        </button>
      </div>
      
      <div v-if="traceId" class="error-trace-id">
        追踪ID: {{ traceId }}
      </div>
    </div>
  </div>
  
  <slot v-else />
</template>

<script setup>
import { ref, computed, onErrorCaptured } from 'vue'
import { useRouter } from 'vue-router'
import { getErrorCategory, getErrorSuggestions } from '../composables/useApiError.js'

const props = defineProps({
  inline: { type: Boolean, default: false },
  canReset: { type: Boolean, default: true },
  componentName: { type: String, default: '' },
})

const emit = defineEmits(['reset', 'error'])

const router = useRouter()

const error = ref(null)
const errorInfo = ref('')
const showDetails = ref(false)
const traceId = ref('')

const displayMessage = computed(() => {
  if (!error.value) return ''
  
  const userMessages = {
    TypeError: '应用程序出现类型错误',
    ReferenceError: '应用程序出现引用错误',
    SyntaxError: '应用程序出现语法错误',
    RangeError: '数值超出有效范围',
    NetworkError: '网络连接失败，请检查网络',
    TimeoutError: '请求超时，请稍后重试',
  }
  
  const errorName = error.value.name || 'Error'
  const baseMessage = userMessages[errorName] || error.value.message || '应用程序出现错误'
  
  if (props.componentName) {
    return `${props.componentName}: ${baseMessage}`
  }
  
  return baseMessage
})

const suggestions = computed(() => {
  if (!error.value) return []
  return getErrorSuggestions(error.value)
})

const errorDetails = computed(() => {
  if (!error.value) return ''
  
  let details = ''
  if (error.value.stack) {
    details += error.value.stack
  }
  if (errorInfo.value) {
    details += '\n\n组件信息: ' + errorInfo.value
  }
  return details
})

onErrorCaptured((err, instance, info) => {
  error.value = err
  errorInfo.value = info
  traceId.value = generateTraceId()
  
  reportError(err, info, traceId.value)
  
  emit('error', { error: err, info, traceId: traceId.value })
  
  return false
})

function generateTraceId() {
  return Math.random().toString(36).substring(2, 10).toUpperCase()
}

function reportError(err, info, traceId) {
  console.error('Error Boundary Caught:', {
    error: err,
    component: info,
    traceId: traceId,
    timestamp: new Date().toISOString(),
  })
  
  if (window.reportError) {
    window.reportError({
      type: 'vue-error-boundary',
      error: err?.toString(),
      stack: err?.stack,
      component: info,
      traceId: traceId,
      url: window.location.href,
      userAgent: navigator.userAgent,
    })
  }
}

function reset() {
  error.value = null
  errorInfo.value = ''
  traceId.value = ''
  showDetails.value = false
  emit('reset')
}

function reload() {
  window.location.reload()
}

function goHome() {
  error.value = null
  router.push('/')
}

function toggleDetails() {
  showDetails.value = !showDetails.value
}
</script>

<style scoped>
.error-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 20px;
  background-color: #f5f5f5;
}

.error-fallback-inline {
  min-height: 200px;
  padding: 16px;
  background-color: transparent;
}

.error-container {
  max-width: 600px;
  width: 100%;
  padding: 40px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  text-align: center;
}

.error-container-inline {
  padding: 24px;
  background: var(--bg-secondary, #1a1f2e);
  border: 1px solid var(--border-color, #2d3748);
  border-radius: 8px;
  box-shadow: none;
}

.error-icon {
  width: 80px;
  height: 80px;
  margin: 0 auto 24px;
  color: #ef4444;
}

.error-fallback-inline .error-icon {
  width: 48px;
  height: 48px;
  margin-bottom: 16px;
}

.error-icon svg {
  width: 100%;
  height: 100%;
}

.error-title {
  font-size: 24px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 12px;
}

.error-fallback-inline .error-title {
  font-size: 16px;
  color: var(--text-primary, #E5E7EB);
}

.error-message {
  font-size: 16px;
  color: #6b7280;
  margin-bottom: 24px;
  line-height: 1.5;
}

.error-fallback-inline .error-message {
  font-size: 14px;
  color: var(--text-secondary, #8B949E);
}

.error-suggestions {
  margin: 16px 0;
  padding: 12px 16px;
  background-color: #f0f9ff;
  border-radius: 8px;
  text-align: left;
}

.error-fallback-inline .error-suggestions {
  background-color: rgba(59, 130, 246, 0.1);
}

.suggestions-title {
  font-size: 14px;
  font-weight: 500;
  color: #3b82f6;
  margin-bottom: 8px;
}

.error-fallback-inline .suggestions-title {
  color: var(--color-primary, #0F52BA);
}

.suggestions-list {
  list-style: disc;
  padding-left: 20px;
  margin: 0;
}

.suggestions-list li {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 4px;
}

.error-fallback-inline .suggestions-list li {
  color: var(--text-secondary, #8B949E);
}

.error-details {
  margin: 20px 0;
  padding: 16px;
  background-color: #f9fafb;
  border-radius: 8px;
  text-align: left;
  overflow-x: auto;
}

.error-fallback-inline .error-details {
  background-color: rgba(0, 0, 0, 0.2);
}

.error-details pre {
  font-size: 12px;
  color: #374151;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}

.error-fallback-inline .error-details pre {
  color: var(--text-secondary, #8B949E);
}

.error-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

.error-fallback-inline .error-actions {
  margin-bottom: 12px;
}

.btn-primary {
  padding: 10px 24px;
  background-color: #3b82f6;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s;
}

.btn-primary:hover {
  background-color: #2563eb;
}

.btn-secondary {
  padding: 10px 24px;
  background-color: white;
  color: #374151;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s;
}

.error-fallback-inline .btn-secondary {
  background-color: transparent;
  color: var(--text-primary, #E5E7EB);
  border-color: var(--border-color, #2d3748);
}

.btn-secondary:hover {
  background-color: #f9fafb;
}

.error-fallback-inline .btn-secondary:hover {
  background-color: rgba(255, 255, 255, 0.1);
}

.btn-text {
  padding: 10px 16px;
  background: none;
  color: #6b7280;
  border: none;
  font-size: 14px;
  cursor: pointer;
  text-decoration: underline;
}

.error-fallback-inline .btn-text {
  color: var(--text-secondary, #8B949E);
}

.btn-text:hover {
  color: #374151;
}

.error-trace-id {
  font-size: 12px;
  color: #9ca3af;
  font-family: monospace;
}

.error-fallback-inline .error-trace-id {
  color: var(--text-dim, #6b7280);
}

@media (max-width: 640px) {
  .error-container {
    padding: 24px;
  }
  
  .error-title {
    font-size: 20px;
  }
  
  .error-actions {
    flex-direction: column;
  }
  
  .btn-primary,
  .btn-secondary {
    width: 100%;
  }
}
</style>