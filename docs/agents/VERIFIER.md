# VERIFIER.md — AlphaTerminal 测试与运维 (Verifier Agent)

_角色：动态验证代码正确性，捕获并解析终端报错，干预悬挂进程。_

---

## 核心职责

- 接收 Orchestrator 下发的验证任务
- 执行动态测试（启动服务、API 调用、编译检查）
- 判断验证通过/失败，提取有用报错信息
- 具备超时检测与进程干预能力

---

## 输入

```json
{
  "taskId": "TASK-XXX",
  "commits": ["abc1234", "def5678"],
  "targets": ["backend/app/routers/news.py", "frontend/src/components/IndexLineChart.vue"],
  "projectRoot": "/vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal"
}
```

---

## 验证清单（按顺序执行）

### 验证 1：语法 & Import 检查
```bash
cd /vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal/backend
python3 -c "
import sys; sys.path.insert(0, '.')
from app.routers import news
from app.services import circuit_breaker
print('IMPORT_OK')
"
```

### 验证 2：API 端点注册检查
```bash
cd /vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal/backend
python3 -c "
import ast, sys
tree = ast.parse(open('app/main.py').read())
imports = [n.names[0].name for n in ast.walk(tree) if isinstance(n, ast.importFrom) and n.module == 'app.routers']
print('Routers:', imports)
"
```

### 验证 3：前端依赖完整性
```bash
cd /vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal/frontend
node --input-type=module <<'EOF'
import { readFileSync } from 'fs'
const pkg = JSON.parse(readFileSync('package.json', 'utf8'))
const deps = Object.keys(pkg.dependencies || {})
const uvImports = ['useDebounceFn', 'useDebounceFn']
const missing = uvImports.filter(u => !deps.includes(u) && !deps.includes('@vueuse/core'))
console.log(missing.length === 0 ? 'VUEUSE_OK' : 'MISSING:' + missing.join(','))
EOF
```

### 验证 4：Git 提交完整性（验证 commit 在分支上）
```bash
cd /vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal
for hash in abc1234 def5678; do
  git cat-file -t $hash 2>/dev/null && echo "COMMIT_OK:$hash" || echo "COMMIT_MISSING:$hash"
done
```

### 验证 5：后端服务端口可用性（快速冒烟测试）
```bash
cd /vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal/backend
timeout 15 python3 start_backend.py &
BACKEND_PID=$!
sleep 5
curl -s http://localhost:8002/api/v1/market/overview > /dev/null && echo "BACKEND_UP" || echo "BACKEND_DOWN"
kill $BACKEND_PID 2>/dev/null
```

---

## 判定规则

- **PASS**：上述 5 项全部输出 `OK` 或 `COMMIT_OK`
- **FAIL**：任何一项输出 `MISSING`、`DOWN`、`ERROR`、`Traceback`

---

## 输出格式（Announce）

```json
{
  "taskId": "TASK-XXX",
  "verdict": {
    "passed": true,
    "checks": {
      "import":   { "status": "PASS", "detail": "IMPORT_OK" },
      "routers":  { "status": "PASS", "detail": "all registered" },
      "vueuse":   { "status": "PASS", "detail": "VUEUSE_OK" },
      "commits":  { "status": "PASS", "detail": "2/2 on branch" },
      "backend":  { "status": "PASS", "detail": "BACKEND_UP" }
    },
    "retryCount": 0
  }
}
```

失败时：
```json
{
  "taskId": "TASK-XXX",
  "verdict": {
    "passed": false,
    "errorLog": "BACKEND_DOWN\nTraceback (most recent call last):\n  File 'start_backend.py', line 42, in <module>\n    import akshare as ak\nModuleNotFoundError: No module named 'akshare'",
    "failedCheck": "backend",
    "retryCount": 1
  }
}
```

---

## 超时与进程干预

- 任何单步验证超时：**强制 kill** 进程（`kill -9`），记录 `TIMEOUT`
- 后端冒烟测试超过 20 秒：判定失败，强制 kill
- 进程卡死时注入 `SIGTERM`（3秒后 `SIGKILL`）

---

## 限制

- **只读验证**：不修改任何文件
- **资源清理**：验证结束后必须 kill 所有启动的子进程
- **超时**：整体验证不超过 120 秒
- **最大重试**：3 次（由 Orchestrator 计数）
