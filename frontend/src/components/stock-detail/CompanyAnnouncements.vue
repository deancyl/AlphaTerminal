<template>
  <div class="space-y-4">
    <h2 class="text-lg font-bold text-terminal-accent">公司公告</h2>
    
    <LoadingSpinner v-if="loading" text="加载公司公告..." />
    
    <ErrorDisplay v-else-if="error" :error="error" :retry="retry" />
    
    <div v-else-if="!data" class="text-center py-8 text-terminal-dim">
      请输入股票代码查看公告
    </div>
    
    <div v-else class="space-y-4">
      <!-- 公告统计 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
        <div class="flex items-center justify-between">
          <div class="text-sm text-terminal-dim">
            共 <span class="text-terminal-accent font-bold">{{ data.total }}</span> 条公告
          </div>
          <div class="text-xs text-terminal-dim">
            最近30天数据
          </div>
        </div>
      </div>
      
      <!-- 公告列表 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary">
        <div v-if="!data.announcements?.length" class="text-center py-8 text-terminal-dim">
          暂无公告数据
        </div>
        <div v-else class="divide-y divide-theme-secondary">
          <div 
            v-for="(item, idx) in data.announcements" 
            :key="idx"
            class="p-4 hover:bg-theme-hover cursor-pointer transition"
            @click="openAnnouncement(item.url)"
          >
            <div class="flex items-start justify-between gap-4">
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-1">
                  <span 
                    class="px-2 py-0.5 rounded text-xs"
                    :class="getAnnouncementTypeClass(item.type)"
                  >
                    {{ item.type || '公告' }}
                  </span>
                  <span class="text-xs text-terminal-dim">{{ item.date }}</span>
                </div>
                <div class="text-sm text-terminal-primary truncate">
                  {{ item.title || '无标题' }}
                </div>
              </div>
              <div class="flex-shrink-0">
                <svg class="w-4 h-4 text-terminal-dim" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 分页 -->
      <div v-if="data.total > pageSize" class="flex items-center justify-center gap-2">
        <button
          class="px-3 py-1.5 rounded text-sm transition"
          :class="currentPage <= 1 ? 'text-terminal-dim cursor-not-allowed' : 'text-terminal-primary hover:bg-theme-hover'"
          :disabled="currentPage <= 1"
          @click="changePage(currentPage - 1)"
        >
          上一页
        </button>
        <span class="text-sm text-terminal-dim">
          第 {{ currentPage }} / {{ totalPages }} 页
        </span>
        <button
          class="px-3 py-1.5 rounded text-sm transition"
          :class="currentPage >= totalPages ? 'text-terminal-dim cursor-not-allowed' : 'text-terminal-primary hover:bg-theme-hover'"
          :disabled="currentPage >= totalPages"
          @click="changePage(currentPage + 1)"
        >
          下一页
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useStockDetail } from '../../composables/useStockDetail'
import LoadingSpinner from '../f9/LoadingSpinner.vue'
import ErrorDisplay from '../f9/ErrorDisplay.vue'

const props = defineProps({
  data: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  retry: { type: Function, default: null },
  currentPage: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20 }
})

const emit = defineEmits(['page-change'])

const { getAnnouncementTypeClass } = useStockDetail()

const totalPages = computed(() => {
  if (!props.data?.total) return 1
  return Math.ceil(props.data.total / props.pageSize)
})

function openAnnouncement(url) {
  if (url && url !== '--' && url !== 'nan') {
    window.open(url, '_blank')
  }
}

function changePage(page) {
  emit('page-change', page)
}
</script>
