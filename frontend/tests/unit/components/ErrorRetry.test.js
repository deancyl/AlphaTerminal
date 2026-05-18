import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ErrorRetry from '@/components/copilot/ErrorRetry.vue'

describe('ErrorRetry', () => {
  it('renders when error prop is provided', () => {
    const wrapper = mount(ErrorRetry, {
      props: {
        error: 'Network connection failed'
      }
    })
    
    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Network connection failed')
    expect(wrapper.find('button').exists()).toBe(true)
    expect(wrapper.find('button').attributes('aria-label')).toBe('重试')
  })

  it('does not render when both error and errorType are empty', () => {
    const wrapper = mount(ErrorRetry, {
      props: {
        error: '',
        errorType: ''
      }
    })
    
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('emits retry event when button is clicked', async () => {
    const wrapper = mount(ErrorRetry, {
      props: {
        error: 'Test error'
      }
    })
    
    await wrapper.find('button').trigger('click')
    
    expect(wrapper.emitted('retry')).toBeTruthy()
    expect(wrapper.emitted('retry').length).toBe(1)
  })

  it('displays correct message for network error type', () => {
    const wrapper = mount(ErrorRetry, {
      props: {
        error: '',
        errorType: 'network'
      }
    })
    
    expect(wrapper.text()).toContain('网络连接失败，请检查网络后重试')
  })

  it('displays correct message for timeout error type', () => {
    const wrapper = mount(ErrorRetry, {
      props: {
        error: '',
        errorType: 'timeout'
      }
    })
    
    expect(wrapper.text()).toContain('请求超时，请稍后重试')
  })

  it('displays correct message for rate_limit error type', () => {
    const wrapper = mount(ErrorRetry, {
      props: {
        error: '',
        errorType: 'rate_limit'
      }
    })
    
    expect(wrapper.text()).toContain('请求过于频繁，请稍后再试')
  })

  it('displays correct message for server error type', () => {
    const wrapper = mount(ErrorRetry, {
      props: {
        error: '',
        errorType: 'server'
      }
    })
    
    expect(wrapper.text()).toContain('服务器暂时无法响应，请稍后重试')
  })

  it('displays custom error message when provided', () => {
    const wrapper = mount(ErrorRetry, {
      props: {
        error: 'Custom error message',
        errorType: 'network'
      }
    })
    
    // Custom error should override type-based message
    expect(wrapper.text()).toContain('Custom error message')
  })

  it('displays generic message for unknown error type', () => {
    const wrapper = mount(ErrorRetry, {
      props: {
        error: '',
        errorType: 'unknown'
      }
    })
    
    expect(wrapper.text()).toContain('发生错误，请重试')
  })

  it('has correct ARIA attributes', () => {
    const wrapper = mount(ErrorRetry, {
      props: {
        error: 'Test error'
      }
    })
    
    const alertDiv = wrapper.find('[role="alert"]')
    expect(alertDiv.exists()).toBe(true)
    expect(alertDiv.attributes('aria-live')).toBe('assertive')
    
    const button = wrapper.find('button')
    expect(button.attributes('aria-label')).toBe('重试')
  })

  it('has correct CSS classes for styling', () => {
    const wrapper = mount(ErrorRetry, {
      props: {
        error: 'Test error'
      }
    })
    
    const alertDiv = wrapper.find('[role="alert"]')
    expect(alertDiv.classes()).toContain('bg-red-500/10')
    expect(alertDiv.classes()).toContain('border-red-500/30')
    
    const button = wrapper.find('button')
    expect(button.classes()).toContain('bg-red-500/20')
    expect(button.classes()).toContain('hover:bg-red-500/30')
  })
})
