import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { readFileSync, writeFileSync, existsSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'
import { execSync } from 'child_process'

const __dirname = dirname(fileURLToPath(import.meta.url))
const pkg = JSON.parse(readFileSync(resolve(__dirname, 'package.json'), 'utf-8'))
const buildTime = new Date().toISOString()
const commitHash = execSync('git rev-parse --short HEAD 2>/dev/null || echo "unknown"').toString().trim()

const backendHost = process.env.VITE_BACKEND_HOST || '127.0.0.1'
const backendPort = process.env.VITE_BACKEND_PORT || '8002'
const backendUrl = `http://${backendHost}:${backendPort}`
const backendWsUrl = `ws://${backendHost}:${backendPort}`

// Allowed hosts for dev server - comma-separated env var or fallback to specific domains
const allowedHostsEnv = process.env.VITE_ALLOWED_HOSTS || ''
const allowedHosts = allowedHostsEnv
  ? allowedHostsEnv.split(',').map(h => h.trim())
  : ['finance.deancylnextcloud.eu.org']

function versionJsonPlugin() {
  return {
    name: 'version-json',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (req.url === '/version.json') {
          res.setHeader('Content-Type', 'application/json')
          res.setHeader('Cache-Control', 'no-store')
          res.end(JSON.stringify({ version: pkg.version, commit: commitHash, buildTime }, null, 2))
          return
        }
        next()
      })
    },
    configurePreviewServer(server) {
      server.middlewares.use((req, res, next) => {
        if (req.url === '/version.json') {
          const versionPath = resolve(__dirname, 'dist/version.json')
          if (existsSync(versionPath)) {
            res.setHeader('Content-Type', 'application/json')
            res.setHeader('Cache-Control', 'no-store')
            res.end(readFileSync(versionPath, 'utf-8'))
            return
          }
        }
        next()
      })
    },
    closeBundle() {
      writeFileSync(
        resolve(__dirname, 'dist/version.json'),
        JSON.stringify({ version: pkg.version, commit: commitHash, buildTime }, null, 2)
      )
    }
  }
}

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  plugins: [vue(), versionJsonPlugin()],
  server: {
    host: '0.0.0.0',
    port: 60100,
    strictPort: true,
    allowedHosts,
    proxy: {
      '/api': {
        target: backendUrl,
        changeOrigin: true,
      },
      '/health': {
        target: backendUrl,
        changeOrigin: true,
      },
      '/ws': {
        target: backendWsUrl,
        ws: true,
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: '0.0.0.0',
    port: 60100,
    strictPort: true,
    allowedHosts,
    headers: {
      'Cache-Control': 'no-store, no-cache, must-revalidate, proxy-revalidate',
      'Pragma': 'no-cache',
      'Expires': '0',
    },
    proxy: {
      '/api': {
        target: backendUrl,
        changeOrigin: true,
      },
      '/health': {
        target: backendUrl,
        changeOrigin: true,
      },
      '/ws': {
        target: backendWsUrl,
        ws: true,
        changeOrigin: true,
      },
    },
  },
  optimizeDeps: {
    include: ['gridstack'],
    exclude: ['echarts'],
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('@mlc-ai/web-llm')) return 'vendor-webllm'
            if (id.includes('vue'))             return 'vendor-vue'
            if (id.includes('gridstack'))        return 'vendor-gridstack'
            if (id.includes('echarts'))          return 'vendor-echarts'
            if (id.includes('lightweight-charts')) return 'vendor-lwcharts'
            if (id.includes('html2canvas'))      return 'vendor-html2canvas'
            if (id.includes('@vueuse'))           return 'vendor-vueuse'
            if (id.includes('pinia'))             return 'vendor-pinia'
            if (id.includes('axios'))            return 'vendor-axios'
            if (id.includes('dayjs'))             return 'vendor-dayjs'
            if (id.includes('lodash'))            return 'vendor-lodash'
            return 'vendor'
          }
        },
      },
    },
    chunkSizeWarningLimit: 1000,
    target: 'esnext',
  },
})
