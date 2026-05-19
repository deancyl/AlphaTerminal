import { ref, computed, onMounted } from 'vue'

const TOUR_STORAGE_KEY = 'alphaterminal_tour_completed'

export function useTour(tourId) {
  const currentStep = ref(0)
  const isActive = ref(false)
  const steps = ref([])
  
  const storageKey = `${TOUR_STORAGE_KEY}_${tourId}`
  
  const isCompleted = computed(() => {
    if (typeof window === 'undefined') return false
    return localStorage.getItem(storageKey) === 'true'
  })
  
  const progress = computed(() => {
    if (steps.value.length === 0) return 0
    return Math.round((currentStep.value / steps.value.length) * 100)
  })
  
  function startTour(tourSteps) {
    if (isCompleted.value) return
    steps.value = tourSteps || []
    currentStep.value = 0
    isActive.value = true
  }
  
  function nextStep() {
    if (currentStep.value < steps.value.length - 1) {
      currentStep.value++
    } else {
      endTour()
    }
  }
  
  function prevStep() {
    if (currentStep.value > 0) {
      currentStep.value--
    }
  }
  
  function skipTour() {
    endTour()
  }
  
  function endTour() {
    isActive.value = false
    currentStep.value = 0
    if (typeof window !== 'undefined') {
      localStorage.setItem(storageKey, 'true')
    }
  }
  
  function resetTour() {
    if (typeof window !== 'undefined') {
      localStorage.removeItem(storageKey)
    }
  }
  
  function goToStep(stepIndex) {
    if (stepIndex >= 0 && stepIndex < steps.value.length) {
      currentStep.value = stepIndex
    }
  }
  
  return {
    currentStep,
    isActive,
    steps,
    isCompleted,
    progress,
    startTour,
    nextStep,
    prevStep,
    skipTour,
    endTour,
    resetTour,
    goToStep,
  }
}

export const RESEARCH_TOUR_STEPS = [
  {
    target: '[data-tour="symbol-input"]',
    title: '输入股票代码',
    content: '在这里输入股票代码（如 600519）来查询该股票的研报。',
    placement: 'bottom',
  },
  {
    target: '[data-tour="category-filter"]',
    title: '分类筛选',
    content: '可以按分类筛选研报：宏观经济、行业研究、个股分析、固定收益。',
    placement: 'bottom',
  },
  {
    target: '[data-tour="report-list"]',
    title: '研报列表',
    content: '点击研报标题可以查看详情，支持关键词搜索和机构筛选。',
    placement: 'top',
  },
  {
    target: '[data-tour="summarize-btn"]',
    title: 'AI智能总结',
    content: '点击"一键总结"按钮，AI会自动提炼研报的核心观点。',
    placement: 'left',
  },
]

export const MAIN_TOUR_STEPS = [
  {
    target: '[data-tour="sidebar"]',
    title: '功能导航',
    content: '左侧是主要功能导航，包含行情、宏观、期货、债券等模块。',
    placement: 'right',
  },
  {
    target: '[data-tour="search"]',
    title: '快速搜索',
    content: '使用 Ctrl+K 打开命令面板，快速搜索股票或执行命令。',
    placement: 'bottom',
  },
  {
    target: '[data-tour="theme-toggle"]',
    title: '主题切换',
    content: '点击右上角可以切换深色/浅色主题。',
    placement: 'left',
  },
]
