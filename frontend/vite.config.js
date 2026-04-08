import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
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
  optimizeDeps: {
    include: ['gridstack'],
    exclude: ['echarts'],   // 通过 CDN 加载，不打入 bundle
  },
  build: {
    rollupOptions: {
      external: ['echarts'], // CDN 加载，标记为 external
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('vue'))       return 'vendor-vue'
            if (id.includes('gridstack')) return 'vendor-gridstack'
          }
        },
      },
    },
    chunkSizeWarningLimit: 600,
  },
})
