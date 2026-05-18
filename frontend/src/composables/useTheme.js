import { ref, watch, onMounted, readonly, computed } from 'vue'

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

export function getThemeColor(varName, fallback = '') {
  return getComputedStyle(document.documentElement).getPropertyValue(varName).trim() || fallback
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