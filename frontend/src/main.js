import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './style.css'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'
import { RecycleScroller, DynamicScroller } from 'vue-virtual-scroller'
import { initWebVitals } from './utils/webVitals'

const app = createApp(App)
app.use(createPinia())
app.component('RecycleScroller', RecycleScroller)
app.component('DynamicScroller', DynamicScroller)

// Initialize Web Vitals monitoring (only in production or when analytics enabled)
if (import.meta.env.PROD || localStorage.getItem('enable-web-vitals') === 'true') {
  initWebVitals(true)
} else {
  // Development mode: collect but don't send analytics
  initWebVitals(false)
}

app.mount('#app')
