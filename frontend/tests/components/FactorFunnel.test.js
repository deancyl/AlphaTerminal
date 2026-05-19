import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import FactorFunnel from '@/components/factor/FactorFunnel.vue'

describe('FactorFunnel', () => {
  const mockFactors = [
    { id: 'macd_cross', name: 'MACD金叉', category: 'technical' },
    { id: 'rsi_oversold', name: 'RSI超卖', category: 'technical' },
    { id: 'foreign_inflow', name: '外资净流入', category: 'fund_flow' },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
  })

  const mountComponent = (options = {}) => {
    return mount(FactorFunnel, {
      props: {
        factors: mockFactors,
      },
      ...options,
    })
  }

  describe('test_drop_factor', () => {
    it('should emit add event when factor dropped', async () => {
      const wrapper = mountComponent({ props: { factors: [] } })

      const newFactor = { id: 'new_factor', name: '新因子' }

      await wrapper.find('.factor-funnel').trigger('drop', {
        dataTransfer: {
          getData: vi.fn(() => JSON.stringify(newFactor)),
        },
      })

      expect(wrapper.emitted('add')).toBeTruthy()
      expect(wrapper.emitted('add')[0][0]).toEqual(newFactor)
    })

    it('should not add duplicate factor', async () => {
      const wrapper = mountComponent()

      await wrapper.find('.factor-funnel').trigger('drop', {
        dataTransfer: {
          getData: vi.fn(() => JSON.stringify(mockFactors[0])),
        },
      })

      expect(wrapper.emitted('add')).toBeFalsy()
    })

    it('should handle invalid JSON data', async () => {
      const wrapper = mountComponent({ props: { factors: [] } })

      await wrapper.find('.factor-funnel').trigger('drop', {
        dataTransfer: {
          getData: vi.fn(() => 'invalid json'),
        },
      })

      expect(wrapper.emitted('add')).toBeFalsy()
    })

    it('should prevent default on dragover', async () => {
      const wrapper = mountComponent()

      const event = { preventDefault: vi.fn() }
      await wrapper.find('.factor-funnel').trigger('dragover', event)

    })
  })

  describe('test_remove_factor', () => {
    it('should emit remove event when remove button clicked', async () => {
      const wrapper = mountComponent()

      const removeButtons = wrapper.findAll('.factor-funnel__item-remove')
      await removeButtons[0].trigger('click')

      expect(wrapper.emitted('remove')).toBeTruthy()
      expect(wrapper.emitted('remove')[0][0]).toBe('macd_cross')
    })

    it('should stop propagation on remove click', async () => {
      const wrapper = mountComponent()

      const removeButton = wrapper.find('.factor-funnel__item-remove')
      await removeButton.trigger('click')

    })
  })

  describe('test_reorder_factors', () => {
    it('should emit reorder event when item dropped on another', async () => {
      const wrapper = mountComponent()

      const items = wrapper.findAll('.factor-funnel__item')

      await items[0].trigger('dragstart', {
        dataTransfer: {
          setData: vi.fn(),
          effectAllowed: 'move',
        },
      })

      await items[1].trigger('dragover', { preventDefault: vi.fn() })

      await items[1].trigger('drop', {
        dataTransfer: {
          getData: vi.fn(() => '0'),
        },
      })

      expect(wrapper.emitted('reorder')).toBeTruthy()
      expect(wrapper.emitted('reorder')[0]).toEqual([0, 1])
    })

    it('should not reorder to same position', async () => {
      const wrapper = mountComponent()

      const items = wrapper.findAll('.factor-funnel__item')

      await items[0].trigger('dragstart', {
        dataTransfer: { setData: vi.fn() },
      })

      await items[0].trigger('dragover', { preventDefault: vi.fn() })

      await items[0].trigger('drop', {
        dataTransfer: { getData: vi.fn(() => '0') },
      })

      expect(wrapper.emitted('reorder')).toBeFalsy()
    })

    it('should clear drag state on dragend', async () => {
      const wrapper = mountComponent()

      const items = wrapper.findAll('.factor-funnel__item')

      await items[0].trigger('dragstart', {
        dataTransfer: { setData: vi.fn() },
      })

      await items[0].trigger('dragend')

      expect(wrapper.vm.draggedIndex).toBeNull()
      expect(wrapper.vm.dropTargetIndex).toBeNull()
    })
  })

  describe('test_display', () => {
    it('should render funnel header', () => {
      const wrapper = mountComponent()

      expect(wrapper.find('.factor-funnel__header').exists()).toBe(true)
      expect(wrapper.text()).toContain('筛选漏斗')
    })

    it('should show factor count', () => {
      const wrapper = mountComponent()

      expect(wrapper.text()).toContain('3 个因子')
    })

    it('should render all factors', () => {
      const wrapper = mountComponent()

      const items = wrapper.findAll('.factor-funnel__item')
      expect(items.length).toBe(3)
    })

    it('should show factor names', () => {
      const wrapper = mountComponent()

      expect(wrapper.text()).toContain('MACD金叉')
      expect(wrapper.text()).toContain('RSI超卖')
      expect(wrapper.text()).toContain('外资净流入')
    })

    it('should show order numbers', () => {
      const wrapper = mountComponent()

      const orderNumbers = wrapper.findAll('.factor-funnel__item-order')
      expect(orderNumbers[0].text()).toBe('1')
      expect(orderNumbers[1].text()).toBe('2')
      expect(orderNumbers[2].text()).toBe('3')
    })

    it('should show empty state when no factors', () => {
      const wrapper = mountComponent({ props: { factors: [] } })

      expect(wrapper.find('.factor-funnel__empty').exists()).toBe(true)
      expect(wrapper.text()).toContain('拖拽因子到此处')
    })

    it('should show funnel SVG connectors', () => {
      const wrapper = mountComponent()

      const connectors = wrapper.findAll('.factor-funnel__item-funnel')
      expect(connectors.length).toBe(3)
    })
  })

  describe('test_funnel_points', () => {
    it('should generate correct funnel points for first item', () => {
      const wrapper = mountComponent()

      const points = wrapper.vm.getFunnelPoints(0)
      expect(points).toBeTruthy()
    })

    it('should generate narrower funnel for later items', () => {
      const wrapper = mountComponent()

      const points0 = wrapper.vm.getFunnelPoints(0)
      const points2 = wrapper.vm.getFunnelPoints(2)

      expect(points0).not.toBe(points2)
    })

    it('should return default points for single item', () => {
      const wrapper = mountComponent({ props: { factors: [mockFactors[0]] } })

      const points = wrapper.vm.getFunnelPoints(0)
      expect(points).toBe('0,0 100,0 100,8 0,8')
    })
  })

  describe('test_animation', () => {
    it('should have animation delay based on index', () => {
      const wrapper = mountComponent()

      const items = wrapper.findAll('.factor-funnel__item')
      items.forEach((item, index) => {
        const style = item.attributes('style')
        expect(style).toContain(`--item-index: ${index}`)
      })
    })
  })

  describe('test_connector_display', () => {
    it('should show connector for items after first', () => {
      const wrapper = mountComponent()

      const connectors = wrapper.findAll('.factor-funnel__item-connector')
      expect(connectors.length).toBe(2)
    })

    it('should not show connector for first item', () => {
      const wrapper = mountComponent()

      const firstItem = wrapper.find('.factor-funnel__item')
      expect(firstItem.find('.factor-funnel__item-connector').exists()).toBe(false)
    })
  })
})