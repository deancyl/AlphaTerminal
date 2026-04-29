#!/usr/bin/env python3
"""
Alpha Vantage 配置指南和数据抓取工具

使用说明：
1. 注册 Alpha Vantage 账户并获取 API Key: https://www.alphavantage.co/support/#api-key
2. 设置环境变量: export ALPHA_VANTAGE_API_KEY=your_key_here
3. 运行脚本: python scripts/fetch_alpha_vantage.py

Alpha Vantage 免费账户限制：
- 每天 25 次 API 请求
- 每次请求最多返回 20 年历史数据
- 需要等待 12 秒后才能再次请求（速率限制）

建议抓取策略：
1. 先抓取最重要的指数（纳斯达克、标普500、恒生等）
2. 使用一次性脚本全部抓取
3. 之后每天只增量更新最新数据
"""
