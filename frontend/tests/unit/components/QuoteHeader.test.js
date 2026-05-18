import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import QuoteHeader from '../QuoteHeader.vue'

describe('QuoteHeader', () => {
  const defaultProps = {
    name: '上证指数',
    symbol: 'sh000001',
    quote: {
      price: 3100.50,
      change: 15.30,
      change_pct: 0.50,
      volume: 150000000,
      amount: 25000000000,
      amplitude: 1.2,
      turnover_rate: 0.35
    },
    period: 'daily',
    adjustment: 'none',
    yAxisType: 'linear'
  }
  
  it('renders name and code correctly', () => {
    const wrapper = mount(QuoteHeader, {
      props: defaultProps
    })
    expect(wrapper.text()).toContain('上证指数')
    expect(wrapper.text()).toContain('000001')
  })
  
  it('displays price with correct formatting', () => {
    const wrapper = mount(QuoteHeader, {
      props: defaultProps
    })
    expect(wrapper.text()).toContain('3100.50')
  })
  
  it('displays change with positive sign for gains', () => {
    const wrapper = mount(QuoteHeader, {
      props: {
        ...defaultProps,
        quote: { ...defaultProps.quote, change: 15.30, change_pct: 0.50 }
      }
    })
    expect(wrapper.text()).toContain('+15.30')
    expect(wrapper.text()).toContain('+0.50')
  })
  
  it('displays change without positive sign for losses', () => {
    const wrapper = mount(QuoteHeader, {
      props: {
        ...defaultProps,
        quote: { ...defaultProps.quote, change: -20.50, change_pct: -0.65 }
      }
    })
    expect(wrapper.text()).toContain('-20.50')
    expect(wrapper.text()).toContain('-0.65')
  })
  
  it('handles null quote gracefully', () => {
    const wrapper = mount(QuoteHeader, {
      props: {
        ...defaultProps,
        quote: {}
      }
    })
    expect(wrapper.text()).toContain('--')
  })
  
  it('handles null price gracefully', () => {
    const wrapper = mount(QuoteHeader, {
      props: {
        ...defaultProps,
        quote: { price: null }
      }
    })
    expect(wrapper.text()).toContain('--')
  })
  
  it('displays period buttons', () => {
    const wrapper = mount(QuoteHeader, {
      props: defaultProps
    })
    expect(wrapper.text()).toContain('T')
    expect(wrapper.text()).toContain('D')
    expect(wrapper.text()).toContain('W')
    expect(wrapper.text()).toContain('M')
  })
  
  it('highlights active period', () => {
    const wrapper = mount(QuoteHeader, {
      props: { ...defaultProps, period: 'daily' }
    })
    const dailyBtn = wrapper.findAll('button').find(b => b.text() === 'D')
    expect(dailyBtn?.classes()).toContain('bg-[var(--color-info-bg)]')
  })
  
  it('emits period-change event on click', async () => {
    const wrapper = mount(QuoteHeader, {
      props: defaultProps
    })
    const buttons = wrapper.findAll('button')
    const weeklyBtn = buttons.find(b => b.text() === 'W')
    await weeklyBtn?.trigger('click')
    expect(wrapper.emitted('period-change')).toBeTruthy()
    expect(wrapper.emitted('period-change')?.[0]).toEqual(['weekly'])
  })
  
  it('emits adjustment-change event', async () => {
    const wrapper = mount(QuoteHeader, {
      props: defaultProps
    })
    const buttons = wrapper.findAll('button')
    const adjBtn = buttons.find(b => b.attributes('title') === '复权')
    await adjBtn?.trigger('click')
    expect(wrapper.emitted('adjustment-change')).toBeTruthy()
  })
  
  it('emits yaxis-change event', async () => {
    const wrapper = mount(QuoteHeader, {
      props: defaultProps
    })
    const buttons = wrapper.findAll('button')
    const yaxisBtn = buttons.find(b => b.attributes('title') === 'Y轴坐标系')
    await yaxisBtn?.trigger('click')
    expect(wrapper.emitted('yaxis-change')).toBeTruthy()
  })
  
  it('displays MA values when provided', () => {
    const wrapper = mount(QuoteHeader, {
      props: {
        ...defaultProps,
        maDisplays: [
          { period: 5, value: 3080.50, color: '#f59e0b' },
          { period: 10, value: 3070.25, color: '#22c55e' },
          { period: 20, value: 3050.00, color: '#ef4444' }
        ]
      }
    })
    expect(wrapper.text()).toContain('MA5')
    expect(wrapper.text()).toContain('3080.50')
    expect(wrapper.text()).toContain('MA10')
    expect(wrapper.text()).toContain('3070.25')
  })
  
  it('displays hoverData when provided', () => {
    const wrapper = mount(QuoteHeader, {
      props: {
        ...defaultProps,
        hoverData: {
          date: '2024-01-15',
          open: 3090.00,
          high: 3110.00,
          low: 3085.00,
          close: 3100.50,
          volume: 150000000
        }
      }
    })
    expect(wrapper.text()).toContain('2024-01-15')
    expect(wrapper.text()).toContain('开')
    expect(wrapper.text()).toContain('高')
    expect(wrapper.text()).toContain('低')
    expect(wrapper.text()).toContain('收')
  })
  
  it('formats volume correctly (亿)', () => {
    const wrapper = mount(QuoteHeader, {
      props: {
        ...defaultProps,
        quote: { ...defaultProps.quote, volume: 150000000 }
      }
    })
    expect(wrapper.text()).toContain('1.50亿')
  })
  
  it('formats amount correctly (亿)', () => {
    const wrapper = mount(QuoteHeader, {
      props: {
        ...defaultProps,
        quote: { ...defaultProps.quote, amount: 25000000000 }
      }
    })
    expect(wrapper.text()).toContain('250.00亿')
  })
  
  it('handles zero volume gracefully', () => {
    const wrapper = mount(QuoteHeader, {
      props: {
        ...defaultProps,
        quote: { ...defaultProps.quote, volume: 0 }
      }
    })
    expect(wrapper.text()).toContain('--')
  })
  
  it('shows adjustment indicator when active', () => {
    const wrapper = mount(QuoteHeader, {
      props: { ...defaultProps, adjustment: 'qfq' }
    })
    const buttons = wrapper.findAll('button')
    const adjBtn = buttons.find(b => b.attributes('title') === '复权')
    expect(adjBtn?.classes()).toContain('text-[var(--color-warning)]')
  })
  
  it('shows log scale indicator when active', () => {
    const wrapper = mount(QuoteHeader, {
      props: { ...defaultProps, yAxisType: 'log' }
    })
    const buttons = wrapper.findAll('button')
    const yaxisBtn = buttons.find(b => b.attributes('title') === 'Y轴坐标系')
    expect(yaxisBtn?.classes()).toContain('text-[var(--color-primary)]')
  })
})
