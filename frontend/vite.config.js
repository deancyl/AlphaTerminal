import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const pkg = JSON.parse(readFileSync(resolve(__dirname, 'package.json'), 'utf-8'))

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 60100,
    allowedHosts: ['finance.deancylnextcloud.eu.org'],
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8002',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8002',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8002',
        ws: true,           // 启用 WebSocket 代理
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: '0.0.0.0',
    port: 60100,
    allowedHosts: ['finance.deancylnextcloud.eu.org'],
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8002',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8002',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8002',
        ws: true,
        changeOrigin: true,
      },
    },
  },
  optimizeDeps: {
    include: ['gridstack', 'echarts'],
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('@mlc-ai/web-llm')) return 'vendor-webllm'
            if (id.includes('vue'))             return 'vendor-vue'
            if (id.includes('gridstack'))       return 'vendor-gridstack'
            if (id.includes('echarts'))         return 'vendor-echarts'
            if (id.includes('lightweight-charts')) return 'vendor-lwcharts'
            if (id.includes('html2canvas'))     return 'vendor-html2canvas'
            return 'vendor'
          }
        },
      },
    },
    chunkSizeWarningLimit: 1000,
  },
})
