/**
 * useTheme.js — AlphaTerminal 主题管理系统 v2.0
 * 
 * 遵循万德金融终端UI/UX设计规范 v1.0
 * 支持：DARK(默认深色) / BLACK(OLED纯黑) / WIND(Wind风格) / LIGHT(专业亮色)
 * 
 * 设计规范：
 * - 品牌主色：#0F52BA（万德蓝）
 * - 上涨色：#E63946（红涨 - A股合规）
 * - 下跌色：#1A936F（绿跌 - A股合规）
 * - 基础间距：4px
 * - PC触控区域：≥44px
 * - 移动端触控区域：≥48px
 * - 对比度：≥4.5:1 (WCAG AA)
 */
import { ref, watch, onMounted, readonly } from 'vue'
import { logger } from '../utils/logger.js'

// ============================================
// 主题定义
// ============================================
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

// ============================================
// 颜色模式定义（CN/Intl）
// ============================================
export const COLOR_MODES = {
  cn: { up: '#E63946', down: '#1A936F' },   // 中国：红涨绿跌
  intl: { up: '#1A936F', down: '#E63946' }  // 国际：绿涨红跌
}

export const COLOR_MODE_NAMES = {
  cn: '中国惯例（红涨绿跌）',
  intl: '国际惯例（绿涨红跌）'
}

// ============================================
// 规范色彩定义（遵循万德金融终端UI/UX设计规范 v1.0）
// ============================================
const BRAND_COLORS = {
  primary: '#0F52BA',        // 万德蓝
  primaryHover: '#1A6AD8',
  primaryLight: '#3A7BD8',
  primaryDark: '#0A3D8C',
}

const MARKET_COLORS = {
  up: '#E63946',             // A股上涨色（红）
  down: '#1A936F',           // A股下跌色（绿）
  neutral: '#B0B8CC',
}

const STATUS_COLORS = {
  warning: '#F5A623',
  danger: '#DC2626',
  success: '#16A34A',
  info: '#0F52BA',
}

// ============================================
// 主题配置（完整版）
// ============================================
const THEME_CONFIG = {
  // ============================================
  // 1. 专业深色主题 (DARK) - 默认
  // ============================================
  [THEMES.DARK]: {
    // ── 品牌色 ──
    '--color-primary': BRAND_COLORS.primary,
    '--color-primary-hover': BRAND_COLORS.primaryHover,
    '--color-primary-light': BRAND_COLORS.primaryLight,
    '--color-primary-dark': BRAND_COLORS.primaryDark,
    '--color-primary-bg': 'rgba(15,82,186,0.10)',
    '--color-primary-border': 'rgba(15,82,186,0.30)',
    
    // ── 语义色（涨跌）──
    '--color-up': MARKET_COLORS.up,
    '--color-up-light': '#FF6B6B',
    '--color-up-bg': 'rgba(230,57,70,0.15)',
    '--color-up-border': 'rgba(230,57,70,0.30)',
    '--color-down': MARKET_COLORS.down,
    '--color-down-light': '#5CD899',
    '--color-down-bg': 'rgba(26,147,111,0.15)',
    '--color-down-border': 'rgba(26,147,111,0.30)',
    '--color-neutral': MARKET_COLORS.neutral,
    '--color-neutral-bg': 'rgba(176,184,204,0.10)',
    '--color-neutral-border': 'rgba(176,184,204,0.25)',
    
    // ── 功能状态色 ──
    '--color-warning': STATUS_COLORS.warning,
    '--color-warning-bg': 'rgba(245,166,35,0.15)',
    '--color-warning-border': 'rgba(245,166,35,0.30)',
    '--color-danger': STATUS_COLORS.danger,
    '--color-danger-bg': 'rgba(220,38,38,0.15)',
    '--color-danger-border': 'rgba(220,38,38,0.30)',
    '--color-success': STATUS_COLORS.success,
    '--color-success-bg': 'rgba(22,163,74,0.15)',
    '--color-success-border': 'rgba(22,163,74,0.30)',
    '--color-info': STATUS_COLORS.info,
    '--color-info-bg': 'rgba(15,82,186,0.15)',
    '--color-info-border': 'rgba(15,82,186,0.30)',
    
    // ── 中性色（背景）──
    '--bg-primary': '#121212',
    '--bg-secondary': '#1E1E1E',
    '--bg-tertiary': '#252525',
    '--bg-elevated': '#2C2C2C',
    '--bg-hover': 'rgba(255,255,255,0.05)',
    '--bg-active': 'rgba(15,82,186,0.10)',
    '--bg-overlay': 'rgba(0,0,0,0.60)',
    '--bg-glass': 'rgba(22,27,34,0.95)',
    
    // ── 中性色（文字）──
    '--text-primary': '#F0F6FC',
    '--text-secondary': '#C9D1D9',
    '--text-tertiary': '#8B949E',
    '--text-muted': '#6E7681',
    '--text-disabled': '#484F58',
    '--text-placeholder': '#6E7681',
    '--text-inverse': '#121212',
    
    // ── 中性色（边框）──
    '--border-primary': '#30363D',
    '--border-secondary': '#2C2C2C',
    '--border-focus': BRAND_COLORS.primary,
    '--border-hover': '#484F58',
    
    // ── 面板背景 ──
    '--panel-bg': '#1E1E1E',
    '--panel-bg-elevated': '#2C2C2C',
    '--panel-bg-hover': '#252525',
    '--panel-bg-active': 'rgba(15,82,186,0.08)',
    
    // ── 图表配色 ──
    '--chart-grid': '#1C2333',
    '--chart-text': '#8B949E',
    '--chart-line': BRAND_COLORS.primary,
    '--chart-area': 'rgba(15,82,186,0.10)',
    '--chart-crosshair': 'rgba(240,246,252,0.20)',
    
    // ── 阴影 ──
    '--shadow-sm': '0 1px 2px rgba(0,0,0,0.30)',
    '--shadow-md': '0 4px 8px rgba(0,0,0,0.40)',
    '--shadow-sm': '0 8px 16px rgba(0,0,0,0.50)',
    '--shadow-sm': '0 12px 24px rgba(0,0,0,0.60)',
    '--shadow-glow': `0 0 20px ${BRAND_COLORS.primary}20`,
    
    // ── 滚动条 ──
    '--scrollbar-track': '#1E1E1E',
    '--scrollbar-thumb': '#30363D',
    '--scrollbar-thumb-hover': '#484F58',
    
    // ── 间距系统（4px基础单位）──
    '--space-xs': '4px',
    '--space-sm': '8px',
    '--space-md': '16px',
    '--space-lg': '24px',
    '--space-xl': '32px',
    '--space-2xl': '48px',
    
    // ── 圆角系统 ──
    '--radius-sm': '4px',
    '--radius-md': '6px',
    '--radius-lg': '8px',
    '--radius-xl': '12px',
    '--radius-full': '9999px',
    
    // ── 动效时长 ──
    '--duration-micro': '150ms',
    '--duration-fast': '200ms',
    '--duration-normal': '250ms',
    '--duration-slow': '300ms',
    '--easing-default': 'cubic-bezier(0.2,0,0,1)',
    '--easing-smooth': 'cubic-bezier(0.23,1,0.32,1)',
    '--easing-bounce': 'cubic-bezier(0.4,0,0.2,1)',
    
    // ── 层级系统 ──
    '--z-base': '0',
    '--z-dropdown': '100',
    '--z-sticky': '200',
    '--z-fixed': '300',
    '--z-modal-backdrop': '400',
    '--z-modal': '500',
    '--z-popover': '600',
    '--z-tooltip': '700',
    '--z-toast': '800',
    '--z-max': '9999',
    
    // ── 组件尺寸 ──
    '--btn-height': '36px',
    '--btn-height-sm': '32px',
    '--btn-height-lg': '40px',
    '--input-height': '32px',
    '--input-height-lg': '36px',
    '--table-row': '32px',
    '--table-row-sm': '24px',
    '--table-row-lg': '40px',
    '--table-header': '36px',
    '--tab-height': '36px',
    '--nav-height': '48px',
    '--sidebar-width': '220px',
    '--sidebar-collapsed': '64px',
    '--panel-width': '280px',
    '--touch-min': '44px',
    
    // ── 字体 ──
    '--font-mono': '"JetBrains Mono", "Roboto Mono", "Consolas", monospace',
    '--font-sans': '"PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif',
    '--font-number': '"JetBrains Mono", "Roboto Mono", "Consolas", monospace',
    '--font-feature-tnum': '"tnum"',
    
    // ── 旧版兼容变量（将逐步迁移）──
    '--accent-primary': BRAND_COLORS.primary,
    '--accent-secondary': BRAND_COLORS.primaryHover,
    '--accent-bg': 'rgba(15,82,186,0.10)',
    '--accent-border': 'rgba(15,82,186,0.30)',
    '--bullish': MARKET_COLORS.up,
    '--bullish-light': '#FF5252',
    '--bullish-bg': 'rgba(230,57,70,0.15)',
    '--bullish-border': 'rgba(230,57,70,0.30)',
    '--bearish': MARKET_COLORS.down,
    '--bearish-light': '#5CD8A8',
    '--bearish-bg': 'rgba(26,147,111,0.15)',
    '--bearish-border': 'rgba(26,147,111,0.30)',
    '--status-live': BRAND_COLORS.primary,
    '--status-warning': STATUS_COLORS.warning,
    '--status-error': STATUS_COLORS.danger,
    '--status-info': STATUS_COLORS.info,
    '--status-success': STATUS_COLORS.success,
  },
  
  // ============================================
  // 2. OLED 纯黑主题 (BLACK)
  // ============================================
  [THEMES.BLACK]: {
    // 品牌色
    '--color-primary': '#0F52BA',
    '--color-primary-hover': '#4A8EFF',
    '--color-primary-light': '#5C9DFF',
    '--color-primary-dark': '#1A6AE8',
    '--color-primary-bg': 'rgba(15,82,186,0.12)',
    '--color-primary-border': 'rgba(15,82,186,0.35)',
    
    // 语义色
    '--color-up': '#FF4D4F',
    '--color-up-light': '#FF7875',
    '--color-up-bg': 'rgba(255,77,79,0.20)',
    '--color-up-border': 'rgba(255,77,79,0.40)',
    '--color-down': '#52C41A',
    '--color-down-light': '#73D13D',
    '--color-down-bg': 'rgba(82,196,26,0.20)',
    '--color-down-border': 'rgba(82,196,26,0.40)',
    '--color-neutral': '#B0B8CC',
    '--color-neutral-bg': 'rgba(176,184,204,0.12)',
    '--color-neutral-border': 'rgba(176,184,204,0.28)',
    
    // 功能状态色
    '--color-warning': '#FFCC00',
    '--color-warning-bg': 'rgba(255,204,0,0.18)',
    '--color-warning-border': 'rgba(255,204,0,0.35)',
    '--color-danger': '#FF4444',
    '--color-danger-bg': 'rgba(255,68,68,0.18)',
    '--color-danger-border': 'rgba(255,68,68,0.35)',
    '--color-success': '#44FF66',
    '--color-success-bg': 'rgba(68,255,102,0.18)',
    '--color-success-border': 'rgba(68,255,102,0.35)',
    '--color-info': '#44AAFF',
    '--color-info-bg': 'rgba(68,170,255,0.18)',
    '--color-info-border': 'rgba(68,170,255,0.35)',
    
    // 中性色
    '--bg-primary': '#000000',
    '--bg-secondary': '#0A0A0A',
    '--bg-tertiary': '#141414',
    '--bg-elevated': '#1A1A1A',
    '--bg-hover': 'rgba(255,255,255,0.08)',
    '--bg-active': 'rgba(15,82,186,0.12)',
    '--bg-overlay': 'rgba(0,0,0,0.70)',
    '--bg-glass': 'rgba(10,10,10,0.95)',
    
    '--text-primary': '#FFFFFF',
    '--text-secondary': '#B0B0B0',
    '--text-tertiary': '#808080',
    '--text-muted': '#505050',
    '--text-disabled': '#404040',
    '--text-placeholder': '#505050',
    '--text-inverse': '#000000',
    
    '--border-primary': '#2A2A2A',
    '--border-secondary': '#1A1A1A',
    '--border-focus': '#0F52BA',
    '--border-hover': '#3A3A3A',
    
    // 面板
    '--panel-bg': '#0A0A0A',
    '--panel-bg-elevated': '#141414',
    '--panel-bg-hover': '#1A1A1A',
    '--panel-bg-active': 'rgba(15,82,186,0.10)',
    
    // 图表
    '--chart-grid': '#1A1A1A',
    '--chart-text': '#606060',
    '--chart-line': '#0F52BA',
    '--chart-area': 'rgba(15,82,186,0.12)',
    '--chart-crosshair': 'rgba(255,255,255,0.15)',
    
    // 阴影
    '--shadow-sm': '0 1px 2px rgba(0,0,0,0.50)',
    '--shadow-md': '0 4px 8px rgba(0,0,0,0.60)',
    '--shadow-sm': '0 8px 16px rgba(0,0,0,0.70)',
    '--shadow-sm': '0 12px 24px rgba(0,0,0,0.80)',
    '--shadow-glow': '0 0 20px rgba(15,82,186,0.15)',
    
    // 滚动条
    '--scrollbar-track': '#0A0A0A',
    '--scrollbar-thumb': '#2A2A2A',
    '--scrollbar-thumb-hover': '#3A3A3A',
    
    // 间距（继承）
    '--space-xs': '4px',
    '--space-sm': '8px',
    '--space-md': '16px',
    '--space-lg': '24px',
    '--space-xl': '32px',
    '--space-2xl': '48px',
    
    // 圆角（继承）
    '--radius-sm': '4px',
    '--radius-md': '6px',
    '--radius-lg': '8px',
    '--radius-xl': '12px',
    '--radius-full': '9999px',
    
    // 动效（继承）
    '--duration-micro': '150ms',
    '--duration-fast': '200ms',
    '--duration-normal': '250ms',
    '--duration-slow': '300ms',
    '--easing-default': 'cubic-bezier(0.2,0,0,1)',
    '--easing-smooth': 'cubic-bezier(0.23,1,0.32,1)',
    '--easing-bounce': 'cubic-bezier(0.4,0,0.2,1)',
    
    // 层级（继承）
    '--z-base': '0',
    '--z-dropdown': '100',
    '--z-sticky': '200',
    '--z-fixed': '300',
    '--z-modal-backdrop': '400',
    '--z-modal': '500',
    '--z-popover': '600',
    '--z-tooltip': '700',
    '--z-toast': '800',
    '--z-max': '9999',
    
    // 组件尺寸（继承）
    '--btn-height': '36px',
    '--btn-height-sm': '32px',
    '--btn-height-lg': '40px',
    '--input-height': '32px',
    '--input-height-lg': '36px',
    '--table-row': '32px',
    '--table-row-sm': '24px',
    '--table-row-lg': '40px',
    '--table-header': '36px',
    '--tab-height': '36px',
    '--nav-height': '48px',
    '--sidebar-width': '220px',
    '--sidebar-collapsed': '64px',
    '--panel-width': '280px',
    '--touch-min': '44px',
    
    // 字体（继承）
    '--font-mono': '"JetBrains Mono", "Roboto Mono", "Consolas", monospace',
    '--font-sans': '"PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif',
    '--font-number': '"JetBrains Mono", "Roboto Mono", "Consolas", monospace',
    '--font-feature-tnum': '"tnum"',
    
    // 旧版兼容
    '--accent-primary': '#0F52BA',
    '--accent-secondary': '#4A8EFF',
    '--accent-bg': 'rgba(15,82,186,0.12)',
    '--accent-border': 'rgba(15,82,186,0.35)',
    '--bullish': '#FF4D4F',
    '--bullish-light': '#FF7875',
    '--bullish-bg': 'rgba(255,77,79,0.20)',
    '--bullish-border': 'rgba(255,77,79,0.40)',
    '--bearish': '#52C41A',
    '--bearish-light': '#73D13D',
    '--bearish-bg': 'rgba(82,196,26,0.20)',
    '--bearish-border': 'rgba(82,196,26,0.40)',
    '--status-live': '#0F52BA',
    '--status-warning': '#FFCC00',
    '--status-error': '#FF4444',
    '--status-info': '#44AAFF',
    '--status-success': '#44FF66',
  },
  
  // ============================================
  // 3. Wind 金融终端风格 (WIND)
  // ============================================
  [THEMES.WIND]: {
    '--color-primary': '#1890FF',
    '--color-primary-hover': '#40A9FF',
    '--color-primary-light': '#69C0FF',
    '--color-primary-dark': '#096DD9',
    '--color-primary-bg': 'rgba(24,144,255,0.10)',
    '--color-primary-border': 'rgba(24,144,255,0.30)',
    
    '--color-up': '#FF4D4F',
    '--color-up-light': '#FF7875',
    '--color-up-bg': 'rgba(255,77,79,0.15)',
    '--color-up-border': 'rgba(255,77,79,0.35)',
    '--color-down': '#52C41A',
    '--color-down-light': '#73D13D',
    '--color-down-bg': 'rgba(82,196,26,0.15)',
    '--color-down-border': 'rgba(82,196,26,0.35)',
    '--color-neutral': '#B0B8CC',
    '--color-neutral-bg': 'rgba(176,184,204,0.10)',
    '--color-neutral-border': 'rgba(176,184,204,0.25)',
    
    '--color-warning': '#FAAD14',
    '--color-warning-bg': 'rgba(250,173,20,0.15)',
    '--color-warning-border': 'rgba(250,173,20,0.30)',
    '--color-danger': '#FF4D4F',
    '--color-danger-bg': 'rgba(255,77,79,0.15)',
    '--color-danger-border': 'rgba(255,77,79,0.30)',
    '--color-success': '#52C41A',
    '--color-success-bg': 'rgba(82,196,26,0.15)',
    '--color-success-border': 'rgba(82,196,26,0.30)',
    '--color-info': '#1890FF',
    '--color-info-bg': 'rgba(24,144,255,0.15)',
    '--color-info-border': 'rgba(24,144,255,0.30)',
    
    '--bg-primary': '#1A1F2E',
    '--bg-secondary': '#232838',
    '--bg-tertiary': '#2D3447',
    '--bg-elevated': '#353D52',
    '--bg-hover': 'rgba(255,255,255,0.06)',
    '--bg-active': 'rgba(255,193,7,0.15)',
    '--bg-overlay': 'rgba(0,0,0,0.60)',
    '--bg-glass': 'rgba(35,40,56,0.95)',
    
    '--text-primary': '#E8EAED',
    '--text-secondary': '#A8ADB5',
    '--text-tertiary': '#7A8194',
    '--text-muted': '#5A6270',
    '--text-disabled': '#4A5060',
    '--text-placeholder': '#5A6270',
    '--text-inverse': '#1A1F2E',
    
    '--border-primary': '#3D4559',
    '--border-secondary': '#2A3142',
    '--border-focus': '#1890FF',
    '--border-hover': '#4D5669',
    
    '--panel-bg': '#232838',
    '--panel-bg-elevated': '#2D3447',
    '--panel-bg-hover': '#353D52',
    '--panel-bg-active': 'rgba(255,193,7,0.10)',
    
    '--chart-grid': '#2A3142',
    '--chart-text': '#7A8194',
    '--chart-line': '#FFC107',
    '--chart-area': 'rgba(255,193,7,0.12)',
    '--chart-crosshair': 'rgba(232,234,237,0.20)',
    
    '--shadow-sm': '0 1px 2px rgba(0,0,0,0.30)',
    '--shadow-md': '0 4px 8px rgba(0,0,0,0.40)',
    '--shadow-sm': '0 8px 16px rgba(0,0,0,0.50)',
    '--shadow-sm': '0 12px 24px rgba(0,0,0,0.60)',
    '--shadow-glow': '0 0 20px rgba(24,144,255,0.15)',
    
    '--scrollbar-track': '#232838',
    '--scrollbar-thumb': '#3D4559',
    '--scrollbar-thumb-hover': '#4D5669',
    
    '--space-xs': '4px',
    '--space-sm': '8px',
    '--space-md': '16px',
    '--space-lg': '24px',
    '--space-xl': '32px',
    '--space-2xl': '48px',
    
    '--radius-sm': '4px',
    '--radius-md': '6px',
    '--radius-lg': '8px',
    '--radius-xl': '12px',
    '--radius-full': '9999px',
    
    '--duration-micro': '150ms',
    '--duration-fast': '200ms',
    '--duration-normal': '250ms',
    '--duration-slow': '300ms',
    '--easing-default': 'cubic-bezier(0.2,0,0,1)',
    '--easing-smooth': 'cubic-bezier(0.23,1,0.32,1)',
    '--easing-bounce': 'cubic-bezier(0.4,0,0.2,1)',
    
    '--z-base': '0',
    '--z-dropdown': '100',
    '--z-sticky': '200',
    '--z-fixed': '300',
    '--z-modal-backdrop': '400',
    '--z-modal': '500',
    '--z-popover': '600',
    '--z-tooltip': '700',
    '--z-toast': '800',
    '--z-max': '9999',
    
    '--btn-height': '36px',
    '--btn-height-sm': '32px',
    '--btn-height-lg': '40px',
    '--input-height': '32px',
    '--input-height-lg': '36px',
    '--table-row': '32px',
    '--table-row-sm': '24px',
    '--table-row-lg': '40px',
    '--table-header': '36px',
    '--tab-height': '36px',
    '--nav-height': '48px',
    '--sidebar-width': '220px',
    '--sidebar-collapsed': '64px',
    '--panel-width': '280px',
    '--touch-min': '44px',
    
    '--font-mono': '"JetBrains Mono", "Roboto Mono", "Consolas", monospace',
    '--font-sans': '"PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif',
    '--font-number': '"JetBrains Mono", "Roboto Mono", "Consolas", monospace',
    '--font-feature-tnum': '"tnum"',
    
    '--accent-primary': '#FFC107',
    '--accent-secondary': '#FFB300',
    '--accent-bg': 'rgba(255,193,7,0.15)',
    '--accent-border': 'rgba(255,193,7,0.35)',
    '--bullish': '#FF4D4F',
    '--bullish-light': '#FF7875',
    '--bullish-bg': 'rgba(255,77,79,0.15)',
    '--bullish-border': 'rgba(255,77,79,0.35)',
    '--bearish': '#52C41A',
    '--bearish-light': '#73D13D',
    '--bearish-bg': 'rgba(82,196,26,0.15)',
    '--bearish-border': 'rgba(82,196,26,0.35)',
    '--status-live': '#FFC107',
    '--status-warning': '#FAAD14',
    '--status-error': '#FF4D4F',
    '--status-info': '#1890FF',
    '--status-success': '#52C41A',
  },
  
  // ============================================
  // 4. 专业亮色主题 (LIGHT)
  // ============================================
  [THEMES.LIGHT]: {
    '--color-primary': '#0F52BA',
    '--color-primary-hover': '#1A6AE8',
    '--color-primary-light': '#4A8EFF',
    '--color-primary-dark': '#0F52BA',
    '--color-primary-bg': 'rgba(15,82,186,0.10)',
    '--color-primary-border': 'rgba(15,82,186,0.25)',
    
    '--color-up': '#CF1322',
    '--color-up-light': '#FF4D4F',
    '--color-up-bg': 'rgba(207,19,34,0.08)',
    '--color-up-border': 'rgba(207,19,34,0.25)',
    '--color-down': '#389E0D',
    '--color-down-light': '#52C41A',
    '--color-down-bg': 'rgba(56,158,13,0.08)',
    '--color-down-border': 'rgba(56,158,13,0.25)',
    '--color-neutral': '#868E96',
    '--color-neutral-bg': 'rgba(134,142,150,0.08)',
    '--color-neutral-border': 'rgba(134,142,150,0.20)',
    
    '--color-warning': '#FF7D00',
    '--color-warning-bg': 'rgba(255,125,0,0.10)',
    '--color-warning-border': 'rgba(255,125,0,0.25)',
    '--color-danger': '#DC2626',
    '--color-danger-bg': 'rgba(220,38,38,0.10)',
    '--color-danger-border': 'rgba(220,38,38,0.25)',
    '--color-success': '#16A34A',
    '--color-success-bg': 'rgba(22,163,74,0.10)',
    '--color-success-border': 'rgba(22,163,74,0.25)',
    '--color-info': '#0F52BA',
    '--color-info-bg': 'rgba(15,82,186,0.10)',
    '--color-info-border': 'rgba(15,82,186,0.25)',
    
    '--bg-primary': '#F8F9FA',
    '--bg-secondary': '#FFFFFF',
    '--bg-tertiary': '#F0F1F3',
    '--bg-elevated': '#FFFFFF',
    '--bg-hover': 'rgba(0,0,0,0.04)',
    '--bg-active': 'rgba(15,82,186,0.08)',
    '--bg-overlay': 'rgba(0,0,0,0.40)',
    '--bg-glass': 'rgba(255,255,255,0.95)',
    
    '--text-primary': '#1A1A1A',
    '--text-secondary': '#4A4A4A',
    '--text-tertiary': '#7A7A7A',
    '--text-muted': '#A0A0A0',
    '--text-disabled': '#C0C0C0',
    '--text-placeholder': '#A0A0A0',
    '--text-inverse': '#FFFFFF',
    
    '--border-primary': '#D9D9D9',
    '--border-secondary': '#E8E8E8',
    '--border-focus': '#0F52BA',
    '--border-hover': '#BFBFBF',
    
    '--panel-bg': '#FFFFFF',
    '--panel-bg-elevated': '#FAFAFA',
    '--panel-bg-hover': '#F5F5F5',
    '--panel-bg-active': 'rgba(15,82,186,0.06)',
    
    '--chart-grid': '#E8E8E8',
    '--chart-text': '#A0A0A0',
    '--chart-line': '#0F52BA',
    '--chart-area': 'rgba(15,82,186,0.10)',
    '--chart-crosshair': 'rgba(26,26,26,0.10)',
    
    '--shadow-sm': '0 1px 2px rgba(0,0,0,0.08)',
    '--shadow-md': '0 4px 8px rgba(0,0,0,0.10)',
    '--shadow-sm': '0 8px 16px rgba(0,0,0,0.12)',
    '--shadow-sm': '0 12px 24px rgba(0,0,0,0.15)',
    '--shadow-glow': '0 0 20px rgba(15,82,186,0.10)',
    
    '--scrollbar-track': '#F0F1F3',
    '--scrollbar-thumb': '#D9D9D9',
    '--scrollbar-thumb-hover': '#BFBFBF',
    
    '--space-xs': '4px',
    '--space-sm': '8px',
    '--space-md': '16px',
    '--space-lg': '24px',
    '--space-xl': '32px',
    '--space-2xl': '48px',
    
    '--radius-sm': '4px',
    '--radius-md': '6px',
    '--radius-lg': '8px',
    '--radius-xl': '12px',
    '--radius-full': '9999px',
    
    '--duration-micro': '150ms',
    '--duration-fast': '200ms',
    '--duration-normal': '250ms',
    '--duration-slow': '300ms',
    '--easing-default': 'cubic-bezier(0.2,0,0,1)',
    '--easing-smooth': 'cubic-bezier(0.23,1,0.32,1)',
    '--easing-bounce': 'cubic-bezier(0.4,0,0.2,1)',
    
    '--z-base': '0',
    '--z-dropdown': '100',
    '--z-sticky': '200',
    '--z-fixed': '300',
    '--z-modal-backdrop': '400',
    '--z-modal': '500',
    '--z-popover': '600',
    '--z-tooltip': '700',
    '--z-toast': '800',
    '--z-max': '9999',
    
    '--btn-height': '36px',
    '--btn-height-sm': '32px',
    '--btn-height-lg': '40px',
    '--input-height': '32px',
    '--input-height-lg': '36px',
    '--table-row': '32px',
    '--table-row-sm': '24px',
    '--table-row-lg': '40px',
    '--table-header': '36px',
    '--tab-height': '36px',
    '--nav-height': '48px',
    '--sidebar-width': '220px',
    '--sidebar-collapsed': '64px',
    '--panel-width': '280px',
    '--touch-min': '44px',
    
    '--font-mono': '"JetBrains Mono", "Roboto Mono", "Consolas", monospace',
    '--font-sans': '"PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif',
    '--font-number': '"JetBrains Mono", "Roboto Mono", "Consolas", monospace',
    '--font-feature-tnum': '"tnum"',
    
    '--accent-primary': '#0F52BA',
    '--accent-secondary': '#1A6AE8',
    '--accent-bg': 'rgba(15,82,186,0.10)',
    '--accent-border': 'rgba(15,82,186,0.25)',
    '--bullish': '#CF1322',
    '--bullish-light': '#FF4D4F',
    '--bullish-bg': 'rgba(207,19,34,0.08)',
    '--bullish-border': 'rgba(207,19,34,0.25)',
    '--bearish': '#389E0D',
    '--bearish-light': '#52C41A',
    '--bearish-bg': 'rgba(56,158,13,0.08)',
    '--bearish-border': 'rgba(56,158,13,0.25)',
    '--status-live': '#0F52BA',
    '--status-warning': '#FF7D00',
    '--status-error': '#DC2626',
    '--status-info': '#0F52BA',
    '--status-success': '#16A34A',
  }
}

// ============================================
// 主题管理逻辑
// ============================================
const currentTheme = ref(THEMES.DARK)
const isInitialized = ref(false)
const themeChangeCallbacks = new Set()

/**
 * 订阅主题变化
 */
export function onThemeChange(cb) {
  themeChangeCallbacks.add(cb)
  return () => themeChangeCallbacks.delete(cb)
}

/**
 * 获取主题CSS变量
 */
function getThemeVariable(name, fallback = '') {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}

/**
 * 获取图表配色（供 ECharts / Canvas 使用）
 */
export function getChartColors() {
  const themeAttr = document.documentElement.getAttribute('data-theme') || THEMES.DARK
  const isLight = themeAttr === THEMES.LIGHT
  
  const get = (name, fallback) => getThemeVariable(name, fallback)
  
  return {
    bgPrimary: get('--bg-primary', '#121212'),
    isLight,
    textPrimary: get('--text-primary', '#F0F6FC'),
    textSecondary: get('--text-secondary', '#C9D1D9'),
    textTertiary: get('--text-tertiary', '#8B949E'),
    borderPrimary: get('--border-primary', '#30363D'),
    borderSecondary: get('--border-secondary', '#2C2C2C'),
    chartGrid: get('--chart-grid', '#1C2333'),
    chartText: get('--chart-text', '#8B949E'),
    chartLine: get('--chart-line', '#0F52BA'),
    accentPrimary: get('--color-primary', '#0F52BA'),
    bullish: get('--color-up', '#E63946'),
    bullishLight: get('--color-up-light', '#FF6B6B'),
    bearish: get('--color-down', '#1A936F'),
    bearishLight: get('--color-down-light', '#5CD899'),
    panelBg: get('--panel-bg', '#1E1E1E'),
    tooltipBg: isLight ? 'rgba(255,255,255,0.96)' : 'rgba(13,17,23,0.95)',
    tooltipBorder: get('--border-primary', '#30363D'),
    tooltipText: get('--text-primary', '#F0F6FC'),
    // 辅助色
    ma5: '#F5A623',
    ma10: '#0F52BA',
    ma20: '#A855F7',
    ma60: '#EC4899',
  }
}

/**
 * 应用主题到DOM
 */
function applyTheme(theme) {
  const root = document.documentElement
  const config = THEME_CONFIG[theme]

  if (!config) {
    logger.warn(`[Theme] 未知主题: ${theme}`)
    return
  }

  // 设置CSS变量
  Object.entries(config).forEach(([key, value]) => {
    root.style.setProperty(key, value)
  })

  // 设置data-theme属性
  root.setAttribute('data-theme', theme)

  // 更新body类名 - 添加font-feature-settings支持
  document.body.className = `theme-${theme} font-mono antialiased`
  
  // 设置数字等宽特性
  root.style.setProperty('font-feature-settings', '"tnum"')

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

  const savedTheme = localStorage.getItem('alphaterminal-theme')
  
  if (savedTheme && Object.values(THEMES).includes(savedTheme)) {
    currentTheme.value = savedTheme
  } else {
    currentTheme.value = THEMES.DARK
  }

  applyTheme(currentTheme.value)
  isInitialized.value = true
}

/**
 * 设置主题
 */
function setTheme(theme) {
  if (Object.values(THEMES).includes(theme)) {
    currentTheme.value = theme
    localStorage.setItem('alphaterminal-theme', theme)
  }
}

/**
 * 循环切换主题
 */
function cycleTheme() {
  const themeList = Object.values(THEMES)
  const currentIndex = themeList.indexOf(currentTheme.value)
  const nextIndex = (currentIndex + 1) % themeList.length
  setTheme(themeList[nextIndex])
}

// 监听标记
let watchInitialized = false

/**
 * Composable - 主题管理
 */
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

  return {
    theme: readonly(currentTheme),
    currentTheme,
    isDark: () => currentTheme.value === THEMES.DARK || currentTheme.value === THEMES.BLACK || currentTheme.value === THEMES.WIND,
    isLight: () => currentTheme.value === THEMES.LIGHT,
    isWind: () => currentTheme.value === THEMES.WIND,
    setTheme,
    cycleTheme,
    onThemeChange,
    getChartColors,
    THEMES,
    THEME_NAMES,
    THEME_ICONS,
    // Color mode exports
    colorMode: readonly(currentColorMode),
    currentColorMode,
    setColorMode,
    cycleColorMode,
    COLOR_MODES,
    COLOR_MODE_NAMES,
  }
}

// ============================================
// 颜色模式管理（CN/Intl）
// ============================================
const currentColorMode = ref('cn')
let colorModeInitialized = false

function initColorMode() {
  if (colorModeInitialized) return
  const saved = localStorage.getItem('alphaterminal-colorMode')
  if (saved && (saved === 'cn' || saved === 'intl')) {
    currentColorMode.value = saved
  } else {
    currentColorMode.value = 'cn'
  }
  applyColorMode(currentColorMode.value)
  colorModeInitialized = true
}

function applyColorMode(mode) {
  const colors = COLOR_MODES[mode] || COLOR_MODES.cn
  const root = document.documentElement
  
  root.style.setProperty('--color-up', colors.up)
  root.style.setProperty('--color-down', colors.down)
  
  root.setAttribute('data-color-mode', mode)
  logger.log(`[ColorMode] 已切换至: ${COLOR_MODE_NAMES[mode]}`)
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
