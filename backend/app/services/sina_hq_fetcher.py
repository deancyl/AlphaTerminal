"""
Sina HQ 行情抓取器 v2 - Phase 3
数据源：腾讯/QQ行情 qt.gtimg.cn（绕过 Sina 直接限制）
批量接口：每次最多50个股票代码，单次<500ms
"""
import logging
import subprocess
import time as time_module
from datetime import datetime
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── 重点关注股票池（50只，覆盖各行业龙头）─────────────────────────────
FOCUS_STOCKS = [
    # 白酒/消费
    "sh600519", "sz000858", "sh600887", "sz002304", "sh603288",
    # 银行
    "sh601318", "sh600036", "sh601166", "sh600000", "sh601398",
    # 保险/券商
    "sh601628", "sh600030", "sh601688", "sz000776", "sh601211",
    # 科技/新能源
    "sz000001", "sh600585", "sz002594", "sh600256", "sh600089",
    "sz300750", "sh688981", "sz300760", "sz002475",
    # 医药
    "sh600276", "sz000538", "sh600196", "sz300015", "sh603259",
    # 互联网
    "sh601888", "sz000063", "sh600050", "sh600588",
    # 地产/建筑
    "sh601668", "sh600048", "sz000002", "sh601800",
    # 电力/公用
    "sh600900", "sh600028", "sh600900",
    # 其他龙头
    "sh601899", "sh600031", "sh601012", "sh600150",
    "sz000100", "sh600690",
]


def fetch_hq_batch(codes: list[str]) -> list[dict]:
    """
    批量获取股票实时行情（腾讯 qt.gtimg.cn）
    codes: ["sh600519", "sz000858", ...]
    返回: [{"code", "name", "price", "yesterday_close", "open", "volume", "chg_pct", "market"}, ...]
    """
    if not codes:
        return []

    batch_size = 45
    all_rows = []

    for i in range(0, len(codes), batch_size):
        batch = codes[i:i + batch_size]
        joined = ",".join(batch)
        try:
            raw = subprocess.check_output(
                ["curl", "-s", "--max-time", "8", "--noproxy", "*",
                 f"https://qt.gtimg.cn/q={joined}",
                 "-H", "Referer: https://gu.qq.com",
                 "-H", "User-Agent: Mozilla/5.0"],
                stderr=subprocess.DEVNULL,
            )
            text = raw.decode("gbk", errors="replace")
            for line in text.strip().split("\n"):
                if "v_" not in line or "=" not in line:
                    continue
                try:
                    # 格式: v_sh600519="1~贵州茅台~1450.00~1451.00~1449.50~...
                    inner = line.split("=")[1].strip().strip('"')
                    parts = inner.split("~")
                    if len(parts) < 40:
                        continue

                    raw_code = parts[0].strip()
                    name     = parts[1].strip()
                    price    = float(parts[3]) if parts[3] else 0.0
                    y_close  = float(parts[4]) if parts[4] else price
                    open_p   = float(parts[5]) if parts[5] else price
                    volume   = float(parts[6]) if parts[6] else 0.0
                    chg_pct  = float(parts[32]) if parts[32] else 0.0
                    chg_val  = round(price - y_close, 2) if y_close else 0.0

                    # 换手率: parts[38] or 计算
                    turnover = float(parts[38]) if (len(parts) > 38 and parts[38]) else 0.0

                    # 判断市场
                    if raw_code.startswith("sh"):
                        market = "SH"
                        code = raw_code[2:]
                    elif raw_code.startswith("sz"):
                        market = "SZ"
                        code = raw_code[2:]
                    elif raw_code.startswith("hk"):
                        market = "HK"
                        code = raw_code[2:]
                    else:
                        market = "?"
                        code = raw_code

                    if not name or price <= 0:
                        continue

                    all_rows.append({
                        "code":         code,
                        "name":         name,
                        "price":        round(price, 2),
                        "yesterday":    round(y_close, 2),
                        "open":         round(open_p, 2),
                        "volume":       round(volume, 0),
                        "chg":          chg_val,
                        "chg_pct":      round(chg_pct, 2),
                        "turnover":     round(turnover, 2),
                        "market":       market,
                        "timestamp":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    })
                except (ValueError, IndexError):
                    continue

            time_module.sleep(0.12)  # 礼貌延迟

        except Exception as e:
            logger.warning(f"[SinaHQ] batch fetch failed: {e}")
            continue

    logger.info(f"[SinaHQ] fetched {len(all_rows)} stocks")
    return all_rows


def build_histogram_from_rows(rows: list[dict]) -> dict:
    """
    基于股票实时数据构建涨跌分布直方图（11桶）
    """
    BUCKET_THRESHOLDS = [
        ("跌停",      -1e9,  -9.9),
        ("<-7%",     -9.9,   -7.0),
        ("-7%~-5%",  -7.0,   -5.0),
        ("-5%~-2%",  -5.0,   -2.0),
        ("-2%~0%",   -2.0,    0.0),
        ("平盘(0%)",   0.0,    0.0),
        ("0%~2%",     0.0,    2.0),
        ("2%~5%",     2.0,    5.0),
        ("5%~7%",     5.0,    7.0),
        (">7%",       7.0,    9.9),
        ("涨停",       9.9,  1e9),
    ]

    if not rows:
        return {"buckets": [], "total": 0, "advance": 0, "decline": 0,
                "unchanged": 0, "limit_up": 0, "limit_down": 0,
                "up_ratio": 0.0, "timestamp": ""}

    pcts = np.array([r["chg_pct"] for r in rows], dtype=float)
    total     = len(rows)
    advance   = int((pcts > 0).sum())
    decline   = int((pcts < 0).sum())
    unchanged = int((pcts == 0).sum())
    limit_up   = int((pcts >= 9.9).sum())
    limit_down = int((pcts <= -9.9).sum())

    buckets = []
    for label, lo, hi in BUCKET_THRESHOLDS:
        if label == "平盘(0%)":
            count = int((pcts == 0.0).sum())
        else:
            count = int(((pcts > lo) & (pcts <= hi)).sum())
        color = "#14b143" if lo < 0 else "#ef232a" if lo >= 0 else "#6b7280"
        buckets.append({
            "label": label,
            "count": count,
            "pct":   round(count / total * 100, 2) if total > 0 else 0,
            "color": color,
        })

    ts = rows[0]["timestamp"] if rows else ""
    return {
        "buckets":    buckets,
        "total":      total,
        "advance":    advance,
        "decline":    decline,
        "unchanged":  unchanged,
        "limit_up":   limit_up,
        "limit_down": limit_down,
        "up_ratio":   round(advance / total, 4) if total > 0 else 0,
        "timestamp":  ts,
    }
