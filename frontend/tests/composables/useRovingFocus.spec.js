/**
 * useRovingFocus.spec.js — Roving Focus Keyboard Navigation Tests
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref, nextTick } from 'vue'
import { useRovingFocus } from '../../src/composables/useRovingFocus.js'

describe('useRovingFocus', () => {
  let container
  let items

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    
    items = ref([
      { symbol: '000001', name: '上证指数' },
      { symbol: '000300', name: '沪深300' },
      { symbol: '399001', name: '深证成指' },
      { symbol: '399006', name: '创业板指' },
      { symbol: 'GOLD', name: '黄金' },
      { symbol: 'WTI', name: '原油' },
      { symbol: 'VIX', name: '恐慌指数' },
      { symbol: 'CNHUSD', name: '离岸人民币' }
    ])
    
    items.value.forEach((item, index) => {
      const card = document.createElement('div')
      card.setAttribute('data-wind-card', '')
      card.setAttribute('tabindex', index === 0 ? '0' : '-1')
      card.setAttribute('role', 'button')
      card.setAttribute('aria-label', item.name)
      container.appendChild(card)
    })
  })

  afterEach(() => {
    document.body.removeChild(container)
  })

  describe('Arrow Key Navigation', () => {
    it('should navigate right with ArrowRight', async () => {
      const containerRef = ref(container)
      const { currentIndex, focusCard } = useRovingFocus({
        containerRef,
        items,
        columns: 2
      })

      expect(currentIndex.value).toBe(0)
      
      focusCard(1)
      await nextTick()
      expect(currentIndex.value).toBe(1)
    })

    it('should navigate left with ArrowLeft', async () => {
      const containerRef = ref(container)
      const { currentIndex, focusCard } = useRovingFocus({
        containerRef,
        items,
        columns: 2
      })

      focusCard(1)
      await nextTick()
      expect(currentIndex.value).toBe(1)
      
      focusCard(0)
      await nextTick()
      expect(currentIndex.value).toBe(0)
    })

    it('should navigate down with ArrowDown in 2-column grid', async () => {
      const containerRef = ref(container)
      const { currentIndex, focusCard } = useRovingFocus({
        containerRef,
        items,
        columns: 2
      })

      focusCard(0)
      await nextTick()
      expect(currentIndex.value).toBe(0)
      
      focusCard(2)
      await nextTick()
      expect(currentIndex.value).toBe(2)
    })

    it('should navigate up with ArrowUp in 2-column grid', async () => {
      const containerRef = ref(container)
      const { currentIndex, focusCard } = useRovingFocus({
        containerRef,
        items,
        columns: 2
      })

      focusCard(2)
      await nextTick()
      expect(currentIndex.value).toBe(2)
      
      focusCard(0)
      await nextTick()
      expect(currentIndex.value).toBe(0)
    })

    it('should wrap right to first item when at last item', async () => {
      const containerRef = ref(container)
      const { currentIndex, focusCard } = useRovingFocus({
        containerRef,
        items,
        columns: 2
      })

      focusCard(7)
      await nextTick()
      expect(currentIndex.value).toBe(7)
      
      focusCard(0)
      await nextTick()
      expect(currentIndex.value).toBe(0)
    })

    it('should wrap left to last item when at first item', async () => {
      const containerRef = ref(container)
      const { currentIndex, focusCard } = useRovingFocus({
        containerRef,
        items,
        columns: 2
      })

      focusCard(0)
      await nextTick()
      expect(currentIndex.value).toBe(0)
      
      focusCard(7)
      await nextTick()
      expect(currentIndex.value).toBe(7)
    })
  })

  describe('Home/End Keys', () => {
    it('should go to first item with Home key', async () => {
      const containerRef = ref(container)
      const { currentIndex, focusCard, reset } = useRovingFocus({
        containerRef,
        items,
        columns: 2
      })

      focusCard(5)
      await nextTick()
      expect(currentIndex.value).toBe(5)
      
      reset()
      await nextTick()
      expect(currentIndex.value).toBe(0)
    })

    it('should go to last item with End key', async () => {
      const containerRef = ref(container)
      const { currentIndex, focusCard } = useRovingFocus({
        containerRef,
        items,
        columns: 2
      })

      focusCard(7)
      await nextTick()
      expect(currentIndex.value).toBe(7)
    })
  })

  describe('Enter/Space Selection', () => {
    it('should trigger onSelect callback with Enter key', async () => {
      const onSelect = vi.fn()
      const containerRef = ref(container)
      const { currentIndex, handleKeydown } = useRovingFocus({
        containerRef,
        items,
        columns: 2,
        onSelect
      })

      const event = new KeyboardEvent('keydown', { key: 'Enter' })
      handleKeydown(event)
      
      expect(onSelect).toHaveBeenCalledWith(items.value[currentIndex.value])
    })

    it('should trigger onSelect callback with Space key', async () => {
      const onSelect = vi.fn()
      const containerRef = ref(container)
      const { currentIndex, handleKeydown } = useRovingFocus({
        containerRef,
        items,
        columns: 2,
        onSelect
      })

      const event = new KeyboardEvent('keydown', { key: ' ' })
      handleKeydown(event)
      
      expect(onSelect).toHaveBeenCalledWith(items.value[currentIndex.value])
    })
  })

  describe('Roving Tabindex', () => {
    it('should only have one element with tabindex="0"', async () => {
      const containerRef = ref(container)
      useRovingFocus({
        containerRef,
        items,
        columns: 2
      })

      await nextTick()
      
      const focusableCards = container.querySelectorAll('[tabindex="0"]')
      expect(focusableCards.length).toBe(1)
    })

    it('should update tabindex when focus changes', async () => {
      const containerRef = ref(container)
      const { focusCard } = useRovingFocus({
        containerRef,
        items,
        columns: 2
      })

      await nextTick()
      
      const cards = container.querySelectorAll('[data-wind-card]')
      expect(cards[0].getAttribute('tabindex')).toBe('0')
      expect(cards[1].getAttribute('tabindex')).toBe('-1')
      
      focusCard(3)
      await nextTick()
      
      expect(cards[0].getAttribute('tabindex')).toBe('-1')
      expect(cards[3].getAttribute('tabindex')).toBe('0')
    })
  })

  describe('Click Handling', () => {
    it('should update focus index on card click', async () => {
      const containerRef = ref(container)
      const { currentIndex, handleCardClick } = useRovingFocus({
        containerRef,
        items,
        columns: 2
      })

      handleCardClick(5)
      await nextTick()
      
      expect(currentIndex.value).toBe(5)
    })
  })

  describe('Edge Cases', () => {
    it('should handle empty items array', async () => {
      const emptyItems = ref([])
      const containerRef = ref(container)
      const { currentIndex, itemCount } = useRovingFocus({
        containerRef,
        items: emptyItems,
        columns: 2
      })

      expect(itemCount.value).toBe(0)
      expect(currentIndex.value).toBe(0)
    })

    it('should handle single item', async () => {
      const singleItem = ref([{ symbol: '000001', name: '上证指数' }])
      
      while (container.firstChild) {
        container.removeChild(container.firstChild)
      }
      
      const card = document.createElement('div')
      card.setAttribute('data-wind-card', '')
      card.setAttribute('tabindex', '0')
      container.appendChild(card)
      
      const containerRef = ref(container)
      const { currentIndex, itemCount } = useRovingFocus({
        containerRef,
        items: singleItem,
        columns: 2
      })

      expect(itemCount.value).toBe(1)
      expect(currentIndex.value).toBe(0)
    })

    it('should handle non-rectangular grid (odd number of items)', async () => {
      const oddItems = ref([
        { symbol: '000001', name: '上证指数' },
        { symbol: '000300', name: '沪深300' },
        { symbol: '399001', name: '深证成指' },
        { symbol: '399006', name: '创业板指' },
        { symbol: 'GOLD', name: '黄金' }
      ])
      
      while (container.firstChild) {
        container.removeChild(container.firstChild)
      }
      
      oddItems.value.forEach((item, index) => {
        const card = document.createElement('div')
        card.setAttribute('data-wind-card', '')
        card.setAttribute('tabindex', index === 0 ? '0' : '-1')
        container.appendChild(card)
      })
      
      const containerRef = ref(container)
      const { currentIndex, focusCard } = useRovingFocus({
        containerRef,
        items: oddItems,
        columns: 2
      })

      focusCard(4)
      await nextTick()
      expect(currentIndex.value).toBe(4)
    })
  })

  describe('Accessibility', () => {
    it('should set role="button" on cards', async () => {
      const containerRef = ref(container)
      useRovingFocus({
        containerRef,
        items,
        columns: 2
      })

      await nextTick()
      
      const cards = container.querySelectorAll('[data-wind-card]')
      cards.forEach(card => {
        expect(card.getAttribute('role')).toBe('button')
      })
    })

    it('should set aria-label on cards', async () => {
      const containerRef = ref(container)
      useRovingFocus({
        containerRef,
        items,
        columns: 2
      })

      await nextTick()
      
      const cards = container.querySelectorAll('[data-wind-card]')
      cards.forEach((card, index) => {
        expect(card.getAttribute('aria-label')).toBeTruthy()
      })
    })
  })
})
