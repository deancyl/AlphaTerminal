#!/usr/bin/env bash
#===============================================================================
# AlphaTerminal Debug Scripts - README
#===============================================================================

# Debug脚本集合使用说明

## 快速开始

### 1. 统一入口（推荐）
```bash
# 快速健康检查
./scripts/debug.sh quick

# 完整诊断
./scripts/debug.sh full

# 仅检查API
./scripts/debug.sh api

# JSON输出（用于CI/CD）
./scripts/debug.sh full --json
```

### 2. 单独使用各个脚本
```bash
# 健康检查
./scripts/quick_check.sh

# API测试
./scripts/api_debug.sh

# 数据库检查
./scripts/database_debug.sh

# 性能分析
./scripts/performance_profile.sh

# 安全审计
./scripts/security_audit.sh

# WebSocket测试
python3 scripts/websocket_debug.py

# 日志分析
python3 scripts/log_analyzer.py
```

## 脚本说明

### debug.sh - 统一调试入口
- **功能**: 统一的debug orchestrator，支持多种模式和输出格式
- **模式**: quick, api, database, security, performance, websocket, logs, full
- **选项**:
  - `--json`: JSON输出（用于CI/CD集成）
  - `--output-dir`: 报告输出目录
  - `--backend-url`: 后端地址
  - `--frontend-url`: 前端地址
  - `--verbose`: 详细输出

### quick_check.sh - 快速健康检查
- **功能**: 快速检查服务状态
- **检查项**: Backend/Frontend健康、进程状态、端口占用
- **增强**: v2.0支持JSON输出

### api_debug.sh - API测试
- **功能**: 测试所有API端点
- **覆盖**: Health, Market, Macro, Portfolio, Backtest, News, Sentiment
- **输出**: 彩色状态报告，支持失败统计

### database_debug.sh - 数据库检查
- **功能**: SQLite数据库完整性检查
- **检查项**: 完整性校验、表行数统计、索引检查
- **支持**: 自动查找多个可能的数据库路径

### security_audit.sh - 安全审计
- **功能**: 安全扫描
- **工具**: Bandit, Safety, Semgrep
- **检查**: 硬编码密钥、已知漏洞、代码安全

### performance_profile.sh - 性能分析
- **功能**: API响应时间测试
- **方法**: 多次请求取平均值
- **分级**: <100ms(优秀), 100-500ms(良好), >500ms(缓慢)

### websocket_debug.py - WebSocket测试
- **功能**: 测试WebSocket连接和消息流
- **指标**: 连接延迟、消息收发、错误统计
- **依赖**: websockets库（自动安装）

### log_analyzer.py - 日志分析
- **功能**: 分析后端和前端日志
- **检测**: ERROR/WARNING计数、异常模式、最近错误
- **输出**: 状态报告、错误详情、趋势分析

### frontend_debug.sh - 前端调试
- **功能**: 运行Playwright自动化测试
- **模式**: quick(截图), full(全面), screenshot(整页)
- **依赖**: Playwright（自动安装）

## CI/CD集成

### GitHub Actions示例
```yaml
- name: Run Debug Checks
  run: |
    ./scripts/debug.sh full --json > debug_report.json
    
- name: Upload Debug Report
  uses: actions/upload-artifact@v4
  with:
    name: debug-report
    path: debug_report.json
```

### 预提交钩子
```bash
#!/bin/sh
# .git/hooks/pre-commit
./scripts/quick_check.sh --json > /dev/null || exit 1
```

## 输出格式

### 标准输出（人类可读）
- 彩色状态指示
- 执行时间统计
- 详细错误信息

### JSON输出（机器可读）
```json
{
  "timestamp": "2024-01-01T12:00:00",
  "mode": "full",
  "checks": {
    "Backend Health": {
      "status": "passed",
      "duration_ms": 15
    }
  },
  "summary": {
    "passed": 10,
    "failed": 0,
    "warnings": 1,
    "total": 11
  }
}
```

## 故障排查

### 常见问题

**Q: 脚本提示权限不足**
```bash
chmod +x scripts/*.sh
```

**Q: Python脚本缺少依赖**
```bash
pip install --break-system-packages websockets
```

**Q: JSON输出需要jq**
```bash
apt-get install jq  # Debian/Ubuntu
```

### 调试流程建议

1. **发现问题** → 运行 `./scripts/debug.sh quick`
2. **定位问题** → 运行 `./scripts/debug.sh full`
3. **深入分析** → 运行具体脚本（api/database/websocket等）
4. **修复验证** → 再次运行 `./scripts/debug.sh quick`

## 扩展开发

### 添加新的检查项
在 `debug.sh` 中添加新的函数：
```bash
run_custom() {
    print_header "Custom Check"
    run_check "My Check" "my_command" 0 "expected"
}
```

### 自定义输出格式
修改 `add_json_result` 函数支持自定义字段。

## 版本历史

### v2.0 (2024-05-02)
- 统一debug入口脚本
- JSON输出支持
- WebSocket测试工具
- 日志分析工具
- 性能优化

### v1.0 (2024-05-01)
- 初始版本
- 6个独立脚本

---

**维护者**: AlphaTerminal Team
**问题反馈**: https://github.com/deancyl/AlphaTerminal/issues
