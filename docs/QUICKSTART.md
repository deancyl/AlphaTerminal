# 历史数据快速开始指南

## 问题诊断

当前 AlphaTerminal 的数据状态：
- ✅ **已有完整历史**：上证 (000001, 8614条)、沪深300 (000300, 5881条)、深证成指 (399001, 8522条)、创业板指 (399006, 3846条)
- ❌ **数据缺失**：美股指数 (IXIC/NDX/SPX/DJI)、港股 (HSI)、商品 (GOLD/WTI/VIX) 只有 1 天数据

## 解决步骤（3 步完成）

### 第一步：获取 API Key

1. 访问：https://www.alphavantage.co/support/#api-key
2. 注册免费账户
3. 复制 API Key（类似：`ABC123XYZ`）

### 第二步：运行数据拉取脚本

```bash
# 1. 设置 API Key
export ALPHA_VANTAGE_API_KEY=your_api_key_here

# 2. 运行脚本（自动拉取 11 个标的的历史数据）
cd /vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal
backend/.venv/bin/python scripts/fetch_historical_data.py

# 3. 验证数据（检查每个标的的数据量）
backend/.venv/bin/python -c "
from app.db import get_daily_count
symbols = ['ixic', 'ndx', 'spx', 'dji', 'hsi', 'glg', 'wti', 'vix']
for sym in symbols:
    print(f'{sym}: {get_daily_count(sym)} rows')
"
```

**预期结果**：
- ixic: ~5000+ rows（纳斯达克综合指数，~20年历史）
- ndx: ~5000+ rows（纳斯达克100，~20年历史）
- spx: ~5000+ rows（标普500，~20年历史）
- dji: ~5000+ rows（道琼斯，~20年历史）
- hsi: ~5000+ rows（恒生指数，~20年历史）
- glg: ~5000+ rows（黄金，~20年历史）
- wti: ~5000+ rows（原油，~20年历史）
- vix: ~1000+ rows（波动率指数，~5年历史）

### 第三步：验证并重启

```bash
# 1. 重启后端（如果需要）
pkill -f "uvicorn app.main:app"
cd backend
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8002

# 2. 打开前端浏览器，检查 K 线图是否显示历史数据
# 访问：http://localhost:60100
# 点击：纳斯达克 (IXIC)、标普500 (SPX)、恒生 (HSI)、黄金 (GLD)
```

## 常见问题

### Q1：脚本运行失败，提示 "API 限制"

**A**：Alpha Vantage 免费版每天 25 次请求，每分钟 5 次请求。
- 如果达到限制，请等待第二天再拉取
- 或者升级到付费版（$0.01/请求）

### Q2：网络连接失败

**A**：Alpha Vantage 是国际网站，需要代理访问。
```bash
# 已在 .env 文件中配置代理（使用你提供的 7897 端口）
export HTTP_PROXY=http://192.168.1.50:7897
export HTTPS_PROXY=http://192.168.1.50:7897
```

### Q3：数据仍然只有 1 天

**A**：检查以下几点：
1. 确认脚本执行成功（查看输出中的 "[SUCCESS]" 标记）
2. 确认数据库中已有数据（运行上述验证命令）
3. 重启后端服务
4. 清除浏览器缓存并刷新页面

### Q4：VIX 和 CNH 没有数据

**A**：Alpha Vantage 不支持 VIX 和 CNH 的历史数据。
- VIX：需要寻找其他数据源（如 CBOE）
- CNH：离岸人民币汇率数据暂时无法获取

## 技术细节

### 数据流程

```
Alpha Vantage API → SQLite 数据库 → 后端 API → 前端 K 线图
```

### 支持的标的

**美股指数**：IXIC, NDX, SPX, DJI
**港股指数**：HSI
**商品**：GLD (黄金), WTI (原油), VIX (波动率), DXY (美元指数)

### 数据库位置

```
/tmp/alpha_ultimate_active.db
```

### 脚本位置

```
AlphaTerminal/scripts/fetch_historical_data.py
```

## 进阶功能

### 定时自动更新

使用 cron 每天自动更新数据：
```bash
# 编辑 crontab
crontab -e

# 添加定时任务（每天 18:00 更新）
0 18 * * 1-5 cd /vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal && backend/.venv/bin/python scripts/fetch_historical_data.py >> /tmp/data_update.log 2>&1
```

### 重新拉取数据

如果需要重新拉取某个标的的数据：
```bash
# 1. 清除该标的的现有数据
backend/.venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('/tmp/alpha_ultimate_active.db')
cursor = conn.cursor()
cursor.execute('DELETE FROM market_data_daily WHERE symbol=?', ('ixic',))
conn.commit()
conn.close()
print('已清除 ixic 数据')
"

# 2. 重新运行脚本
backend/.venv/bin/python scripts/fetch_historical_data.py
```

## 获取帮助

- 📖 完整文档：`docs/HISTORICAL_DATA_GUIDE.md`
- 🐛 提交 Issue：https://github.com/deancyl/AlphaTerminal/issues
- 💬 Discord 社区：https://discord.com/invite/clawd

---

**预计完成时间**：5-10 分钟（注册 + 拉取）
**预计数据量**：~50,000 条历史记录（11 个标的 × ~5,000 条）
