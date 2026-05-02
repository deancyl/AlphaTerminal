# AlphaTerminal Debug工作流 v3.0
## 管理面板联动设计方案

---

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                    前端管理面板 (Vue 3)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  健康仪表盘   │  │  Debug控制台 │  │  报告中心    │      │
│  │  Dashboard   │  │  Console     │  │  Reports     │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
└─────────┼─────────────────┼─────────────────┼──────────────┘
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │ HTTP / WebSocket
┌───────────────────────────┼──────────────────────────────┐
│                           ▼                              │
│              ┌──────────────────────────┐                │
│              │   Debug API Router       │                │
│              │   /api/v1/debug/*        │                │
│              └──────────┬───────────────┘                │
│                         │                                │
│      ┌──────────────────┼──────────────────┐            │
│      │                  │                  │            │
│      ▼                  ▼                  ▼            │
│ ┌──────────┐    ┌──────────┐     ┌──────────────┐     │
│ │ Debug工具 │    │ 执行引擎  │     │ 报告存储      │     │
│ │ Scripts  │    │ Executor │     │ /tmp/reports │     │
│ └──────────┘    └──────────┘     └──────────────┘     │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## 前端管理面板设计

### 1. 页面路由规划

```typescript
// 管理面板路由
{
  path: '/admin',
  component: AdminLayout,
  children: [
    {
      path: 'debug',
      name: 'DebugDashboard',
      component: () => import('@/views/admin/DebugDashboard.vue'),
      meta: { title: 'Debug控制台', icon: 'Bug' }
    },
    {
      path: 'debug/reports',
      name: 'DebugReports',
      component: () => import('@/views/admin/DebugReports.vue'),
      meta: { title: '诊断报告', icon: 'FileText' }
    },
    {
      path: 'system',
      name: 'SystemStatus',
      component: () => import('@/views/admin/SystemStatus.vue'),
      meta: { title: '系统状态', icon: 'Monitor' }
    }
  ]
}
```

### 2. 组件结构

```
views/admin/
├── DebugDashboard.vue          # 主控制台
│   ├── components/
│   │   ├── HealthCard.vue      # 健康状态卡片
│   │   ├── ToolGrid.vue        # 工具网格
│   │   ├── ExecutionPanel.vue  # 执行面板
│   │   └── RealtimeLog.vue     # 实时日志
│   └── composables/
│       ├── useDebugTools.ts    # 工具管理
│       ├── useWebSocket.ts     # WS连接
│       └── useHealthCheck.ts   # 健康检查
│
├── DebugReports.vue            # 报告中心
│   ├── components/
│   │   ├── ReportList.vue      # 报告列表
│   │   ├── ReportDetail.vue    # 报告详情
│   │   └── ReportFilter.vue    # 筛选器
│
└── SystemStatus.vue            # 系统状态
    └── components/
        ├── ResourceChart.vue   # 资源图表
        └── ServiceStatus.vue   # 服务状态
```

### 3. API服务层

```typescript
// services/debugApi.ts
import axios from 'axios'

export class DebugApi {
  private baseUrl = '/api/v1/debug'
  
  // 获取工具列表
  async getTools() {
    return axios.get(`${this.baseUrl}/tools`)
  }
  
  // 执行Debug工具
  async executeTool(toolId: string, options?: Record<string, string>) {
    return axios.post(`${this.baseUrl}/execute`, {
      tool_id: toolId,
      options: options || {}
    })
  }
  
  // 获取执行历史
  async getExecutions(toolId?: string, limit = 10) {
    return axios.get(`${this.baseUrl}/executions`, {
      params: { tool_id: toolId, limit }
    })
  }
  
  // 获取聚合健康状态
  async getHealthAggregate() {
    return axios.get(`${this.baseUrl}/health/aggregate`)
  }
  
  // 获取报告列表
  async getReports(limit = 20) {
    return axios.get(`${this.baseUrl}/reports`, {
      params: { limit }
    })
  }
  
  // 获取系统信息
  async getSystemInfo() {
    return axios.get(`${this.baseUrl}/system/info`)
  }
  
  // 删除报告
  async deleteReport(reportId: string) {
    return axios.delete(`${this.baseUrl}/reports/${reportId}`)
  }
}

// WebSocket服务
export class DebugWebSocket {
  private ws: WebSocket | null = null
  private messageHandlers: Map<string, Function[]> = new Map()
  
  connect() {
    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/v1/debug/ws`
    this.ws = new WebSocket(wsUrl)
    
    this.ws.onopen = () => {
      console.log('[Debug WS] Connected')
      this.emit('connected', {})
    }
    
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      this.emit(data.type, data)
    }
    
    this.ws.onclose = () => {
      console.log('[Debug WS] Disconnected')
      this.emit('disconnected', {})
    }
    
    this.ws.onerror = (error) => {
      console.error('[Debug WS] Error:', error)
      this.emit('error', error)
    }
  }
  
  execute(toolId: string, options?: Record<string, string>) {
    this.send({
      action: 'execute',
      tool_id: toolId,
      options: options || {}
    })
  }
  
  checkHealth() {
    this.send({ action: 'health' })
  }
  
  ping() {
    this.send({ action: 'ping' })
  }
  
  private send(data: object) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }
  
  on(event: string, handler: Function) {
    if (!this.messageHandlers.has(event)) {
      this.messageHandlers.set(event, [])
    }
    this.messageHandlers.get(event)!.push(handler)
  }
  
  private emit(event: string, data: any) {
    const handlers = this.messageHandlers.get(event) || []
    handlers.forEach(h => h(data))
  }
  
  disconnect() {
    this.ws?.close()
  }
}

export const debugApi = new DebugApi()
export const debugWS = new DebugWebSocket()
```

### 4. 状态管理 (Pinia Store)

```typescript
// stores/debugStore.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { debugApi, debugWS } from '@/services/debugApi'

export const useDebugStore = defineStore('debug', () => {
  // State
  const tools = ref([])
  const executions = ref([])
  const reports = ref([])
  const healthStatus = ref(null)
  const systemInfo = ref(null)
  const isExecuting = ref(false)
  const currentExecution = ref(null)
  const wsConnected = ref(false)
  const realtimeOutput = ref('')
  
  // Getters
  const toolCategories = computed(() => {
    const categories = {}
    tools.value.forEach(tool => {
      if (!categories[tool.category]) {
        categories[tool.category] = []
      }
      categories[tool.category].push(tool)
    })
    return categories
  })
  
  const hasCriticalIssues = computed(() => {
    return healthStatus.value?.overall_status === 'critical'
  })
  
  const issueCount = computed(() => {
    return healthStatus.value?.issues?.length || 0
  })
  
  // Actions
  async function loadTools() {
    const response = await debugApi.getTools()
    tools.value = response.data
  }
  
  async function executeTool(toolId: string, options?: Record<string, string>) {
    isExecuting.value = true
    realtimeOutput.value = ''
    
    try {
      // 使用WebSocket实时执行
      if (wsConnected.value) {
        debugWS.execute(toolId, options)
      } else {
        // 降级为HTTP
        const response = await debugApi.executeTool(toolId, options)
        currentExecution.value = response.data
        executions.value.unshift(response.data)
      }
    } catch (error) {
      console.error('Execution failed:', error)
    }
  }
  
  function handleExecutionStarted(data: any) {
    currentExecution.value = {
      tool_id: data.tool_id,
      status: 'running',
      start_time: data.timestamp
    }
  }
  
  function handleExecutionCompleted(data: any) {
    isExecuting.value = false
    currentExecution.value = {
      ...currentExecution.value,
      status: data.status,
      output: data.output,
      json_output: data.json_output,
      duration_ms: data.duration_ms,
      end_time: data.timestamp
    }
    executions.value.unshift(currentExecution.value)
  }
  
  async function loadHealth() {
    const response = await debugApi.getHealthAggregate()
    healthStatus.value = response.data
  }
  
  async function loadReports() {
    const response = await debugApi.getReports()
    reports.value = response.data
  }
  
  async function loadSystemInfo() {
    const response = await debugApi.getSystemInfo()
    systemInfo.value = response.data
  }
  
  function connectWebSocket() {
    debugWS.connect()
    
    debugWS.on('connected', () => {
      wsConnected.value = true
    })
    
    debugWS.on('disconnected', () => {
      wsConnected.value = false
    })
    
    debugWS.on('started', (data) => {
      handleExecutionStarted(data)
    })
    
    debugWS.on('completed', (data) => {
      handleExecutionCompleted(data)
    })
    
    debugWS.on('health', (data) => {
      healthStatus.value = data.data
    })
  }
  
  return {
    tools,
    executions,
    reports,
    healthStatus,
    systemInfo,
    isExecuting,
    currentExecution,
    wsConnected,
    realtimeOutput,
    toolCategories,
    hasCriticalIssues,
    issueCount,
    loadTools,
    executeTool,
    loadHealth,
    loadReports,
    loadSystemInfo,
    connectWebSocket
  }
})
```

### 5. UI设计

#### DebugDashboard.vue
```vue
<template>
  <div class="debug-dashboard">
    <!-- 顶部状态栏 -->
    <div class="status-bar">
      <HealthCard 
        :status="healthStatus?.overall_status"
        :issues="healthStatus?.issues"
        @refresh="refreshHealth"
      />
    </div>
    
    <!-- 工具网格 -->
    <div class="tools-grid">
      <ToolCard
        v-for="tool in tools"
        :key="tool.id"
        :tool="tool"
        :is-running="isExecuting && currentExecution?.tool_id === tool.id"
        @execute="executeTool(tool.id)"
      />
    </div>
    
    <!-- 执行面板 -->
    <ExecutionPanel
      v-if="currentExecution"
      :execution="currentExecution"
      :output="realtimeOutput"
    />
    
    <!-- 最近报告 -->
    <RecentReports :reports="reports.slice(0, 5)" />
  </div>
</template>
```

#### 组件交互流程
```
用户点击"快速健康检查"
  ↓
store.executeTool('quick_check')
  ↓
WebSocket发送: {action: "execute", tool_id: "quick_check"}
  ↓
后端执行 scripts/debug/quick_check.sh --json
  ↓
WebSocket实时推送输出
  ↓
前端更新 ExecutionPanel 显示进度
  ↓
执行完成 → 解析JSON结果
  ↓
更新 HealthCard 状态
  ↓
保存到报告列表
```

---

## 后端工作流

### API端点清单

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/v1/debug/tools | 获取工具列表 | Admin |
| POST | /api/v1/debug/execute | 执行Debug工具 | Admin |
| GET | /api/v1/debug/executions | 获取执行历史 | Admin |
| GET | /api/v1/debug/executions/{id} | 获取执行详情 | Admin |
| GET | /api/v1/debug/health/aggregate | 聚合健康状态 | Admin |
| GET | /api/v1/debug/reports | 获取报告列表 | Admin |
| DELETE | /api/v1/debug/reports/{id} | 删除报告 | Admin |
| WS | /api/v1/debug/ws | WebSocket实时通信 | Admin |
| GET | /api/v1/debug/system/info | 系统信息 | Admin |

### 执行流程

```
1. 接收请求
   POST /api/v1/debug/execute
   Body: {"tool_id": "quick_check", "options": {}}

2. 验证工具
   - 检查tool_id是否在DEBUG_TOOLS列表中
   - 验证用户权限

3. 准备执行
   - 生成execution_id
   - 构建命令参数
   - 设置超时时间

4. 异步执行
   - 使用asyncio.create_subprocess_exec
   - 捕获stdout/stderr
   - 实时监控输出

5. 结果处理
   - 解析JSON输出（如果支持）
   - 保存执行记录到内存/文件
   - 返回执行结果

6. WebSocket推送（如果连接）
   - 发送started事件
   - 流式输出（未来扩展）
   - 发送completed事件
```

### 错误处理

```python
# 脚本未找到
{"code": 1, "message": "Script not found: /path/to/script.sh"}

# 执行超时
{"code": 1, "message": "Script timed out after 60s"}

# 执行错误
{"code": 1, "message": "Execution error: Permission denied"}

# 未知工具
{"code": 1, "message": "Unknown tool: invalid_tool_id"}
```

---

## 脚本目录结构

```
scripts/
├── debug/                          # Debug工作流目录
│   ├── README.md                   # 使用文档
│   ├── debug.sh                    # 统一入口
│   ├── quick_check.sh              # 快速健康检查
│   ├── api_debug.sh                # API接口测试
│   ├── database_debug.sh           # 数据库诊断
│   ├── security_audit.sh           # 安全审计
│   ├── performance_profile.sh      # 性能分析
│   ├── websocket_debug.py          # WebSocket测试
│   ├── log_analyzer.py             # 日志分析
│   └── frontend_debug.sh           # 前端调试
│
└── (其他业务脚本...)
```

---

## 工作流场景

### 场景1: 日常巡检
```
管理员打开Debug Dashboard
  ↓
查看HealthCard - 显示3个服务状态
  ↓
发现Frontend状态为unhealthy
  ↓
点击"快速健康检查"工具
  ↓
实时查看执行输出
  ↓
确认Frontend进程未运行
  ↓
执行start-services.sh restart
  ↓
再次运行健康检查验证
  ↓
状态恢复为healthy
```

### 场景2: 问题排查
```
用户反馈API响应慢
  ↓
管理员打开Debug Dashboard
  ↓
点击"性能分析"工具
  ↓
等待测试完成（约2分钟）
  ↓
查看报告 - 发现某API >500ms
  ↓
点击"日志分析"工具
  ↓
发现大量数据库查询日志
  ↓
定位到缺少索引
  ↓
修复后再次运行性能分析验证
```

### 场景3: 安全审计
```
定期执行（通过CI/CD或定时任务）
  ↓
调用POST /api/v1/debug/execute
  Body: {"tool_id": "security_audit"}
  ↓
后端执行security_audit.sh
  ↓
生成安全报告
  ↓
如果有漏洞 → 发送告警通知
  ↓
管理员在报告中心查看详情
```

### 场景4: 实时监控
```
前端建立WebSocket连接
  ↓
定时发送 {"action": "health"}
  ↓
后端返回聚合健康状态
  ↓
前端更新仪表盘
  ↓
如果状态变为critical
  ↓
自动弹出告警通知
  ↓
提供一键诊断按钮
```

---

## CI/CD集成

### GitHub Actions工作流
```yaml
name: Debug Audit
on:
  schedule:
    - cron: '0 2 * * *'  # 每天凌晨2点
  workflow_dispatch:

jobs:
  debug-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Run Health Check
        run: |
          ./scripts/debug/debug.sh quick --json > health.json
      
      - name: Run Security Audit
        run: |
          ./scripts/debug/security_audit.sh
      
      - name: Upload Reports
        uses: actions/upload-artifact@v4
        with:
          name: debug-reports
          path: |
            health.json
            /tmp/bandit-report.json
      
      - name: Check Results
        run: |
          if [ $(jq '.summary.failed' health.json) -gt 0 ]; then
            echo "Health check failed!"
            exit 1
          fi
```

---

## 扩展指南

### 添加新的Debug工具

1. 创建脚本 `scripts/debug/my_tool.sh`
2. 在 `backend/app/routers/debug.py` 的 `DEBUG_TOOLS` 列表中添加定义
3. 前端会自动显示新工具（无需修改前端代码）

### 添加新的API端点

1. 在 `debug.py` 中添加路由函数
2. 使用 `@router.get/post/put/delete` 装饰器
3. 自动集成到管理面板

### 自定义前端组件

1. 在 `views/admin/components/` 创建组件
2. 在DebugDashboard中引用
3. 使用 `useDebugStore` 获取数据

---

## 安全考虑

1. **权限控制**: Debug API仅允许管理员访问
2. **命令注入防护**: 所有脚本参数经过验证和转义
3. **超时保护**: 脚本执行有最大超时限制
4. **资源限制**: 使用asyncio防止资源耗尽
5. **日志脱敏**: 自动检测并隐藏敏感信息

---

## 性能指标

| 指标 | 目标 | 当前 |
|------|------|------|
| 健康检查响应时间 | < 5s | ~3s |
| API测试响应时间 | < 10s | ~8s |
| 数据库检查响应时间 | < 15s | ~5s |
| WebSocket连接延迟 | < 100ms | ~50ms |
| 报告列表加载 | < 1s | ~200ms |

---

## 版本历史

### v3.0 (2024-05-02)
- 管理面板联动设计
- WebSocket实时通信
- 统一的Debug工作流
- 前端组件架构

### v2.0 (2024-05-02)
- 统一debug入口脚本
- JSON输出支持
- WebSocket测试工具
- 日志分析工具

### v1.0 (2024-05-01)
- 初始版本
- 6个独立脚本

---

**维护者**: AlphaTerminal Team
**文档版本**: 3.0
