#!/usr/bin/env python3
"""
抓取美股/港股/商品历史数据脚本
使用 Alpha Vantage API 获取历史数据并存储到数据库
"""
import os
import sys
import requests
import time
from datetime import datetime, timedelta
import sqlite3

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 数据库路径
DB_PATH = '/tmp/alpha_ultimate_active.db'

# Alpha Vantage API 配置
API_KEY = os.environ.get('ALPHA_VANTAGE_API_KEY')
BASE_URL = 'https://www.alphavantage.co/query'

# 代理设置
PROXIES = {
    'http': os.environ.get('HTTP_PROXY', 'http://192.168.1.50:7897'),
    'https': os.environ.get('HTTPS_PROXY', 'http://192.168.1.50:7897'),
}

# Alpha Vantage API 调用限制：每分钟最多 5 次请求，每天最多 25 次请求
API_CALL_DELAY = 13  # 秒，确保不超过每分钟 5 次请求

def fetch_from_alpha_vantage(symbol, function='TIME_SERIES_DAILY'):
    """从 Alpha Vantage API 获取历史数据"""
    if not API_KEY:
        print(f"[ERROR] 未设置 ALPHA_VANTAGE_API_KEY 环境变量")
        return None

    params = {
        'function': function,
        'symbol': symbol,
        'outputsize': 'full',
        'apikey': API_KEY,
        'datatype': 'json',
    }

    try:
        print(f"[Alpha Vantage] 正在拉取 {symbol}...")
        response = requests.get(BASE_URL, params=params, proxies=PROXIES, timeout=30)
        response.raise_for_status()
        data = response.json()

        # 检查 API 错误
        if 'Error Message' in data:
            print(f"[Alpha Vantage] {symbol} API 错误: {data['Error Message']}")
            return None
        if 'Note' in data:
            print(f"[Alpha Vantage] {symbol} API 限制: {data['Note']}")
            return None

        # 提取时间序列数据
        if function == 'TIME_SERIES_DAILY':
            time_series = data.get('Time Series (Daily)', {})
        elif function == 'TIME_SERIES_WEEKLY':
            time_series = data.get('Weekly Time Series', {})
        elif function == 'TIME_SERIES_MONTHLY':
            time_series = data.get('Monthly Time Series', {})
        else:
            print(f"[Alpha Vantage] 不支持的 function: {function}")
            return None

        # 转换为标准格式
        rows = []
        for date_str, values in time_series.items():
            row = {
                'symbol': symbol.lower(),
                'date': date_str,
                'open': float(values.get('1. open', 0)),
                'high': float(values.get('2. high', 0)),
                'low': float(values.get('3. low', 0)),
                'close': float(values.get('4. close', 0)),
                'volume': int(values.get('5. volume', 0)),
                'change_pct': 0.0,  # Alpha Vantage 不提供 change_pct
                'timestamp': int(datetime.strptime(date_str, '%Y-%m-%d').timestamp()),
                'data_type': 'daily',
            }
            rows.append(row)

        print(f"[Alpha Vantage] {symbol} 成功获取 {len(rows)} 条记录")
        return rows

    except requests.exceptions.RequestException as e:
        print(f"[Alpha Vantage] {symbol} 网络错误: {e}")
        return None
    except Exception as e:
        print(f"[Alpha Vantage] {symbol} 未知错误: {e}")
        return None

def store_to_database(rows, table='market_data_daily'):
    """将数据存储到数据库"""
    if not rows:
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 批量插入（使用 INSERT OR REPLACE 避免重复）
        for row in rows:
            cursor.execute(f'''
                INSERT OR REPLACE INTO {table}
                (symbol, date, open, high, low, close, volume, change_pct, timestamp, data_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                row['symbol'],
                row['date'],
                row['open'],
                row['high'],
                row['low'],
                row['close'],
                row['volume'],
                row['change_pct'],
                row['timestamp'],
                row['data_type'],
            ))

        conn.commit()
        print(f"[DB] 成功写入 {len(rows)} 条记录")
        return True

    except Exception as e:
        print(f"[DB] 写入失败: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_symbols_to_fetch():
    """获取需要拉取历史数据的标的列表"""
    # Alpha Vantage 支持的美股/港股/商品代码
    symbols = {
        'IXIC': 'NASDAQ Composite',  # 纳斯达克
        'NDX': 'NASDAQ 100',  # 纳斯达克 100
        'SPX': 'S&P 500',  # 标普 500
        'DJI': 'Dow Jones',  # 道琼斯
        'HSI': 'Hang Seng',  # 恒生指数
        'N225': 'Nikkei 225',  # 日经 225
        'GLD': 'Gold',  # 黄金
        'GDX': 'Gold Miners',  # 黄金矿业
        'USO': 'Crude Oil',  # 原油
        'VIX': 'VIX Index',  # 波动率指数
        'DXY': 'US Dollar Index',  # 美元指数
    }
    return symbols

def check_existing_data(symbol):
    """检查数据库中是否已有该标的的数据"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute(
            'SELECT COUNT(*) as cnt FROM market_data_daily WHERE symbol=?',
            (symbol.lower(),)
        )
        row = cursor.fetchone()
        return row[0] if row else 0
    finally:
        conn.close()

def main():
    """主函数"""
    if not API_KEY:
        print("[ERROR] 未设置 ALPHA_VANTAGE_API_KEY 环境变量")
        print("获取 API Key：https://www.alphavantage.co/support/#api-key")
        print("设置方式：export ALPHA_VANTAGE_API_KEY=your_api_key_here")
        sys.exit(1)

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始抓取历史数据...")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 使用 Alpha Vantage API Key: {API_KEY[:10]}...")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 代理: {PROXIES['http']}")

    # 获取需要拉取的标的
    symbols_to_fetch = get_symbols_to_fetch()

    total_symbols = len(symbols_to_fetch)
    success_count = 0
    fail_count = 0

    for i, (symbol, description) in enumerate(symbols_to_fetch.items(), 1):
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{i}/{total_symbols}] 处理 {symbol} ({description})...")

        # 检查是否已有数据
        existing_count = check_existing_data(symbol)
        if existing_count > 1:  # 超过 1 条说明有历史数据
            print(f"[INFO] {symbol} 已有 {existing_count} 条数据，跳过拉取")
            continue

        # 拉取数据
        rows = fetch_from_alpha_vantage(symbol)

        if rows:
            # 存储到数据库
            if store_to_database(rows):
                success_count += 1
                print(f"[SUCCESS] {symbol} 成功获取并存储 {len(rows)} 条历史数据")
            else:
                fail_count += 1
                print(f"[FAIL] {symbol} 存储失败")
        else:
            fail_count += 1
            print(f"[FAIL] {symbol} 拉取失败")

        # Alpha Vantage API 限制：每分钟最多 5 次请求
        if i < total_symbols:
            print(f"[INFO] 等待 {API_CALL_DELAY} 秒以避免 API 限制...")
            time.sleep(API_CALL_DELAY)

    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 数据抓取完成")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 成功: {success_count}, 失败: {fail_count}, 跳过: {total_symbols - success_count - fail_count}")

if __name__ == "__main__":
    main()
