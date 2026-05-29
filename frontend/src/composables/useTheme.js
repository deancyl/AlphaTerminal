import { ref, watch, onMounted, readonly, computed } from 'vue'
import { getDynamicThemeColors } from '../utils/echartsTheme.js'

export const THEMES = {
  DARK: 'dark',
  BLACK: 'black',
  WIND: 'wind',
  LIGHT: 'light'
}

export const THEME_NAMES = {
  [THEMES.DARK]: '深色',
  [THEMES.BLACK]: '全黑',
  [THEMES.WIND]: 'Wind',
  [THEMES.LIGHT]: '亮色'
}

export const THEME_ICONS = {
  [THEMES.DARK]: '🌙',
  [THEMES.BLACK]: '⚫',
  [THEMES.WIND]: '💼',
  [THEMES.LIGHT]: '☀️'
}

export const COLOR_MODES = {
  cn: { up: 'bull', down: 'bear' },
  intl: { up: 'bear', down: 'bull' }
}

export const COLOR_MODE_NAMES = {
  cn: '中国惯例（红涨绿跌）',
  intl: '国际惯例（绿涨红跌）'
}

const currentTheme = ref(THEMES.DARK)
const currentColorMode = ref('cn')
const isInitialized = ref(false)
const themeChangeCallbacks = new Set()

export function onThemeChange(cb) {
  themeChangeCallbacks.add(cb)
  return () => themeChangeCallbacks.delete(cb)
}

/**
 * Get theme color by name or CSS variable.
 * 
 * @param {string} nameOrVar - Either a named color ('primary', 'warning', etc.) 
 *                              or CSS variable ('--color-primary')
 * @param {string} fallback - Fallback value if color not found
 * @returns {string} Color value
 * 
 * Named colors map:
 *   - 'primary' → --color-primary (brand accent)
 *   - 'bull' / 'up' → --color-bull (上涨 color)
 *   - 'bear' / 'down' → --color-bear (下跌 color)
 *   - 'warning' → Standard warning yellow (#fbbf24)
 *   - 'success' → Standard success green (#22c55e)
 *   - 'error' → Standard error red (#ef4444)
 *   - 'info' → Standard info blue (#3b82f6)
 *   - 'bg-base', 'bg-surface', 'text-primary', etc. → Corresponding CSS vars
 */
export function getThemeColor(nameOrVar, fallback = '') {
  // Named color map (semantic aliases)
  const NAMED_COLORS = {
    // Brand colors
    'primary': '--color-primary',
    'primary-hover': '--color-primary-hover',
    
    // Market colors (涨跌)
    'bull': '--color-bull',
    'up': '--color-bull',
    'bear': '--color-bear',
    'down': '--color-bear',
    'bull-light': '--color-bull-light',
    'bear-light': '--color-bear-light',
    
    // Background colors
    'bg-base': '--bg-base',
    'bg-surface': '--bg-surface',
    'bg-surface-hover': '--bg-surface-hover',
    
    // Text colors
    'text-primary': '--text-primary',
    'text-secondary': '--text-secondary',
    'text-muted': '--text-muted',
    
    // Border colors
    'border-base': '--border-base',
    'border-light': '--border-light',
    
    // Chart colors
    'chart-grid': '--chart-grid',
    'chart-text': '--chart-text',
    'chart-line': '--chart-line',
    
    // Semantic colors (standard values, not CSS vars)
    'warning': '#fbbf24',
    'success': '#22c55e',
    'error': '#ef4444',
    'info': '#3b82f6',
    
    // Indicator colors (MA/MACD/Overlay)
    'ma5': '--color-ma5',
    'ma10': '--color-ma10',
    'ma20': '--color-ma20',
    'ma60': '--color-ma60',
    'macd-dif': '--color-macd-dif',
    'macd-dea': '--color-macd-dea',
    'macd-hist': '--color-macd-hist',
    'overlay': '--color-overlay',
    'oi': '--color-oi',
    'flat': '--color-flat',
  }
  
  // If it's a named color, get the CSS var or return the value
  if (NAMED_COLORS[nameOrVar]) {
    const mapped = NAMED_COLORS[nameOrVar]
    // If mapped starts with '--', it's a CSS variable
    if (mapped.startsWith('--')) {
      return getComputedStyle(document.documentElement).getPropertyValue(mapped).trim() || fallback
    }
    // Otherwise it's a direct color value (like standard semantic colors)
    return mapped
  }
  
  // If it starts with '--', treat as CSS variable
  if (nameOrVar.startsWith('--')) {
    return getComputedStyle(document.documentElement).getPropertyValue(nameOrVar).trim() || fallback
  }
  
  // Return fallback if not found
  return fallback || nameOrVar
}

export function getChartColors() {
  const themeAttr = document.documentElement.getAttribute('data-theme') || THEMES.DARK
  const isLight = themeAttr === THEMES.LIGHT
  
  return {
    isLight,
    bgBase: getThemeColor('--bg-base', '#121212'),
    bgSurface: getThemeColor('--bg-surface', '#1E1E1E'),
    textPrimary: getThemeColor('--text-primary', '#F0F6FC'),
    textSecondary: getThemeColor('--text-secondary', '#C9D1D9'),
    textMuted: getThemeColor('--text-muted', '#8B949E'),
    borderBase: getThemeColor('--border-base', '#30363D'),
    chartGrid: getThemeColor('--chart-grid', '#1C2333'),
    chartText: getThemeColor('--chart-text', '#8B949E'),
    chartLine: getThemeColor('--chart-line', '#0F52BA'),
    colorPrimary: getThemeColor('--color-primary', '#0F52BA'),
    colorBull: getThemeColor('--color-bull', '#E63946'),
    colorBullLight: getThemeColor('--color-bull-light', '#FF6B6B'),
    colorBear: getThemeColor('--color-bear', '#1A936F'),
    colorBearLight: getThemeColor('--color-bear-light', '#5CD899'),
    tooltipBg: isLight ? 'rgba(255,255,255,0.96)' : 'rgba(13,17,23,0.95)',
    tooltipBorder: getThemeColor('--border-base', '#30363D'),
    tooltipText: getThemeColor('--text-primary', '#F0F6FC'),
    ma5: '#F5A623',
    ma10: '#0F52BA',
    ma20: '#A855F7',
    ma60: '#EC4899',
  }
}

export function getIndicatorColors() {
  return {
    ma5: getThemeColor('ma5', '#F5A623'),
    ma10: getThemeColor('ma10', '#0F52BA'),
    ma20: getThemeColor('ma20', '#A855F7'),
    ma60: getThemeColor('ma60', '#EC4899'),
    macdDif: getThemeColor('macd-dif', '#60a5fa'),
    macdDea: getThemeColor('macd-dea', '#f87171'),
    macdHist: getThemeColor('macd-hist', '#22c55e'),
    overlay: getThemeColor('overlay', '#f97316'),
    oi: getThemeColor('oi', '#f59e0b'),
    flat: getThemeColor('flat', '#71717a'),
  }
}

export function getMarketColors(marketType = 'ashare') {
  const colors = getDynamicThemeColors()
  if (marketType === 'ashare') {
    // A股惯例：红涨绿跌
    // colors.bull = 绿色(#10b981), colors.bear = 红色(#ef4444)
    // up(上涨) = 红色 = colors.bear, down(下跌) = 绿色 = colors.bull
    return { up: colors.bear, down: colors.bull }
  }
  // 国际惯例：绿涨红跌
  return { up: colors.bull, down: colors.bear }
}
  function applyTheme(theme) {
  const root = document.documentElement
  
    if (!Object.values(THEMES).includes(theme)) {
      console.warn(`[Theme] Unknown theme: ${theme}`)
      return
  }
  
  root.setAttribute('data-theme', theme)
  
  document.body.className = `theme-${theme} font-mono antialiased`
  
  themeChangeCallbacks.forEach(cb => {
    try { cb(theme) } catch (e) { console.error('[Theme] callback error:', e) }
  })
  
  console.log(`[Theme] Switched to: ${THEME_NAMES[theme]}`)
}

function initTheme() {
  if (isInitialized.value) return
  
  const savedTheme = localStorage.getItem('alphaterminal-theme')
  
  if (savedTheme && Object.values(THEMES).includes(savedTheme)) {
    currentTheme.value = savedTheme
  } else {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    currentTheme.value = prefersDark ? THEMES.DARK : THEMES.LIGHT
  }
  
  applyTheme(currentTheme.value)
  isInitialized.value = true
}

function setTheme(theme) {
  if (Object.values(THEMES).includes(theme)) {
    currentTheme.value = theme
    localStorage.setItem('alphaterminal-theme', theme)
  }
}

function cycleTheme() {
  const themeList = Object.values(THEMES)
  const currentIndex = themeList.indexOf(currentTheme.value)
  const nextIndex = (currentIndex + 1) % themeList.length
  setTheme(themeList[nextIndex])
}

let watchInitialized = false

export function useTheme() {
  onMounted(() => {
    initTheme()
    initColorMode()
  })
  
  if (!watchInitialized) {
    watch(currentTheme, (newTheme) => {
      applyTheme(newTheme)
    })
    watchInitialized = true
  }
  
  const activeTheme = computed(() => currentTheme.value)
  const isDark = computed(() => 
    currentTheme.value === THEMES.DARK || 
    currentTheme.value === THEMES.BLACK || 
    currentTheme.value === THEMES.WIND
  )
  const isLight = computed(() => currentTheme.value === THEMES.LIGHT)
  
  return {
    theme: readonly(currentTheme),
    activeTheme,
    currentTheme,
    isDark,
    isLight,
    isWind: () => currentTheme.value === THEMES.WIND,
    setTheme,
    cycleTheme,
    onThemeChange,
    getChartColors,
    getThemeColor,
    THEMES,
    THEME_NAMES,
    THEME_ICONS,
    colorMode: readonly(currentColorMode),
    currentColorMode,
    setColorMode,
    cycleColorMode,
    COLOR_MODES,
    COLOR_MODE_NAMES,
  }
}

function initColorMode() {
  const saved = localStorage.getItem('alphaterminal-colorMode')
  if (saved && (saved === 'cn' || saved === 'intl')) {
    currentColorMode.value = saved
  } else {
    currentColorMode.value = 'cn'
  }
  applyColorMode(currentColorMode.value)
}

function applyColorMode(mode) {
  const root = document.documentElement
  root.setAttribute('data-color-mode', mode)
  console.log(`[ColorMode] Switched to: ${COLOR_MODE_NAMES[mode]}`)
}

function setColorMode(mode) {
  if (mode === 'cn' || mode === 'intl') {
    currentColorMode.value = mode
    localStorage.setItem('alphaterminal-colorMode', mode)
    applyColorMode(mode)
  }
}

function cycleColorMode() {
  const next = currentColorMode.value === 'cn' ? 'intl' : 'cn'
  setColorMode(next)
}