# AlphaTerminal 历史数据扩展指南

## 概述

AlphaTerminal 目前存在以下数据限制：
- **已有历史数据**：上证指数 (000001)、沪深300 (000300)、深证成指 (399001)、创业板指 (399006) 等四个主要指数已有 5+ 年历史数据（8614/5881/8522/3846 条记录）
- **数据缺失**：美股指数 (IXIC/NDX/SPX/DJI)、港股指数 (HSI)、商品 (GLD/WTI) 等只有 1 天数据

## 解决方案

本方案使用 **Alpha Vantage API** 作为主要数据源，获取美股/港股/商品的历史数据，并存储到本地 SQLite 数据库。

## 前置要求

### 1. Alpha Vantage API Key（必需）

1. 注册 Alpha Vantage 账户：https://www.alphavantage.co/support/#api-key
2. 获取免费的 API Key（每天 25 次请求，每分钟 5 次请求）
3. 设置环境变量：
   ```bash
   export ALPHA_VANTAGE_API_KEY=your_api_key_here
   ```

### 2. 代理设置（可选）

如果你的网络环境需要代理访问 Alpha Vantage API（国际网站），请在 `.env` 文件中配置：
```bash
HTTP_PROXY=http://192.168.1.50:7897
HTTPS_PROXY=http://192.168.1.50:7897
```

## 使用指南

### 1. 配置环境变量

```bash
# 方式一：直接导出环境变量
export ALPHA_VANTAGE_API_KEY=your_api_key_here

# 方式二：编辑 .env 文件
nano .env
# 填入你的 API Key
```

### 2. 初始化数据库（首次使用）

数据库表已经创建，无需手动初始化。但如果需要重新创建，可以运行：
```bash
cd /vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal
backend/.venv/bin/python scripts/init_database.py
```

### 3. 运行历史数据抓取脚本

```bash
cd /vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal
backend/.venv/bin/python scripts/fetch_historical_data.py
```

**注意**：
- 脚本会自动检测哪些标的需要拉取历史数据（已有 1 天数据的会被拉取）
- 脚本遵守 Alpha Vantage API 限制（每分钟 5 次请求，每天 25 次请求）
- 对于 11 个主要标的，预计需要约 3-5 分钟完成

### 4. 验证数据

检查数据库中的数据：
```bash
cd /vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal/backend
.venv/bin/python -c "
from app.db import get_daily_count
symbols = ['ixic', 'ndx', 'spx', 'dji', 'hsi', 'glg', 'wti', 'vix']
for sym in symbols:
    print(f'{sym}: {get_daily_count(sym)} rows')
"
```

### 5. 重启后端服务

```bash
# 停止现有后端
pkill -f "uvicorn app.main:app"

# 启动后端（如果需要加载环境变量）
source .env
cd backend
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

## 技术架构

### 数据流程

```
Alpha Vantage API → 历史数据 → SQLite 数据库 (/tmp/alpha_ultimate_active.db) → 后端 API → 前端 K 线图
```

### 支持的数据源

1. **Alpha Vantage API**（主要）：
   - 美股指数：IXIC, NDX, SPX, DJI
   - 港股指数：HSI
   - 商品：GLD (黄金), WTI (原油), VIX (波动率), DXY (美元指数)

2. **AkShare**（已集成）：
   - A 股指数：000001, 000300, 399001, 399006
   - A 股个股

3. **腾讯行情**（实时数据补充）：
   - 今日实时数据（用于当日未收盘时）

### 数据库表结构

```sql
CREATE TABLE market_data_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER NOT NULL,
    change_pct REAL,
    timestamp INTEGER NOT NULL,
    data_type TEXT NOT NULL DEFAULT 'daily',
    UNIQUE(symbol, date)
);
```

## API 限制说明

### Alpha Vantage API 限制

- **免费版**：每天 25 次请求，每分钟 5 次请求
- **付费版**：$0.01/请求，更高频率
- **建议**：优先使用免费版测试，如需更高频率可升级

### 脚本优化策略

1. **智能检测**：只拉取缺失的历史数据（已有 >1 条数据的跳过）
2. **限流控制**：每次请求间隔 13 秒（确保不超过每分钟 5 次限制）
3. **批量处理**：自动处理 11 个主要标的，无需手动逐个配置

## 已知问题

### 1. VIX/CNH 数据缺失

- **原因**：Alpha Vantage 不直接支持 VIX 和 CNH 的历史数据
- **解决方案**：需要寻找其他数据源（如 CBOE、美联储数据）

### 2. 数据准确性

- **问题**：不同数据源的数据可能存在差异
- **验证**：建议与官方数据源对比验证

### 3. 网络访问

- **问题**：Alpha Vantage API 是国际网站，可能需要代理
- **解决**：配置 HTTP_PROXY/HTTPS_PROXY 环境变量

## 定时更新

### 手动更新

运行历史数据抓取脚本：
```bash
backend/.venv/bin/python scripts/fetch_historical_data.py
```

### 自动化定时任务（推荐）

使用 cron 定期更新数据：
```bash
# 编辑 crontab
crontab -e

# 添加定时任务（每天收盘后更新）
0 18 * * 1-5 cd /vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal && backend/.venv/bin/python scripts/fetch_historical_data.py >> logs/data_update.log 2>&1
```

## 故障排除

### 问题：API Key 未配置

**症状**：
```
[ERROR] 未设置 ALPHA_VANTAGE_API_KEY 环境变量
```

**解决方法**：
```bash
export ALPHA_VANTAGE_API_KEY=your_api_key_here
```

### 问题：网络连接失败

**症状**：
```
[Alpha Vantage] symbol 网络错误: HTTPSConnectionPool
```

**解决方法**：
1. 检查代理配置是否正确
2. 测试代理是否可用：
   ```bash
   curl -x http://192.168.1.50:7897 https://www.alphavantage.co
   ```

### 问题：API 限制

**症状**：
```
[Alpha Vantage] symbol API 限制: API call frequency
```

**解决方法**：
1. 等待 1 分钟后重试
2. 升级到付费版 API Key
3. 分批拉取数据（每天拉取 5 个标的）

### 问题：数据未更新

**症状**：K 线图仍然只显示 1 天数据

**解决方法**：
1. 检查数据库中是否已有数据：
   ```bash
   backend/.venv/bin/python -c "from app.db import get_daily_count; print(get_daily_count('ixic'))"
   ```
2. 重启后端服务
3. 清除浏览器缓存并刷新页面

## 性能优化

### 数据库索引

已创建以下索引以提升查询性能：
```sql
CREATE INDEX idx_daily_sym ON market_data_daily(symbol);
CREATE INDEX idx_daily_sym_date ON market_data_daily(symbol, date);
```

### 查询优化

后端 API 已优化，支持分页查询：
- 默认返回 300 条记录
- 支持通过 `offset` 参数加载更多数据

### 缓存策略

前端已实现数据缓存：
- 首次加载数据后会缓存到内存
- 切换周期时会重用已加载的数据

## 数据验证

### 验证 A 股数据

```bash
backend/.venv/bin/python -c "
from app.db import get_daily_history, get_daily_count
symbols = ['000001', '000300', '399001', '399006']
for sym in symbols:
    cnt = get_daily_count(sym)
    print(f'{sym}: {cnt} rows')
    if cnt > 0:
        rows = get_daily_history(sym, limit=3)
        print(f'  Latest: {[r[\"date\"] for r in rows]}')
"
```

### 验证美股数据

```bash
backend/.venv/bin/python -c "
from app.db import get_daily_history, get_daily_count
symbols = ['ixic', 'ndx', 'spx', 'dji']
for sym in symbols:
    cnt = get_daily_count(sym)
    print(f'{sym}: {cnt} rows')
    if cnt > 0:
        rows = get_daily_history(sym, limit=3)
        print(f'  Latest: {[r[\"date\"] for r in rows]}')
"
```

## 下一步计划

1. **短期**：
   - 配置 Alpha Vantage API Key 并测试数据拉取
   - 验证数据准确性
   - 更新前端 K 线图显示

2. **中期**：
   - 集成更多数据源（如 Bloomberg、Reuters）
   - 实现数据自动更新定时任务
   - 优化数据查询性能

3. **长期**：
   - 建立数据质量监控系统
   - 实现多数据源交叉验证
   - 支持更多全球市场数据

## 联系支持

如有问题或建议，请：
1. 提交 GitHub Issue：https://github.com/deancyl/AlphaTerminal/issues
2. 加入 Discord 社区：https://discord.com/invite/clawd
3. 查看项目文档：https://docs.openclaw.ai

---

**最后更新**：2026-04-04
**版本**：v0.3.2
