import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import compression from 'vite-plugin-compression'
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
  resolve: {
    alias: {
      '@': resolve(__dirname, './src'),
    },
  },
  plugins: [
    vue(),
    versionJsonPlugin(),
    // v0.6.61: Compression plugin for gzip
    compression({
      algorithm: 'gzip',
      threshold: 10240,  // Only compress files > 10KB
      deleteOriginFile: false,  // Keep original files
    }),
    // v0.6.61: Brotli compression for better compression ratio
    compression({
      algorithm: 'brotliCompress',
      threshold: 10240,
      deleteOriginFile: false,
    })
  ],
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
    // v0.6.68: 审计报告任务 5 - 异步样式防闪烁
    cssCodeSplit: true,
    rollupOptions: {
      output: {
        // v0.6.61: Refactored manualChunks to 4 vendor groups
        manualChunks(id) {
          if (id.includes('node_modules')) {
            // Group 1: vendor-core - Core Vue ecosystem
            if (id.includes('vue') || id.includes('pinia') || id.includes('@vueuse')) {
              return 'vendor-core'
            }
            
            // Group 2: vendor-charts - Charting libraries
            if (id.includes('echarts') || id.includes('lightweight-charts')) {
              return 'vendor-charts'
            }
            
            // Group 3: vendor-utils - Utility libraries
            if (id.includes('axios') || id.includes('dayjs') || id.includes('lodash') || id.includes('gridstack')) {
              return 'vendor-utils'
            }
            
            // Group 4: vendor-webllm - Heavy WebLLM library (separate for lazy loading)
            if (id.includes('@mlc-ai/web-llm')) {
              return 'vendor-webllm'
            }
            
            // Group 5: vendor-misc - Other libraries
            if (id.includes('html2canvas')) {
              return 'vendor-misc'
            }
            
            // Default: vendor-misc
            return 'vendor-misc'
          }
          
          // Admin panel - separate chunk for admin routes
          if (id.includes('/components/admin/')) {
            return 'admin-panel'
          }
        },
      },
    },
    chunkSizeWarningLimit: 1000,
    target: 'esnext',
  },
})
