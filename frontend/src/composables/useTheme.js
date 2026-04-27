/**
 * useTheme.js — 四主题管理系统
 * 
 * 主题列表：
 * 1. DARK (dark) - 原始深色主题（默认）
 * 2. BLACK (black) - 全黑 OLED 主题
 * 3. WIND (wind) - Wind 金融终端风格
 * 4. LIGHT (light) - 专业亮色主题
 * 
 * 使用 CSS 变量实现，localStorage 持久化
 */
import { ref, watch, onMounted, readonly } from 'vue'
import { logger } from '../utils/logger.js'

// 主题类型
export const THEMES = {
  DARK: 'dark',
  BLACK: 'black',
  WIND: 'wind',
  LIGHT: 'light'
}

// 主题显示名称
export const THEME_NAMES = {
  [THEMES.DARK]: '深色',
  [THEMES.BLACK]: '全黑',
  [THEMES.WIND]: 'Wind',
  [THEMES.LIGHT]: '亮色'
}

// 主题图标
export const THEME_ICONS = {
  [THEMES.DARK]: '🌙',
  [THEMES.BLACK]: '⚫',
  [THEMES.WIND]: '💼',
  [THEMES.LIGHT]: '☀️'
}

// 当前主题状态
const currentTheme = ref(THEMES.DARK)
const isInitialized = ref(false)

/**
 * 主题配色配置
 * 每个主题定义完整的 CSS 变量集
 */
const THEME_CONFIG = {
  // ============================================
  // 1. 原始深色主题 (DARK) - 默认
  // ============================================
  [THEMES.DARK]: {
    // 背景色
    '--bg-primary': '#0a0e17',
    '--bg-secondary': '#111827',
    '--bg-tertiary': '#1f2937',
    '--bg-hover': 'rgba(255,255,255,0.05)',
    '--bg-active': 'rgba(0,255,136,0.10)',
    
    // 文字色
    '--text-primary': '#f3f4f6',
    '--text-secondary': '#9ca3af',
    '--text-tertiary': '#6b7280',
    '--text-muted': '#4b5563',
    
    // 边框色
    '--border-primary': '#374151',
    '--border-secondary': '#1f2937',
    '--border-hover': '#4b5563',
    
    // 强调色（终端绿）
    '--accent-primary': '#00ff88',
    '--accent-secondary': '#00cc6a',
    '--accent-bg': 'rgba(0,255,136,0.10)',
    '--accent-border': 'rgba(0,255,136,0.30)',
    
    // 面板背景
    '--panel-bg': '#111827',
    '--panel-bg-elevated': '#1f2937',
    '--panel-bg-hover': '#1f2937',
    
    // 涨跌色（A股传统：红涨绿跌）
    '--bullish': '#ef232a',
    '--bullish-light': '#f87171',
    '--bullish-bg': 'rgba(239,35,42,0.15)',
    '--bullish-border': 'rgba(239,35,42,0.30)',
    '--bearish': '#14b143',
    '--bearish-light': '#4ade80',
    '--bearish-bg': 'rgba(20,177,67,0.15)',
    '--bearish-border': 'rgba(20,177,67,0.30)',
    
    // 状态色
    '--status-live': '#00ff88',
    '--status-warning': '#fbbf24',
    '--status-error': '#ef4444',
    '--status-info': '#60a5fa',
    '--status-success': '#22c55e',
    
    // 图表配色
    '--chart-grid': '#1f2937',
    '--chart-text': '#6b7280',
    '--chart-line': '#00ff88',
    '--chart-area': 'rgba(0,255,136,0.1)',
    
    // 阴影
    '--shadow-sm': '0 1px 2px rgba(0,0,0,0.3)',
    '--shadow-md': '0 4px 6px rgba(0,0,0,0.4)',
    '--shadow-lg': '0 10px 15px rgba(0,0,0,0.5)',
    
    // 滚动条
    '--scrollbar-track': '#111827',
    '--scrollbar-thumb': '#374151',
    '--scrollbar-thumb-hover': '#4b5563',
  },
  
  // ============================================
  // 2. 全黑 OLED 主题 (BLACK)
  // ============================================
  [THEMES.BLACK]: {
    // 背景色 - 纯黑节省 OLED 电量
    '--bg-primary': '#000000',
    '--bg-secondary': '#0a0a0a',
    '--bg-tertiary': '#141414',
    '--bg-hover': 'rgba(255,255,255,0.08)',
    '--bg-active': 'rgba(0,255,136,0.15)',
    
    // 文字色 - 高对比度
    '--text-primary': '#ffffff',
    '--text-secondary': '#b0b0b0',
    '--text-tertiary': '#808080',
    '--text-muted': '#505050',
    
    // 边框色 - 极细边框
    '--border-primary': '#2a2a2a',
    '--border-secondary': '#1a1a1a',
    '--border-hover': '#3a3a3a',
    
    // 强调色（更亮的终端绿）
    '--accent-primary': '#00ff88',
    '--accent-secondary': '#00ffaa',
    '--accent-bg': 'rgba(0,255,136,0.15)',
    '--accent-border': 'rgba(0,255,136,0.40)',
    
    // 面板背景
    '--panel-bg': '#0a0a0a',
    '--panel-bg-elevated': '#141414',
    '--panel-bg-hover': '#1a1a1a',
    
    // 涨跌色（更鲜艳）
    '--bullish': '#ff3333',
    '--bullish-light': '#ff6666',
    '--bullish-bg': 'rgba(255,51,51,0.20)',
    '--bullish-border': 'rgba(255,51,51,0.40)',
    '--bearish': '#33ff66',
    '--bearish-light': '#66ff88',
    '--bearish-bg': 'rgba(51,255,102,0.20)',
    '--bearish-border': 'rgba(51,255,102,0.40)',
    
    // 状态色
    '--status-live': '#00ff88',
    '--status-warning': '#ffcc00',
    '--status-error': '#ff4444',
    '--status-info': '#44aaff',
    '--status-success': '#44ff66',
    
    // 图表配色
    '--chart-grid': '#1a1a1a',
    '--chart-text': '#606060',
    '--chart-line': '#00ff88',
    '--chart-area': 'rgba(0,255,136,0.15)',
    
    // 阴影
    '--shadow-sm': '0 1px 2px rgba(0,0,0,0.5)',
    '--shadow-md': '0 4px 6px rgba(0,0,0,0.6)',
    '--shadow-lg': '0 10px 15px rgba(0,0,0,0.7)',
    
    // 滚动条
    '--scrollbar-track': '#0a0a0a',
    '--scrollbar-thumb': '#2a2a2a',
    '--scrollbar-thumb-hover': '#3a3a3a',
  },
  
  // ============================================
  // 3. Wind 金融终端风格 (WIND)
  // ============================================
  [THEMES.WIND]: {
    // 背景色 - Wind 经典深蓝灰
    '--bg-primary': '#1a1f2e',
    '--bg-secondary': '#232838',
    '--bg-tertiary': '#2d3447',
    '--bg-hover': 'rgba(255,255,255,0.06)',
    '--bg-active': 'rgba(255,193,7,0.15)',
    
    // 文字色
    '--text-primary': '#e8eaed',
    '--text-secondary': '#a8adb5',
    '--text-tertiary': '#7a8194',
    '--text-muted': '#5a6270',
    
    // 边框色
    '--border-primary': '#3d4559',
    '--border-secondary': '#2a3142',
    '--border-hover': '#4d5669',
    
    // 强调色（Wind 金橙色）
    '--accent-primary': '#ffc107',
    '--accent-secondary': '#ffb300',
    '--accent-bg': 'rgba(255,193,7,0.15)',
    '--accent-border': 'rgba(255,193,7,0.35)',
    
    // 面板背景
    '--panel-bg': '#232838',
    '--panel-bg-elevated': '#2d3447',
    '--panel-bg-hover': '#353d52',
    
    // 涨跌色（Wind 风格：红涨绿跌，更饱和）
    '--bullish': '#ff4d4f',
    '--bullish-light': '#ff7875',
    '--bullish-bg': 'rgba(255,77,79,0.15)',
    '--bullish-border': 'rgba(255,77,79,0.35)',
    '--bearish': '#52c41a',
    '--bearish-light': '#73d13d',
    '--bearish-bg': 'rgba(82,196,26,0.15)',
    '--bearish-border': 'rgba(82,196,26,0.35)',
    
    // 状态色
    '--status-live': '#ffc107',
    '--status-warning': '#faad14',
    '--status-error': '#ff4d4f',
    '--status-info': '#1890ff',
    '--status-success': '#52c41a',
    
    // 图表配色
    '--chart-grid': '#2a3142',
    '--chart-text': '#7a8194',
    '--chart-line': '#ffc107',
    '--chart-area': 'rgba(255,193,7,0.12)',
    
    // 阴影
    '--shadow-sm': '0 1px 2px rgba(0,0,0,0.3)',
    '--shadow-md': '0 4px 8px rgba(0,0,0,0.4)',
    '--shadow-lg': '0 8px 16px rgba(0,0,0,0.5)',
    
    // 滚动条
    '--scrollbar-track': '#232838',
    '--scrollbar-thumb': '#3d4559',
    '--scrollbar-thumb-hover': '#4d5669',
  },
  
  // ============================================
  // 4. 专业亮色主题 (LIGHT)
  // ============================================
  [THEMES.LIGHT]: {
    // 背景色 - 专业金融白
    '--bg-primary': '#f5f6f8',
    '--bg-secondary': '#ffffff',
    '--bg-tertiary': '#f0f1f3',
    '--bg-hover': 'rgba(0,0,0,0.04)',
    '--bg-active': 'rgba(24,144,255,0.10)',
    
    // 文字色 - 层次分明的灰度
    '--text-primary': '#1a1a1a',
    '--text-secondary': '#4a4a4a',
    '--text-tertiary': '#7a7a7a',
    '--text-muted': '#a0a0a0',
    
    // 边框色
    '--border-primary': '#d9d9d9',
    '--border-secondary': '#e8e8e8',
    '--border-hover': '#bfbfbf',
    
    // 强调色（专业蓝）
    '--accent-primary': '#1890ff',
    '--accent-secondary': '#096dd9',
    '--accent-bg': 'rgba(24,144,255,0.10)',
    '--accent-border': 'rgba(24,144,255,0.30)',
    
    // 面板背景
    '--panel-bg': '#ffffff',
    '--panel-bg-elevated': '#fafafa',
    '--panel-bg-hover': '#f5f5f5',
    
    // 涨跌色（亮色主题使用更克制的颜色）
    '--bullish': '#cf1322',
    '--bullish-light': '#ff4d4f',
    '--bullish-bg': 'rgba(207,19,34,0.08)',
    '--bullish-border': 'rgba(207,19,34,0.25)',
    '--bearish': '#389e0d',
    '--bearish-light': '#52c41a',
    '--bearish-bg': 'rgba(56,158,13,0.08)',
    '--bearish-border': 'rgba(56,158,13,0.25)',
    
    // 状态色
    '--status-live': '#1890ff',
    '--status-warning': '#faad14',
    '--status-error': '#cf1322',
    '--status-info': '#1890ff',
    '--status-success': '#389e0d',
    
    // 图表配色
    '--chart-grid': '#e8e8e8',
    '--chart-text': '#a0a0a0',
    '--chart-line': '#1890ff',
    '--chart-area': 'rgba(24,144,255,0.1)',
    
    // 阴影
    '--shadow-sm': '0 1px 2px rgba(0,0,0,0.08)',
    '--shadow-md': '0 4px 8px rgba(0,0,0,0.10)',
    '--shadow-lg': '0 8px 16px rgba(0,0,0,0.12)',
    
    // 滚动条
    '--scrollbar-track': '#f0f1f3',
    '--scrollbar-thumb': '#d9d9d9',
    '--scrollbar-thumb-hover': '#bfbfbf',
  }
}

// 主题变化监听器
const themeChangeCallbacks = new Set()

/**
 * 订阅主题变化（供图表等组件使用）
 * @param {Function} cb - callback(theme)
 * @returns {Function} unsubscribe
 */
export function onThemeChange(cb) {
  themeChangeCallbacks.add(cb)
  return () => themeChangeCallbacks.delete(cb)
}

/**
 * 获取当前主题的 CSS 变量原始值
 */
function getThemeVariable(name, fallback = '') {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}

/**
 * 获取当前主题完整配色（供 ECharts / Canvas 使用）
 */
export function getChartColors() {
  const themeAttr = document.documentElement.getAttribute('data-theme') || THEMES.DARK
  const isLight = themeAttr === THEMES.LIGHT
  const bgPrimary   = getThemeVariable('--bg-primary', '#0a0e17')
  const textPrimary   = getThemeVariable('--text-primary', '#f3f4f6')
  const textSecondary = getThemeVariable('--text-secondary', '#9ca3af')
  const textTertiary  = getThemeVariable('--text-tertiary', '#6b7280')
  const borderPrimary = getThemeVariable('--border-primary', '#374151')
  const borderSecondary = getThemeVariable('--border-secondary', '#1f2937')
  const chartGrid     = getThemeVariable('--chart-grid', '#1f2937')
  const chartText     = getThemeVariable('--chart-text', '#6b7280')
  const chartLine     = getThemeVariable('--chart-line', '#00ff88')
  const accentPrimary = getThemeVariable('--accent-primary', '#00ff88')
  const bullish       = getThemeVariable('--bullish', '#ef232a')
  const bullishLight  = getThemeVariable('--bullish-light', '#f87171')
  const bearish       = getThemeVariable('--bearish', '#14b143')
  const bearishLight  = getThemeVariable('--bearish-light', '#4ade80')
  const panelBg       = getThemeVariable('--panel-bg', '#111827')

  // 根据主题调整 tooltip / overlay 透明度
  const tooltipBg = isLight
    ? 'rgba(255,255,255,0.96)'
    : 'rgba(10,14,23,0.95)'
  const tooltipBorder = borderPrimary
  const tooltipText = textPrimary

  return {
    bgPrimary,
    isLight,
    textPrimary,
    textSecondary,
    textTertiary,
    borderPrimary,
    borderSecondary,
    chartGrid,
    chartText,
    chartLine,
    accentPrimary,
    bullish,
    bullishLight,
    bearish,
    bearishLight,
    panelBg,
    tooltipBg,
    tooltipBorder,
    tooltipText,
    // 辅助色（指标线颜色固定但会根据主题微调亮度）
    ma5:  '#fbbf24',
    ma10: '#60a5fa',
    ma20: '#c084fc',
    ma60: '#f472b6',
  }
}

/**
 * 应用主题到 DOM
 */
function applyTheme(theme) {
  const root = document.documentElement
  const config = THEME_CONFIG[theme]

  if (!config) {
    logger.warn(`[Theme] 未知主题: ${theme}`)
    return
  }

  // 设置 CSS 变量
  Object.entries(config).forEach(([key, value]) => {
    root.style.setProperty(key, value)
  })

  // 设置 data-theme 属性
  root.setAttribute('data-theme', theme)

  // 更新 body 类名
  document.body.className = `theme-${theme} font-mono antialiased`

  // 通知监听者
  themeChangeCallbacks.forEach(cb => {
    try { cb(theme) } catch (e) { logger.error('[Theme] callback error:', e) }
  })

  logger.log(`[Theme] 已切换至: ${THEME_NAMES[theme]}`)
}

/**
 * 初始化主题
 */
function initTheme() {
  if (isInitialized.value) return

  // 从 localStorage 读取保存的主题
  const savedTheme = localStorage.getItem('alphaterminal-theme')

  // 验证并应用主题
  if (savedTheme && Object.values(THEMES).includes(savedTheme)) {
    currentTheme.value = savedTheme
  } else {
    // 默认使用深色主题
    currentTheme.value = THEMES.DARK
  }

  applyTheme(currentTheme.value)
  isInitialized.value = true
}

/**
 * 切换到指定主题
 */
function setTheme(theme) {
  if (Object.values(THEMES).includes(theme)) {
    currentTheme.value = theme
    localStorage.setItem('alphaterminal-theme', theme)
  }
}

/**
 * 切换到下一个主题（循环）
 */
function cycleTheme() {
  const themeList = Object.values(THEMES)
  const currentIndex = themeList.indexOf(currentTheme.value)
  const nextIndex = (currentIndex + 1) % themeList.length
  setTheme(themeList[nextIndex])
}

// 监听主题变化
let watchInitialized = false

export function useTheme() {
  onMounted(() => {
    initTheme()
  })

  if (!watchInitialized) {
    watch(currentTheme, (newTheme) => {
      applyTheme(newTheme)
    })
    watchInitialized = true
  }

  return {
    theme: readonly(currentTheme),
    currentTheme,
    isDark: () => currentTheme.value === THEMES.DARK || currentTheme.value === THEMES.BLACK,
    isLight: () => currentTheme.value === THEMES.LIGHT,
    isWind: () => currentTheme.value === THEMES.WIND,
    setTheme,
    cycleTheme,
    onThemeChange,
    getChartColors,
    THEMES,
    THEME_NAMES,
    THEME_ICONS,
  }
}
