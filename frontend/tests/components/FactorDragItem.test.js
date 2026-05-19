import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import FactorDragItem from '@/components/factor/FactorDragItem.vue'

vi.stubGlobal('navigator', {
  vibrate: vi.fn(),
})

describe('FactorDragItem', () => {
  const mockFactor = {
    id: 'macd_cross',
    name: 'MACD金叉',
    category: 'technical',
    description: 'MACD金叉信号',
    unit: '信号',
  }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  const mountComponent = (options = {}) => {
    return mount(FactorDragItem, {
      props: {
        factor: mockFactor,
        selected: false,
      },
      ...options,
    })
  }

  describe('test_drag_start', () => {
    it('should emit dragstart event on drag start', async () => {
      const wrapper = mountComponent()
      const item = wrapper.find('.factor-drag-item')

      await item.trigger('dragstart', {
        dataTransfer: {
          setData: vi.fn(),
          effectAllowed: 'copy',
        },
      })

      expect(wrapper.emitted('dragstart')).toBeTruthy()
      expect(wrapper.emitted('dragstart')[0][0]).toEqual(mockFactor)
    })

    it('should set correct dataTransfer data', async () => {
      const wrapper = mountComponent()
      const mockSetData = vi.fn()

      await wrapper.find('.factor-drag-item').trigger('dragstart', {
        dataTransfer: {
          setData: mockSetData,
          effectAllowed: 'copy',
        },
      })

      expect(mockSetData).toHaveBeenCalledWith(
        'application/json',
        JSON.stringify(mockFactor)
      )
    })

    it('should set isDragging state', async () => {
      const wrapper = mountComponent()

      await wrapper.find('.factor-drag-item').trigger('dragstart', {
        dataTransfer: { setData: vi.fn() },
      })

      expect(wrapper.find('.factor-drag-item--dragging').exists()).toBe(true)
    })

    it('should emit dragend on drag end', async () => {
      const wrapper = mountComponent()

      await wrapper.find('.factor-drag-item').trigger('dragend')

      expect(wrapper.emitted('dragend')).toBeTruthy()
    })

    it('should clear isDragging state on drag end', async () => {
      const wrapper = mountComponent()

      await wrapper.find('.factor-drag-item').trigger('dragstart', {
        dataTransfer: { setData: vi.fn() },
      })
      expect(wrapper.find('.factor-drag-item--dragging').exists()).toBe(true)

      await wrapper.find('.factor-drag-item').trigger('dragend')
      expect(wrapper.find('.factor-drag-item--dragging').exists()).toBe(false)
    })
  })

  describe('test_touch_drag', () => {
    it('should start touch drag after long press', async () => {
      const wrapper = mountComponent()
      const item = wrapper.find('.factor-drag-item')

      await item.trigger('touchstart', {
        touches: [{ clientX: 100, clientY: 100 }],
      })

      vi.advanceTimersByTime(300)

      expect(wrapper.vm.isTouchDragging).toBe(true)
    })

    it('should cancel touch drag if moved before long press', async () => {
      const wrapper = mountComponent()

      await wrapper.find('.factor-drag-item').trigger('touchstart', {
        touches: [{ clientX: 100, clientY: 100 }],
      })

      await wrapper.find('.factor-drag-item').trigger('touchmove', {
        touches: [{ clientX: 120, clientY: 100 }],
      })

      vi.advanceTimersByTime(300)

      expect(wrapper.vm.isTouchDragging).toBe(false)
    })

    it('should emit touchdrop when dropped on funnel', async () => {
      const wrapper = mountComponent()

      document.elementFromPoint = vi.fn(() => ({
        closest: vi.fn(() => ({ classList: { add: vi.fn(), remove: vi.fn() } })),
      }))

      await wrapper.find('.factor-drag-item').trigger('touchstart', {
        touches: [{ clientX: 100, clientY: 100 }],
      })
      vi.advanceTimersByTime(300)

      await wrapper.find('.factor-drag-item').trigger('touchend', {
        changedTouches: [{ clientX: 100, clientY: 100 }],
      })

      expect(wrapper.emitted('touchdrop')).toBeTruthy()
    })

    it('should trigger haptic feedback on touch drag start', async () => {
      const wrapper = mountComponent()

      await wrapper.find('.factor-drag-item').trigger('touchstart', {
        touches: [{ clientX: 100, clientY: 100 }],
      })
      vi.advanceTimersByTime(300)

      expect(navigator.vibrate).toHaveBeenCalledWith(50)
    })

    it('should show touch ghost element during drag', async () => {
      const wrapper = mountComponent()

      await wrapper.find('.factor-drag-item').trigger('touchstart', {
        touches: [{ clientX: 100, clientY: 100 }],
      })
      vi.advanceTimersByTime(300)

      expect(wrapper.find('.factor-drag-item__touch-ghost').exists()).toBe(true)
    })
  })

  describe('test_click_toggle', () => {
    it('should emit click event on click', async () => {
      const wrapper = mountComponent()

      await wrapper.find('.factor-drag-item').trigger('click')

      expect(wrapper.emitted('click')).toBeTruthy()
      expect(wrapper.emitted('click')[0][0]).toEqual(mockFactor)
    })

    it('should not emit click during touch drag', async () => {
      const wrapper = mountComponent()

      await wrapper.find('.factor-drag-item').trigger('touchstart', {
        touches: [{ clientX: 100, clientY: 100 }],
      })
      vi.advanceTimersByTime(300)

      await wrapper.find('.factor-drag-item').trigger('click')

      expect(wrapper.emitted('click')).toBeFalsy()
    })
  })

  describe('test_selected_state', () => {
    it('should show selected class when selected', () => {
      const wrapper = mountComponent({
        props: { selected: true },
      })

      expect(wrapper.find('.factor-drag-item--selected').exists()).toBe(true)
    })

    it('should show check mark when selected', () => {
      const wrapper = mountComponent({
        props: { selected: true },
      })

      expect(wrapper.find('.factor-drag-item__check').exists()).toBe(true)
    })

    it('should not show check mark when not selected', () => {
      const wrapper = mountComponent()

      expect(wrapper.find('.factor-drag-item__check').exists()).toBe(false)
    })
  })

  describe('test_keyboard_navigation', () => {
    it('should emit click on Enter key', async () => {
      const wrapper = mountComponent()

      await wrapper.find('.factor-drag-item').trigger('keydown.enter')

      expect(wrapper.emitted('click')).toBeTruthy()
    })

    it('should emit click on Space key', async () => {
      const wrapper = mountComponent()

      await wrapper.find('.factor-drag-item').trigger('keydown.space')

      expect(wrapper.emitted('click')).toBeTruthy()
    })

    it('should have tabindex for keyboard focus', () => {
      const wrapper = mountComponent()
      const item = wrapper.find('.factor-drag-item')

      expect(item.attributes('tabindex')).toBe('0')
    })

    it('should have correct ARIA attributes', () => {
      const wrapper = mountComponent()
      const item = wrapper.find('.factor-drag-item')

      expect(item.attributes('role')).toBe('option')
      expect(item.attributes('aria-selected')).toBe('false')
    })

    it('should have aria-selected true when selected', () => {
      const wrapper = mountComponent({
        props: { selected: true },
      })
      const item = wrapper.find('.factor-drag-item')

      expect(item.attributes('aria-selected')).toBe('true')
    })
  })

  describe('test_display', () => {
    it('should display factor name', () => {
      const wrapper = mountComponent()

      expect(wrapper.text()).toContain('MACD金叉')
    })

    it('should display factor description', () => {
      const wrapper = mountComponent()

      expect(wrapper.text()).toContain('MACD金叉信号')
    })

    it('should display factor unit', () => {
      const wrapper = mountComponent()

      expect(wrapper.text()).toContain('信号')
    })

    it('should display category icon', () => {
      const wrapper = mountComponent()

      expect(wrapper.text()).toContain('📊')
    })

    it('should use correct icon for each category', () => {
      const categories = [
        { category: 'value', icon: '💰' },
        { category: 'growth', icon: '📈' },
        { category: 'quality', icon: '⭐' },
        { category: 'momentum', icon: '🚀' },
        { category: 'technical', icon: '📊' },
        { category: 'sentiment', icon: '🧠' },
        { category: 'fund_flow', icon: '💵' },
        { category: 'volatility', icon: '📉' },
      ]

      categories.forEach(({ category, icon }) => {
        const wrapper = mountComponent({
          props: {
            factor: { ...mockFactor, category },
          },
        })
        expect(wrapper.text()).toContain(icon)
      })
    })

    it('should use default icon for unknown category', () => {
      const wrapper = mountComponent({
        props: {
          factor: { ...mockFactor, category: 'unknown' },
        },
      })

      expect(wrapper.text()).toContain('📌')
    })
  })

  describe('test_cleanup', () => {
    it('should clear long press timer on unmount', async () => {
      const wrapper = mountComponent()

      await wrapper.find('.factor-drag-item').trigger('touchstart', {
        touches: [{ clientX: 100, clientY: 100 }],
      })

      wrapper.unmount()
    })
  })
})
