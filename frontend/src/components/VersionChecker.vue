<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const showUpdate = ref(false)
const newVersion = ref('')
const isTabVisible = ref(true)
let intervalId = null
let pendingUpdate = false

async function checkVersion() {
  if (!isTabVisible.value) return
  
  try {
    const response = await fetch('/version.json', { cache: 'no-store' })
    const data = await response.json()
    
    if (data.version !== __APP_VERSION__) {
      if (!isTabVisible.value) {
        pendingUpdate = true
      } else {
        showUpdate.value = true
        newVersion.value = data.version
      }
    }
  } catch (e) {
    // Silently fail - version.json might not exist in dev
  }
}

function handleVisibilityChange() {
  isTabVisible.value = !document.hidden
  
  if (isTabVisible.value && pendingUpdate) {
    window.location.reload()
  }
}

function reload() {
  window.location.reload()
}

function dismiss() {
  showUpdate.value = false
}

onMounted(() => {
  checkVersion()
  intervalId = setInterval(checkVersion, 60000)
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onUnmounted(() => {
  if (intervalId) clearInterval(intervalId)
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})
</script>

<template>
  <Transition name="slide-down">
    <div v-if="showUpdate" class="version-update-banner">
      <span class="update-text">
        <span class="update-icon">🔄</span>
        发现新版本 <span class="version-number">v{{ newVersion }}</span>
      </span>
      <div class="update-actions">
        <button @click="reload" class="btn-update">立即更新</button>
        <button @click="dismiss" class="btn-dismiss">稍后</button>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.version-update-banner {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 0.75rem 1rem;
  background: linear-gradient(135deg, #1e3a5f 0%, #0f52ba 100%);
  color: #fff;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
}

.update-text {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
}

.update-icon {
  font-size: 1rem;
}

.version-number {
  font-weight: 600;
  background: rgba(255, 255, 255, 0.2);
  padding: 0.125rem 0.5rem;
  border-radius: 0.25rem;
}

.update-actions {
  display: flex;
  gap: 0.5rem;
}

.btn-update {
  padding: 0.375rem 0.75rem;
  font-size: 0.75rem;
  font-weight: 500;
  color: #0f52ba;
  background: #fff;
  border: none;
  border-radius: 0.25rem;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-update:hover {
  background: #f0f0f0;
  transform: translateY(-1px);
}

.btn-dismiss {
  padding: 0.375rem 0.75rem;
  font-size: 0.75rem;
  font-weight: 500;
  color: #fff;
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 0.25rem;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-dismiss:hover {
  background: rgba(255, 255, 255, 0.3);
}

.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.3s ease;
}

.slide-down-enter-from,
.slide-down-leave-to {
  transform: translateY(-100%);
  opacity: 0;
}

@media (max-width: 640px) {
  .version-update-banner {
    flex-direction: column;
    padding: 0.5rem;
    gap: 0.5rem;
  }
  
  .update-text {
    font-size: 0.75rem;
  }
  
  .btn-update,
  .btn-dismiss {
    padding: 0.5rem 1rem;
    min-height: 44px;
  }
}
</style>
