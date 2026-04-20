# AlphaTerminal Agent System — 架构说明

## 目录结构

```
AlphaTerminal/docs/agents/
├── README.md              # 本文件
├── TASK_QUEUE.json        # 共享状态文件（Orchestrator 读写）
├── TASK_QUEUE_SCHEMA.json # JSON Schema 定义
├── ORCHESTRATOR.md        # 主节点指令
├── AUDITOR.md             # 审查员指令
├── CODER.md               # 施工队指令
└── VERIFIER.md            # 测试员指令
```

## 角色与工具约束

| 角色 | 工具权限 | 上下文 |
|------|---------|--------|
| **Orchestrator**（主 session） | 所有工具 | TASK_QUEUE.json / AGENTS.md |
| **Auditor**（子 agent） | `exec`（只读 grep/cat）| Blueprint JSON |
| **Coder**（子 agent） | `exec`（读/写/提交）| Blueprint JSON |
| **Verifier**（子 agent） | `exec`（读/验证/kill）| commits / targets |

## 全自动循环流程

```
架构师写入 TASK_QUEUE.json
         │
         ▼
[心跳检测] ──phase==IDLE & PENDING tasks──▶ 启动 Orchestrator
         │
         ▼
  Auditor (只读审计) ──▶ Blueprint JSON
         │
         ▼
  Coder (按蓝图施工) ──▶ Git commits
         │
         ▼
  Verifier (动态验证) ──▶ verdict
         │
    ┌────┴────┐
  PASS        FAIL (≤3次)
    │            │
    ▼            ▼
  DONE       Coder 重试
                    │
                 FAIL (>3次)
                    │
                    ▼
               BLOCKED → 用户告警
```

## 使用方法

### 下发任务（架构师操作）

在 `TASK_QUEUE.json` 中添加任务，例如：

```json
{
  "tasks": [
    {
      "id": "TASK-001",
      "title": "F10基本面数据补全",
      "description": "新增个股财务指标、龙虎榜、大宗交易 API",
      "status": "PENDING",
      "type": "FEATURE",
      "priority": "P1",
      "targets": [
        "backend/app/routers/stocks.py",
        "frontend/src/components/StockDetailPanel.vue"
      ],
      "createdAt": "2026-04-21T01:30:00+08:00",
      "updatedAt": "2026-04-21T01:30:00+08:00"
    }
  ]
}
```

更新 `phase` 为任意非 `"IDLE"` 值即可触发心跳检测。

### 查看状态

```bash
cat AlphaTerminal/docs/agents/TASK_QUEUE.json | python3 -m json.tool
```

### 中断循环

将 `phase` 设为 `"IDLE"`，或将目标任务 `status` 设为 `"CANCELLED"`。
