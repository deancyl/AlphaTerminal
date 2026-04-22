#!/usr/bin/env python3
"""
direct_kline_fetcher.py
直接调用腾讯/新浪/东方财富 API 获取 A 股指数 K 线历史数据（直连，不走代理）
"""
import os, sys, json, sqlite3, re
from datetime import datetime, timedelta
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database.db')

# ── 指数代码映射 ────────────────────────────────────────────────────
INDEX_CODES = {
    'sh000001': 'sh000001',   # 上证指数
    'sh000300': 'sh000300',   # 沪深300
    'sz399001': 'sz399001',   # 深证成指
    'sz399006': 'sz399006',   # 创业板指
    'sh000688': 'sh000688',   # 科创50
    'sh000016': 'sh000016',   # 上证50
    'sh000905': 'sh000905',   # 中证500
    'sz399005': 'sz399005',   # 中证1000
    # 港股
    'hkHSI':   'hkHSI',       # 恒生指数
    # 美股（备用）
    'usNDX':   'usNDX',
    'usSPX':   'usSPX',
    'usDJI':   'usDJI',
}

# ── 腾讯 K 线接口（A股日K，支持qfq复权）──────────────────────────────
TENCENT_KLINE_URL = (
    "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    "?_var=kline_dayqfq&param={symbol},day,,,{limit},qfq"
)

# ── 新浪 K 线接口（备用）────────────────────────────────────────────
SINA_KLINE_URL = (
    "https://finance.sina.com.cn/realstock/company/{symbol}/nc.shtml"
    # 新浪日K线需要用 hq_str 接口
)

TENCENT_HIST_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"


def fetch_tencent_kline(symbol: str, limit: int = 300) -> Optional[list]:
    """
    腾讯财经 A 股日 K 线（直连，不走代理）
    返回: [{date, open, close, high, low, volume}, ...]
    """
    try:
        import requests
        url = TENCENT_HIST_URL
        params = {
            '_var': 'kline_dayqfq',
            'param': f'{symbol},day,,,{limit},qfq',
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        text = resp.text
        # 解析: kline_dayqfq={json}
        m = re.search(r'=\s*(\{.*\})', text, re.DOTALL)
        if not m:
            return None
        raw = json.loads(m.group(1))
        data = raw.get('data', {}).get(symbol, {}).get('day', [])
        if not data:
            return None
        # data 格式: ["date", "open", "close", "high", "low", "volume"]
        records = []
        for item in data:
            if len(item) < 6:
                continue
            try:
                records.append({
                    'date':   item[0],
                    'open':   float(item[1]),
                    'close':  float(item[2]),
                    'high':   float(item[3]),
                    'low':    float(item[4]),
                    'volume': float(item[5]),
                })
            except (ValueError, IndexError):
                continue
        return records
    except Exception as e:
        print(f"[Tencent] {symbol} 失败: {e}")
        return None


def store_klines(symbol: str, klines: list) -> int:
    """写入 market_data_daily，返回写入条数"""
    if not klines:
        return 0
    conn = sqlite3.connect(DB_FILE)
    count = 0
    for k in klines:
        try:
            conn.execute("""
                INSERT OR REPLACE INTO market_data_daily
                (symbol, date, open, high, low, close, volume, timestamp, data_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'daily')
            """, (
                symbol,
                k['date'],
                k['open'],
                k['high'],
                k['low'],
                k['close'],
                int(k['volume']),
                int(datetime.strptime(k['date'], '%Y-%m-%d').timestamp()),
            ))
            count += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    return count


def main():
    symbols = list(INDEX_CODES.keys())
    print(f"开始抓取 {len(symbols)} 个指数 K 线数据（直连腾讯财经）...")
    total = 0
    for sym in symbols:
        print(f"\n{'='*50}")
        print(f"处理: {sym}")
        print(f"{'='*50}")
        klines = fetch_tencent_kline(sym, limit=300)
        if klines:
            n = store_klines(sym, klines)
            print(f"[OK] {sym}: 写入 {n} 条 ({klines[0]['date']} ~ {klines[-1]['date']})")
            total += n
        else:
            print(f"[FAIL] {sym}: 无数据")
    print(f"\n总计写入: {total} 条 K 线记录")


if __name__ == '__main__':
    main()
