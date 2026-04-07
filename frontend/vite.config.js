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
    },
  },
  optimizeDeps: {
    include: ['gridstack'],
  },
})
