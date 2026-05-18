<template>
  <aside
    class="flex-shrink-0 flex flex-col h-full overflow-hidden transition-all duration-300 ease-in-out group"
    :class="isCollapsed ? 'w-14' : 'w-56'"
    @mouseenter="isCollapsed = false"
    @mouseleave="isCollapsed = true"
    role="navigation"
    aria-label="主导航菜单"
  >
    <div class="flex flex-col h-full bg-terminal-card border-r border-terminal-border">
      <!-- Logo -->
      <div class="flex items-center h-12 px-3 border-b border-terminal-border shrink-0">
        <span class="text-agent-blue font-bold text-sm whitespace-nowrap overflow-hidden transition-opacity duration-200"
              :class="isCollapsed ? 'opacity-0 w-0' : 'opacity-100'">
          AlphaTerminal
        </span>
        <span v-if="isCollapsed" class="text-agent-blue font-bold text-lg">A</span>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 overflow-y-auto overflow-x-hidden py-2" aria-label="市场行情">
        <!-- Market Section -->
        <div class="px-3 py-1.5 text-[10px] text-gray-500 uppercase tracking-wider whitespace-nowrap overflow-hidden transition-opacity duration-200"
             :class="isCollapsed ? 'opacity-0 h-0 py-0' : 'opacity-100'">
          市场行情
        </div>

        <button
          v-for="item in mainNavItems"
          :key="item.id"
          class="w-full flex items-center gap-3 px-3 py-2.5 transition-all duration-200 relative mx-1 my-0.5 rounded-sm"
          :class="[
            activeId === item.id
              ? 'text-white border-l-2 border-agent-blue bg-agent-blue/5'
              : 'text-gray-400 hover:text-gray-200 hover:bg-white/5 border-l-2 border-transparent'
          ]"
          @click="handleClick(item)"
          :aria-current="activeId === item.id ? 'page' : undefined"
          :aria-label="item.label"
          :title="isCollapsed ? item.label : undefined"
          type="button"
        >
          <span class="text-base shrink-0 w-5 text-center" aria-hidden="true">{{ item.icon }}</span>
          <span class="whitespace-nowrap text-xs overflow-hidden transition-all duration-200"
                :class="isCollapsed ? 'opacity-0 w-0' : 'opacity-100'">
            {{ item.label }}
          </span>
        </button>

        <!-- AI Tools Section -->
        <div class="px-3 py-1.5 text-[10px] text-gray-500 uppercase tracking-wider mt-4 whitespace-nowrap overflow-hidden transition-opacity duration-200"
             :class="isCollapsed ? 'opacity-0 h-0 py-0' : 'opacity-100'">
          AI & Agent
        </div>

        <button
          v-for="item in aiNavItems"
          :key="item.id"
          class="w-full flex items-center gap-3 px-3 py-2.5 transition-all duration-200 relative mx-1 my-0.5 rounded-sm"
          :class="[
            activeId === item.id
              ? 'text-white border-l-2 border-agent-blue bg-agent-blue/5'
              : 'text-gray-400 hover:text-gray-200 hover:bg-white/5 border-l-2 border-transparent'
          ]"
          @click="handleClick(item)"
          :aria-current="activeId === item.id ? 'page' : undefined"
          :aria-label="item.label"
          :title="isCollapsed ? item.label : undefined"
          type="button"
        >
          <span class="text-base shrink-0 w-5 text-center" aria-hidden="true">{{ item.icon }}</span>
          <span class="whitespace-nowrap text-xs overflow-hidden transition-all duration-200"
                :class="isCollapsed ? 'opacity-0 w-0' : 'opacity-100'">
            {{ item.label }}
          </span>
        </button>
      </nav>

      <!-- Theme Switcher -->
      <div class="px-2 py-2 border-t border-terminal-border shrink-0 overflow-hidden">
        <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2 px-1 whitespace-nowrap transition-opacity duration-200"
             :class="isCollapsed ? 'opacity-0 h-0 mb-0' : 'opacity-100'">
          主题
        </div>
        <div class="flex gap-1 justify-center">
          <button
            v-for="t in themeList"
            :key="t.key"
            class="flex items-center justify-center w-8 h-8 rounded-sm transition-all duration-200"
            :class="currentTheme === t.key
              ? 'bg-agent-blue/20 text-agent-blue border border-agent-blue/50'
              : 'bg-transparent text-gray-500 border border-transparent hover:bg-white/5 hover:text-gray-300'"
            @click="setTheme(t.key)"
            :aria-label="t.name"
            :aria-pressed="currentTheme === t.key"
            :title="t.name"
            type="button"
          >
            <span class="text-sm" aria-hidden="true">{{ t.icon }}</span>
          </button>
        </div>
      </div>

      <!-- Admin -->
      <div class="border-t border-terminal-border shrink-0 px-1 py-2">
        <button
          v-for="item in adminNavItems"
          :key="item.id"
          class="w-full flex items-center gap-3 px-2 py-2 transition-all duration-200 rounded-sm"
          :class="[
            activeId === item.id
              ? 'text-red-400 border-l-2 border-red-400 bg-red-400/5'
              : 'text-gray-500 hover:text-gray-300 hover:bg-white/5 border-l-2 border-transparent'
          ]"
          @click="handleClick(item)"
          :aria-current="activeId === item.id ? 'page' : undefined"
          :aria-label="item.label"
          :title="isCollapsed ? item.label : undefined"
          type="button"
        >
          <span class="text-base shrink-0 w-5 text-center" aria-hidden="true">{{ item.icon }}</span>
          <span class="whitespace-nowrap text-xs overflow-hidden transition-all duration-200"
                :class="isCollapsed ? 'opacity-0 w-0' : 'opacity-100'">
            {{ item.label }}
          </span>
        </button>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref } from 'vue'
import { useTheme, THEMES, THEME_NAMES, THEME_ICONS } from '../composables/useTheme.js'

const props = defineProps({
  isOpen:   { type: Boolean, default: false },
  activeId: { type: String,  default: 'stock' },
})
const emit = defineEmits(['navigate', 'close'])

const { theme: currentTheme, setTheme } = useTheme()

const isCollapsed = ref(true)

const mainNavItems = [
  { id: 'stock',     label: '股票行情',   icon: '📊' },
  { id: 'portfolio', label: '投资组合',   icon: '💰' },
  { id: 'fund',      label: '基金分析',   icon: '📈' },
  { id: 'bond',      label: '债券行情',   icon: '📉' },
  { id: 'futures',   label: '期货行情',   icon: '🛢️' },
  { id: 'forex',     label: '外汇行情',   icon: '💱' },
  { id: 'macro',     label: '宏观经济',   icon: '🌍' },
  { id: 'options',   label: '期权分析',   icon: '⚡' },
  { id: 'global-index', label: '全球指数',  icon: '🌐' },
  { id: 'research',  label: '研报平台',   icon: '📄' },
]

const aiNavItems = [
  { id: 'strategy-center', label: '策略中心', icon: '🎯' },
  { id: 'walk-forward', label: '滚动前向分析', icon: '📊' },
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
