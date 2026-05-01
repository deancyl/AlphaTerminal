<template>
  <aside
    class="flex-shrink-0 flex flex-col bg-terminal-panel border-r border-theme-secondary transition-all duration-300 ease-in-out overflow-hidden h-full"
    :class="isMobile ? '' : (isCollapsed ? 'items-center' : '')"
    :style="isMobile ? { width: '220px' } : { width: isCollapsed ? '64px' : '220px' }"
  >
    <!-- 顶部：Logo + 切换按钮 -->
    <div
      class="flex items-center h-12 border-b border-theme-secondary shrink-0 w-full"
      :class="isMobile || !isCollapsed ? 'justify-between px-4' : 'justify-center px-2'"
    >
      <span v-if="isMobile || !isCollapsed" class="text-theme-primary font-bold text-sm whitespace-nowrap">AlphaTerminal</span>
      <button
        class="flex items-center justify-center rounded-sm text-theme-tertiary hover:text-terminal-accent hover:bg-theme-hover transition-colors"
        :class="isMobile ? 'w-12 h-12' : 'w-11 h-11'"
        @click="$emit('toggle')"
        :title="isMobile ? '关闭' : (isCollapsed ? '展开' : '折叠')"
      >
        <span class="text-sm">{{ isCollapsed && !isMobile ? '☰' : '◀' }}</span>
      </button>
    </div>

    <!-- 导航列表 -->
    <nav class="flex-1 overflow-y-auto py-2 w-full">
      <!-- 分类标题 -->
      <div v-if="isMobile || !isCollapsed" class="px-3 py-1.5 text-[10px] text-theme-tertiary uppercase tracking-wider">📂 市场行情</div>

      <!-- 主导航项 -->
      <button
        v-for="item in mainNavItems"
        :key="item.id"
        class="w-full flex items-center transition-all duration-200 relative group mx-2 my-0.5 rounded-sm"
        :class="[
          isCollapsed && !isMobile ? 'justify-center px-0 py-3' : 'gap-2.5 px-3 py-2.5',
          activeId === item.id
            ? 'bg-theme-hover text-theme-primary border-r-2 border-theme-secondary'
            : 'text-theme-secondary hover:bg-theme-hover hover:text-theme-primary border-r-transparent'
        ]"
        @click="handleClick(item)"
      >
        <span :class="isCollapsed && !isMobile ? 'text-lg' : 'text-base'">{{ item.icon }}</span>
        <span v-if="isMobile || !isCollapsed" class="whitespace-nowrap text-xs">{{ item.label }}</span>
        <!-- 折叠态 tooltip -->
        <span
          v-if="!isMobile && isCollapsed"
          class="absolute left-full ml-2 px-2 py-1 rounded-sm bg-terminal-panel border border-theme-secondary text-xs text-theme-primary whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-sm"
        >
          {{ item.label }}
        </span>
      </button>
    </nav>

    <!-- 主题切换区域（仅展开时显示） -->
    <div v-if="isMobile || !isCollapsed" class="px-3 py-3 border-t border-theme shrink-0 w-full">
      <div class="text-[10px] text-theme-tertiary uppercase tracking-wider mb-2">🎨 主题切换</div>
      <div class="grid grid-cols-4 gap-1">
        <button
          v-for="t in themeList"
          :key="t.key"
          class="flex flex-col items-center justify-center py-2 px-1 rounded-sm text-[10px] transition-all duration-200"
          :class="currentTheme === t.key
            ? 'bg-theme-accent/20 text-theme-accent border border-theme-accent/50'
            : 'bg-theme-secondary/50 text-theme-secondary border border-transparent hover:bg-theme-hover hover:text-theme-primary'"
          @click="setTheme(t.key)"
          :title="t.name"
        >
          <span class="text-base mb-0.5">{{ t.icon }}</span>
          <span class="scale-90">{{ t.shortName }}</span>
        </button>
      </div>
    </div>

    <!-- 系统管理 -->
    <div
      class="border-t border-theme shrink-0 w-full"
      :class="isCollapsed && !isMobile ? 'py-1 flex flex-col items-center' : 'px-3 py-2'"
    >
      <button
        v-for="item in adminNavItems"
        :key="item.id"
        class="w-full flex items-center transition-colors border-r-2 rounded-sm relative group"
        :class="[
          isCollapsed && !isMobile ? 'justify-center px-0 py-3' : 'gap-2.5 px-3 py-2',
          activeId === item.id
            ? 'bg-[var(--color-danger-bg)] text-[var(--color-danger)] border-r-2 border-[var(--color-danger)]'
            : 'text-theme-secondary hover:bg-[var(--color-danger-bg)] hover:text-[var(--color-danger)] border-r-transparent'
        ]"
        @click="handleClick(item)"
      >
        <span :class="isCollapsed && !isMobile ? 'text-lg' : 'text-base'">{{ item.icon }}</span>
        <span v-if="isMobile || !isCollapsed" class="whitespace-nowrap text-xs">{{ item.label }}</span>
        <!-- 折叠态 tooltip -->
        <span
          v-if="!isMobile && isCollapsed"
          class="absolute left-full ml-2 px-2 py-1 rounded-sm bg-terminal-panel border border-theme-secondary text-xs text-theme-primary whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-sm"
        >
          {{ item.label }}
        </span>
      </button>
    </div>
  </aside>
</template>

<script setup>
import { useTheme, THEMES, THEME_NAMES, THEME_ICONS } from '../composables/useTheme.js'

const props = defineProps({
  isMobile:   { type: Boolean, default: false },
  isCollapsed:{ type: Boolean, default: true },
  activeId:   { type: String,  default: 'stock' },
})
const emit = defineEmits(['navigate', 'toggle'])

const { theme: currentTheme, setTheme } = useTheme()

const mainNavItems = [
  { id: 'stock',     label: '股票行情',   icon: '📊' },
  { id: 'portfolio', label: '投资组合',   icon: '💰' },
  { id: 'fund',      label: '基金分析',   icon: '📈' },
  { id: 'bond',      label: '债券行情',   icon: '📉' },
  { id: 'futures',   label: '期货行情',   icon: '🛢️' },
  { id: 'macro',     label: '宏观经济',   icon: '🌍' },
  { id: 'options',   label: '期权分析',   icon: '⚡' },
  { id: 'global-index', label: '全球指数',  icon: '🌐' },
  { id: 'backtest',  label: '回测实验室', icon: '🔬' },
]

const adminNavItems = [
  { id: 'admin',     label: '系统管理',   icon: '⚙️' },
]

const themeList = [
  { key: THEMES.DARK,  name: THEME_NAMES[THEMES.DARK],  shortName: '深色', icon: THEME_ICONS[THEMES.DARK] },
  { key: THEMES.BLACK, name: THEME_NAMES[THEMES.BLACK], shortName: '全黑', icon: THEME_ICONS[THEMES.BLACK] },
  { key: THEMES.WIND,  name: THEME_NAMES[THEMES.WIND],  shortName: 'Wind', icon: THEME_ICONS[THEMES.WIND] },
  { key: THEMES.LIGHT, name: THEME_NAMES[THEMES.LIGHT], shortName: '亮色', icon: THEME_ICONS[THEMES.LIGHT] },
]

function handleClick(item) {
  emit('navigate', item.id)
}
</script>
