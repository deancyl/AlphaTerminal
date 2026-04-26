# AUDIT-CONSTRAINTS.md — 审计任务统一约束

## 死命令 (绝对禁止)
- 禁止删除总报告 `audit-master.md`
- 禁止删除任何审计报告文件
- 禁止修改已存在的审计报告内容 (仅允许追加)
- 禁止在其他分支生成或修改总日志
- 违反命令立即终止任务并报错

## 总日志管理规则
- 总日志 (audit-master.md) 只能存在于主分支 (main/master)
- 其他分支有总日志则先合并到主分支
- 所有修复记录统一合并到主分支的总日志

## Token 控制规则
- 无代码变更则跳过审计 (检查 git log)
- 分页读取大文件 (offset/limit)
- 不重复读取已读内容
- 快速退出: 检测到无工作立即结束
- 批量操作合并为单次调用

## Karpathy 准则
- Think Before Coding: 明确目标，多解时呈现
- Simplicity First: 50行搞定，不复杂化
- Surgical Changes: 只碰被要求的部分
- Goal-Driven: 每步有验证标准

## 文件路径
- 项目: /vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal
- 审计报告: .audit-reports/
- 总报告: .audit-reports/audit-master.md
- 进度文件: /tmp/alphaterminal-audit-progress.json
- 修复记录: /tmp/audit-mmf-fixes.json
- 代理: http://192.168.1.50:7897
