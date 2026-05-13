import { ref, onUnmounted } from 'vue'

export function useAbortableRequest() {
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

  return {
    createSignal,
    complete,
    abort,
    pending
  }
}
