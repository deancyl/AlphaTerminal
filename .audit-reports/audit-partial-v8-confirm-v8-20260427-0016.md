# AlphaTerminal v8 审计确认报告 - 第14次

**时间:** 2026-04-27 00:16 CST  
**提交范围:** 2d61433..83cee28

---

## 🔍 代码变更检测

### 新提交 (2个)
| 提交 | 描述 | 文件 |
|------|------|------|
| `fa301e3` | fix: P1-5 admin auth + P0-2 copilot API key + P1-2 trading double close | admin.py, copilot.py, trading.py |
| `83cee28` | fix: P2-12 backtest.py benchmark_return_pct 除零风险 | backtest.py |

### 修复验证

| 问题ID | 文件 | 状态 | 验证结果 |
|--------|------|------|----------|
| P2-12 | backtest.py | ✅ 已修复 | `first_close <= 0` 除零保护正确 |
| P1-5 | admin.py | ❌ 引入新P0 | `verify_admin_key` 定义顺序错误 |
| P0-2 | copilot.py | ✅ 已修复 | API Key 常量已定义 |
| P1-2 | trading.py | ✅ 已修复 | 双重 close 已移除 |

---

## 🚨 新发现问题

### P0-NEW-1: admin.py 启动时 NameError

**严重程度:** P0 (Critical)  
**文件:** `backend/app/routers/admin.py`  
**行号:** 33

**问题描述:**
```python
router = APIRouter(
    prefix="/admin", 
    tags=["admin"],
    dependencies=[Depends(verify_admin_key)]  # ← NameError: verify_admin_key 未定义
)

# ... 后面才定义 ...
def verify_admin_key(api_key: str = None):
    ...
```

**验证结果:**
```bash
$ python3 -c "from app.routers.admin import router"
NameError: name 'verify_admin_key' is not defined
```

**影响:** 后端启动失败，所有 `/admin/*` 端点不可用

**修复建议:** 将 `verify_admin_key` 函数定义移到 `router = APIRouter(...)` 之前

---

## 📊 累计统计

| 优先级 | 已修复 | 待修复 |
|--------|--------|--------|
| P0 (Critical) | 1 | **2** |
| P1 (High) | 5 | 9 |
| P2 (Medium) | 3 | 26 |
| P3 (Low) | 0 | 5 |
| **总计** | **9** | **42** |

### P0 问题清单
1. **P0-1** - data_fetcher.py 同步阻塞 HTTP (待修复)
2. **P0-NEW-1** - admin.py NameError 启动失败 (新发现)

---

## 📌 审计结论

fa301e3 提交修复了 P1-5、P0-2、P1-2，但引入了新的 P0 级别启动错误。建议立即修复 P0-NEW-1。

---

*报告由 AlphaTerminal-Code-Audit cron 任务自动生成*
