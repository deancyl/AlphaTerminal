import { ref, onErrorCaptured, provide, inject, h } from 'vue'

/**
 * 全局错误边界 Composable
 * 
 * 捕获组件树中的错误，防止单个组件崩溃影响全局
 */
export function useErrorBoundary() {
  const error = ref(null)
  const errorInfo = ref(null)

  const clearError = () => {
    error.value = null
    errorInfo.value = null
  }

  const handleError = (err, instance, info) => {
    console.error('[ErrorBoundary] 捕获到错误:', err)
    console.error('[ErrorBoundary] 组件:', instance)
    console.error('[ErrorBoundary] 信息:', info)
    
    error.value = err
    errorInfo.value = {
      component: instance?.$options?.name || 'Unknown',
      info,
      timestamp: new Date().toISOString(),
      stack: err.stack
    }
  }

  // ErrorBoundary 组件渲染函数
  const ErrorBoundary = {
    name: 'ErrorBoundary',
    setup(_, { slots }) {
      onErrorCaptured((err, instance, info) => {
        handleError(err, instance, info)
        return false
      })

      return () => {
        if (error.value) {
          // 使用渲染函数替代 JSX
          return h('div', { class: 'error-boundary-fallback' }, [
            h('div', { class: 'error-icon' }, '⚠️'),
            h('div', { class: 'error-title' }, '组件渲染出错'),
            h('div', { class: 'error-message' }, error.value.message),
            h('button', { 
              class: 'error-retry',
              onClick: clearError 
            }, '重试')
          ])
        }
        return slots.default?.()
      }
    }
  }

  return {
    error,
    errorInfo,
    clearError,
    ErrorBoundary,
    handleError
  }
}

// 全局错误处理注入键
const ERROR_BOUNDARY_KEY = Symbol('errorBoundary')

export function provideErrorBoundary() {
  const boundary = useErrorBoundary()
  provide(ERROR_BOUNDARY_KEY, boundary)
  return boundary
}

export function useGlobalError() {
  return inject(ERROR_BOUNDARY_KEY, null)
}
