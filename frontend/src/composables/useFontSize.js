import { ref, watch, onMounted } from 'vue'

const FONT_SIZE_KEY = 'font-size'
const FONT_SIZE_OPTIONS = [
  { value: 'small', label: '小', size: '13px', desc: '紧凑显示，适合小屏幕' },
  { value: 'normal', label: '标准', size: '14px', desc: '默认大小，平衡显示' },
  { value: 'medium', label: '中', size: '15px', desc: '稍大字体，更易阅读' },
  { value: 'large', label: '大', size: '16px', desc: '大字体，适合视力较弱用户' },
  { value: 'xlarge', label: '特大', size: '18px', desc: '最大字体，最佳可读性' }
]

const DEFAULT_FONT_SIZE = 'normal'

const currentFontSize = ref(DEFAULT_FONT_SIZE)
const isInitialized = ref(false)

function applyFontSize(sizeValue) {
  const option = FONT_SIZE_OPTIONS.find(o => o.value === sizeValue)
  if (!option) return
  
  const root = document.documentElement
  root.style.setProperty('--font-size-base', option.size)
  
  const scaleFactors = {
    'small': { xs: '11px', sm: '12px', md: '13px', lg: '15px', xl: '17px' },
    'normal': { xs: '12px', sm: '13px', md: '14px', lg: '16px', xl: '18px' },
    'medium': { xs: '12px', sm: '14px', md: '15px', lg: '17px', xl: '19px' },
    'large': { xs: '13px', sm: '15px', md: '16px', lg: '18px', xl: '20px' },
    'xlarge': { xs: '14px', sm: '16px', md: '18px', lg: '20px', xl: '22px' }
  }
  
  const factors = scaleFactors[sizeValue] || scaleFactors['normal']
  root.style.setProperty('--font-size-xs', factors.xs)
  root.style.setProperty('--font-size-sm', factors.sm)
  root.style.setProperty('--font-size-md', factors.md)
  root.style.setProperty('--font-size-lg', factors.lg)
  root.style.setProperty('--font-size-xl', factors.xl)
}

function setFontSize(sizeValue) {
  if (!FONT_SIZE_OPTIONS.find(o => o.value === sizeValue)) {
    sizeValue = DEFAULT_FONT_SIZE
  }
  currentFontSize.value = sizeValue
  localStorage.setItem(FONT_SIZE_KEY, sizeValue)
  applyFontSize(sizeValue)
}

function initFontSize() {
  if (isInitialized.value) return
  
  const saved = localStorage.getItem(FONT_SIZE_KEY)
  const initialSize = saved && FONT_SIZE_OPTIONS.find(o => o.value === saved) 
    ? saved 
    : DEFAULT_FONT_SIZE
  
  currentFontSize.value = initialSize
  applyFontSize(initialSize)
  isInitialized.value = true
}

function cycleFontSize() {
  const currentIndex = FONT_SIZE_OPTIONS.findIndex(o => o.value === currentFontSize.value)
  const nextIndex = (currentIndex + 1) % FONT_SIZE_OPTIONS.length
  setFontSize(FONT_SIZE_OPTIONS[nextIndex].value)
}

function getFontSizeInfo() {
  const option = FONT_SIZE_OPTIONS.find(o => o.value === currentFontSize.value)
  return {
    value: currentFontSize.value,
    label: option?.label || '标准',
    size: option?.size || '14px',
    desc: option?.desc || ''
  }
}

export function useFontSize() {
  onMounted(() => {
    initFontSize()
  })
  
  watch(currentFontSize, (newSize) => {
    if (isInitialized.value) {
      applyFontSize(newSize)
    }
  })
  
  return {
    currentFontSize,
    fontSizeOptions: FONT_SIZE_OPTIONS,
    setFontSize,
    cycleFontSize,
    getFontSizeInfo,
    initFontSize
  }
}