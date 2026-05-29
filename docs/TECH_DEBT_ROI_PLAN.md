# AlphaTerminal 技术债务 ROI 分析与稳定化冻结计划

**版本**: v0.6.201  
**日期**: 2026-05-25  
**状态**: 规划中

---

## 一、当前状态评估

### 1.1 架构健康分数: 6.5/10

| 维度 | 分数 | 说明 |
|------|------|------|
| 代码组织 | 6/10 | 路由文件过大，需要拆分 |
| 性能 | 7/10 | 已优化线程池和缓存 |
| 稳定性 | 7/10 | 熔断器和重试机制完善 |
| 可维护性 | 5/10 | 部分代码缺少测试覆盖 |
| 安全性 | 7/10 | 已实现异常处理装饰器 |

### 1.2 技术债务清单

| 优先级 | 问题 | 影响 | 修复工作量 |
|--------|------|------|-----------|
| P0 | error_decorator.py 函数签名错误 | 测试失败 | ✅ 已修复 |
| P0 | market_mock.py 孤立文件 | 安全风险 | ✅ 已移除 |
| P1 | LLM 情绪分析未实现 | 功能缺失 | ✅ 已标注 |
| P1 | Agent 回测端点未实现 | 功能缺失 | ✅ 已标注 |
| P2 | console.log 在生产环境 | 信息泄露风险 | ✅ 已有 logger |
| P2 | DEBUG_MODE 默认值 | 日志过多 | ✅ 已修复 |

---

## 二、ROI 计算

### 2.1 技术债务成本模型

```
每周浪费 = (工程师人数 × 平均时薪) × (修复回归问题时间占比)
         = 1 × $50/hr × 12 hrs/周 = $600/周
年浪费 = $600 × 52 = $31,200/年
```

### 2.2 修复 ROI 分析

| 修复项 | 投资 | 年节省 | 回收期 | ROI |
|--------|------|--------|--------|-----|
| ThreadPoolExecutor 整合 | 4 周 × 1 工程师 | $28,800 | 7 月 | 72% |
| ECharts 内存泄漏修复 | 1 周 × 2 工程师 | $14,400 | 4 月 | 41% |
| 路由文件拆分 | 2 周 × 1 工程师 | $9,600 | 3 月 | 35% |
| 特征化测试补充 | 3 周 × 1 工程师 | $12,000 | 5 月 | 38% |

---

## 三、稳定化冻结计划

### 3.1 冻结范围

**停止添加**:
- 新模块（已足够：agentic, attribution, market_radar, factor_sandbox, timemachine）
- 新路由端点（已有 466 个）
- 新前端组件（已有 153 个）

**允许进行**:
- Bug 修复
- 性能优化
- 测试补充
- 文档完善

### 3.2 时间线

```
v0.6.200 ─────────────────────────────────────────────────────► v0.7.0
   │                                                              │
   ├── Week 1-2: P0 Bug 修复 ✅                                   │
   ├── Week 3-4: 路由文件拆分                                     │
   ├── Week 5-6: 事件循环保护                                     │
   ├── Week 7-8: 前端内存泄漏修复                                 │
   ├── Week 9-10: 特征化测试补充                                  │
   └── Week 11-12: 架构文档完善                                   │
```

### 3.3 每个 Sprint 的债务容量

| Sprint 类型 | 功能开发 | 债务修复 | 说明 |
|------------|----------|----------|------|
| 常规 Sprint | 80% (16 pts) | 20% (4 pts) | 正常迭代 |
| 稳定化 Sprint | 50% (10 pts) | 50% (10 pts) | 当前阶段 |
| 纯债务 Sprint | 0% (0 pts) | 100% (20 pts) | 紧急修复 |

---

## 四、安全重构指南

### 4.1 可以安全重构

| 项目 | 风险 | 预计工作量 |
|------|------|-----------|
| admin.py 拆分 (2425 行 → 6 文件) | 低 | 3 天 |
| macro.py 拆分 (2315 行 → 3 文件) | 低 | 2 天 |
| 移除旧执行器模式 (27 文件) | 低 | 2 天 |
| 前端清理工具类提取 | 低 | 1 天 |

### 4.2 需要架构评审后重构

| 项目 | 风险 | 原因 |
|------|------|------|
| DataCache 重写 (1516 行) | 高 | 复杂 TTL/LRU 逻辑 |
| Backtest 引擎 (1447 行) | 高 | 金融计算核心 |
| WebSocket 管理器 | 高 | 实时通信基础设施 |
| CircuitBreaker 整合 | 中 | 172 处引用 |

---

## 五、成功指标

### 5.1 量化目标

| 指标 | 当前值 | 目标值 | 截止日期 |
|------|--------|--------|----------|
| P0 事故数 | 5+/版本 | 0/版本 | v0.7.0 |
| 测试覆盖率 | ~60% | 80% | v0.7.0 |
| 最大路由文件行数 | 2425 | 500 | v0.7.0 |
| API 响应时间 P95 | 500ms | 200ms | v0.7.0 |

### 5.2 定性目标

- [ ] 所有 P0 Bug 已修复
- [ ] 所有 TODO 已处理或标注
- [ ] 架构图已更新到 AGENTS.md
- [ ] 新开发者可以在 1 小时内理解项目结构

---

## 六、行动计划

### Week 1-2 (当前): P0 Bug 修复 ✅

- [x] 修复 error_decorator.py 函数签名
- [x] 移除 market_mock.py
- [x] 标注 agent.py TODO
- [x] 验证 DEBUG_MODE 默认值

### Week 3-4: 路由文件拆分

- [ ] 创建 `backend/app/routers/admin/` 子目录
- [ ] 拆分 admin.py 为 6 个模块
- [ ] 拆分 macro.py 为 3 个模块
- [ ] 更新导入语句

### Week 5-6: 事件循环保护

- [ ] 检查所有 akshare 调用
- [ ] 确保所有阻塞调用在 executor 中
- [ ] 添加超时保护

### Week 7-8: 前端内存泄漏修复

- [ ] 检查所有 ECharts 组件
- [ ] 确保 onDeactivated 清理
- [ ] 减少 KeepAlive 缓存大小

### Week 9-10: 特征化测试补充

- [ ] ML Strategy 模块特征化测试
- [ ] Options Greeks 模块特征化测试
- [ ] Factor Sandbox 模块特征化测试

### Week 11-12: 架构文档完善

- [ ] 更新 AGENTS.md 架构图
- [ ] 创建 ADR (Architecture Decision Records)
- [ ] 更新 README.md

---

## 七、参考资源

- [Martin Fowler - Strangler Fig Pattern](https://martinfowler.com/bliki/StranglerFigApplication.html)
- [Michael Feathers - Working Effectively with Legacy Code](https://www.oreilly.com/library/view/working-effectively-with/0131177052/)
- [Spotify - Honk Agent Framework (QCon 2026)](https://qconnewyork.com/)
- [Etsy - Vitess Migration](https://www.etsy.com/)

---

**文档维护者**: AlphaTerminal 开发团队  
**最后更新**: 2026-05-25
