import { ref, onUnmounted, onDeactivated } from 'vue'

export function useAbortableRequest(options = {}) {
  const { abortOnDeactivate = true } = options
  const controller = ref(null)
  const pending = ref(false)

  function createSignal() {
    if (controller.value) {
      controller.value.abort('New request started')
    }
    controller.value = new AbortController()
    pending.value = true
    return controller.value.signal
  }

  function complete() {
    controller.value = null
    pending.value = false
  }

  function abort(reason = 'Request aborted') {
    if (controller.value) {
      controller.value.abort(reason)
      controller.value = null
      pending.value = false
    }
  }

  onUnmounted(() => {
    abort('Component unmounted')
  })

  // Handle KeepAlive deactivation
  if (abortOnDeactivate) {
    onDeactivated(() => {
      abort('Component deactivated (KeepAlive)')
    })
  }

  return {
    createSignal,
    complete,
    abort,
    pending
  }
}
