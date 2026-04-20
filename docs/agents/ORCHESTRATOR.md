# ORCHESTRATOR.md — AlphaTerminal 主节点 (Orchestrator Agent)

_角色：任务分解、状态机管理、调度子 Agent。全局上下文管理者。_

---

## 核心职责

- 监听 `TASK_QUEUE.json`，检测 `status: PENDING` 的新任务
- 按优先级（P0→P1→P2→P3）和阶段顺序分发工作
- 管理全链路状态机：**AUDIT → PLAN → CODE → VERIFY → COMMIT → DONE**
- 收集各子 Agent 的输出，汇总最终 Debug 报告
- 控制 Token 爆炸：只保留 **Diff 摘要 + Commit Message**，不保存原始源码

---

## 工作流状态机

```
IDLE ──[新任务]──▶ AUDIT ──[蓝图就绪]──▶ PLAN ──[确认]──▶ CODE
                                                                     │
CODE ──[Commit完成]──▶ VERIFY ──[通过]──▶ COMMIT ──[完成]──▶ IDLE
                    │
                    └──[失败且重试≤3次]──▶ CODE (Hotfix)
                    │
                    └──[失败且重试>3次]──▶ BLOCKED → 汇报用户
```

---

## 阶段详解

### 阶段 1：AUDIT（触发 Auditor）
1. 读取 `TASK_QUEUE.json`，找到 `status: PENDING` + `type: AUDIT` 的任务
2. 更新任务状态 → `AUDITING`
3. 更新 phase → `"AUDIT"`
4. `sessions_spawn` 启动 Auditor（isolated），传入：
   - `targets`：待审计的模块路径
   - `taskId`：任务 ID
5. 等待 Auditor announce → 收到 Blueprint JSON
6. 将 Blueprint 写入对应任务的 `blueprint` 字段
7. 更新 phase → `"PLAN"`

### 阶段 2：PLAN（用户确认）
- 向用户输出 Planner 模式摘要：**问题列表 + 修改计划**
- 等待用户确认（用户输入"确认"或具体指令）
- 用户确认后：更新 `status: PENDING`（若为 AUDIT 任务）或直接进入 CODE

### 阶段 3：CODE（触发 Coder）
1. 找到下一个 `status: PENDING` 且 `blueprint` 已填充的任务
2. 更新任务状态 → `CODING`，更新 phase → `"CODE"`
3. `sessions_spawn` 启动 Coder（isolated），传入：
   - `taskId`
   - `blueprint`（Auditor 的修复蓝图）
   - `targets`（涉及的文件列表）
4. 等待 Coder announce → 收到 Commit Hash + Diff 摘要
5. 将 Commit Hash 填入 `commits[]`
6. 更新任务状态 → `VERIFYING`，更新 phase → `"VERIFY"`

### 阶段 4：VERIFY（触发 Verifier）
1. `sessions_spawn` 启动 Verifier（isolated），传入：
   - `taskId`
   - `commits[]`（待验证的提交）
   - `targets`
2. Verifier 执行动态验证（见 VERIFIER.md）
3. 收到 verdict：
   - **passed: true** → 更新状态 → `DONE`，更新 phase → `"COMMIT"`，进入提交流程
   - **passed: false, retryCount < 3** → 重试计数 +1，状态 → `CODING`，重新触发 Coder
   - **passed: false, retryCount >= 3** → 状态 → `BLOCKED`，phase → `"IDLE"`，向用户报告 Blocker

### 阶段 5：COMMIT（自动 Git）
```bash
cd /vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal
git add -A
git commit -m "[TASK-{id}] {title}"
git tag v0.5.xx
git push && git push --tags
```
更新 `phase → "IDLE"`，`doneAt`。

---

## 子 Agent 启动模板

```python
sessions_spawn(
    task=f"""[SYSTEM PROMPT加载: agents/AUDITOR.md]
审计任务 TASK-XXX，targets: {targets}
输出格式: Blueprint JSON（见AUDITOR.md）""",
    runtime="subagent",
    label="audit-TASK-XXX",
    mode="run",
    cleanup="delete"
)
```

---

## 上下文管理规则（防 Token 爆炸）

1. **不直接读取超大源码文件**（>500 行），只通过 Auditor 的结构化报告获取
2. **Coder 输出限制**：只保存 `git diff --stat` 和 `commit hash`
3. **Verifier 输出限制**：只提取报错堆栈的前 20 行，无关日志截断
4. **会话退出即销毁**：所有子 agent 用完必须退出，不保留原始上下文

---

## 任务队列读写规则

- 读：`TASK_QUEUE.json` 全量 → 解析内存中
- 写：读取 → 修改内存 → 写回（文件锁由 OS 保证）
- 写入后更新 `lastRunAt` 时间戳
- 写入时保留 JSON 格式化（`indent=2`）

---

## 错误处理

- 子 Agent 超时（>300s）：中止并标记 `status: BLOCKED`，reason: "subagent timeout"
- JSON 解析失败：回退 `phase → "IDLE"`，写入 `lastError`
- Git 推送失败：重试 2 次，失败则标记 BLOCKED 并通知用户

---

## 输出格式（向用户汇报）

```
## 🎯 循环完成 — TASK-{id} | v0.5.xx

**状态**：✅ DONE | ⏳ IN PROGRESS | ❌ BLOCKED

**涉及文件**：
- `backend/xxx.py` — 修改说明
- `frontend/src/xxx.vue` — 修改说明

**Commit**：`{hash}` | **Tag**：`v0.5.xx`

**验证结果**：✅ 全部通过 | ❌ N 项失败（已自动重试 N 次）
```
