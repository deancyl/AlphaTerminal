<!--
  ErrorDisplay.vue - 错误显示组件
  
  用途：
    统一的错误展示组件，用于 F9 深度资料各 Tab 和仪表盘的错误状态显示。
    支持自定义错误消息和重试功能。
  
  Props:
    - error (String): 错误消息文本，默认为空字符串
      - 如果为空，显示默认消息 "加载失败，请稍后重试"
    - retry (Function): 重试回调函数，默认为 null
      - 如果提供，会显示"重试"按钮
      - 点击按钮时调用此函数
  
  使用示例：
    <ErrorDisplay 
      error="网络连接失败" 
      :retry="fetchData" 
    />
    
    <ErrorDisplay 
      :error="errorMessage" 
      :retry="loadFinancialData" 
    />
    
    // 无重试按钮
    <ErrorDisplay error="数据不可用" />
  
  样式：
    - 居中布局，最小高度 200px
    - 警告图标 + 错误消息 + 可选重试按钮
    - 符合终端主题配色（terminal-dim, terminal-accent）
  
  无障碍：
    - role="alert" + aria-live="assertive" 确保屏幕阅读器立即播报
    - 重试按钮有 aria-label 标签
-->
<template>
  <div class="error-display flex flex-col items-center justify-center py-12" role="alert" aria-live="assertive">
    <div class="text-4xl mb-4" aria-hidden="true">⚠️</div>
    <div class="text-sm text-terminal-dim mb-4 text-center max-w-md">
      {{ error || '加载失败，请稍后重试' }}
    </div>
    <!-- 重试按钮：仅当 retry prop 提供时显示 -->
    <button
      v-if="retry"
      class="px-4 py-2 text-sm rounded border border-terminal-accent text-terminal-accent hover:bg-terminal-accent hover:text-white transition"
      @click="handleRetry"
      aria-label="重试加载"
      type="button"
    >
      重试
    </button>
  </div>
</template>

<script setup>
// Props 定义
const props = defineProps({
  // error: 错误消息文本
  // - 类型: String
  // - 默认: 空字符串（显示默认消息）
  // - 用途: 向用户展示具体的错误原因
  error: {
    type: String,
    default: ''
  },
  // retry: 重试回调函数
  // - 类型: Function
  // - 默认: null（不显示重试按钮）
  // - 用途: 点击重试按钮时执行的函数，通常用于重新加载数据
  retry: {
    type: Function,
    default: null
  }
})

// 处理重试按钮点击
// - 检查 retry 函数是否存在
// - 如果存在则调用，触发父组件重新加载数据
function handleRetry() {
  if (props.retry) {
    props.retry()
  }
}
</script>

<style scoped>
/* 错误显示容器最小高度，确保视觉一致性 */
.error-display {
  min-height: 200px;
}
</style>
