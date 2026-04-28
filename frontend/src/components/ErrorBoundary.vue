<template>
  <div v-if="error" class="error-fallback">
    <div class="error-container">
      <div class="error-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
      </div>
      
      <h2 class="error-title">出错了</h2>
      
      <p class="error-message">{{ displayMessage }}</p>
      
      <div v-if="errorDetails && showDetails" class="error-details">
        <pre>{{ errorDetails }}</pre>
      </div>
      
      <div class="error-actions">
        <button @click="reload" class="btn-primary">
          重新加载
        </button>
        <button @click="goHome" class="btn-secondary">
          返回首页
        </button>
        <button v-if="errorDetails" @click="toggleDetails" class="btn-text">
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

const router = useRouter()

const error = ref(null)
const errorInfo = ref('')
const showDetails = ref(false)
const traceId = ref('')

const displayMessage = computed(() => {
  if (!error.value) return ''
  
  // 用户友好的错误消息
  const userMessages = {
    TypeError: '应用程序出现类型错误',
    ReferenceError: '应用程序出现引用错误',
    SyntaxError: '应用程序出现语法错误',
    RangeError: '数值超出有效范围',
    NetworkError: '网络连接失败，请检查网络',
    TimeoutError: '请求超时，请稍后重试',
  }
  
  const errorName = error.value.name || 'Error'
  return userMessages[errorName] || error.value.message || '应用程序出现错误'
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
  
  // 上报错误
  reportError(err, info, traceId.value)
  
  // 阻止错误继续传播
  return false
})

function generateTraceId() {
  return Math.random().toString(36).substring(2, 10).toUpperCase()
}

function reportError(err, info, traceId) {
  // 控制台输出
  console.error('Error Boundary Caught:', {
    error: err,
    component: info,
    traceId: traceId,
    timestamp: new Date().toISOString(),
  })
  
  // TODO: 发送到错误监控服务
  // 例如: Sentry, LogRocket, 或自建服务
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

.error-container {
  max-width: 600px;
  width: 100%;
  padding: 40px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  text-align: center;
}

.error-icon {
  width: 80px;
  height: 80px;
  margin: 0 auto 24px;
  color: #ef4444;
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

.error-message {
  font-size: 16px;
  color: #6b7280;
  margin-bottom: 24px;
  line-height: 1.5;
}

.error-details {
  margin: 20px 0;
  padding: 16px;
  background-color: #f9fafb;
  border-radius: 8px;
  text-align: left;
  overflow-x: auto;
}

.error-details pre {
  font-size: 12px;
  color: #374151;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}

.error-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
  margin-bottom: 20px;
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

.btn-secondary:hover {
  background-color: #f9fafb;
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

.btn-text:hover {
  color: #374151;
}

.error-trace-id {
  font-size: 12px;
  color: #9ca3af;
  font-family: monospace;
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
