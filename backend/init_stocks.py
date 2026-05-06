#!/usr/bin/env python3
"""
全量A股股票数据初始化脚本
用法: python init_stocks.py
一次性获取全量A股实时行情并写入realtime_spot表
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import sqlite3
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'database.db')

# Symbol 前缀映射（akshare 返回的是纯数字代码）
PREFIX_MAP = {
    '6': 'sh',   # 上证
    '0': 'sz',   # 深证主板
    '3': 'sz',   # 创业板
    '8': 'bj',   # 北交所
}


def norm_sym(code: str) -> str:
    """将 akshare 返回的纯数字代码转换为标准前缀格式"""
    if not code or len(code) < 1:
        return code
    prefix = PREFIX_MAP.get(code[0], 'sh')
    return f'{prefix}{code}'


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA busy_timeout = 10000')
    return conn


def init_schema(conn):
    """确保表存在"""
    conn.execute('''
        CREATE TABLE IF NOT EXISTS realtime_spot (
            symbol TEXT PRIMARY KEY,
            name TEXT,
            price REAL,
            change_pct REAL,
            volume REAL,
            amount REAL,
            amplitude REAL,
            high REAL,
            low REAL,
            open REAL,
            prev_close REAL,
            update_time INTEGER,
            pe REAL,
            pb REAL,
            market_cap REAL,
            float_market_cap REAL,
            sector TEXT,
            change_abs REAL
        )
    ''')
    conn.commit()
    logger.info('Schema ready')


def fetch_all_stocks() -> list[dict]:
    """使用 akshare 获取全量 A 股实时行情"""
    import akshare as ak

    logger.info('正在获取全量A股列表...')
    df = ak.stock_zh_a_spot_em()

    rows = []
    for _, row in df.iterrows():
        code = str(row.get('代码', ''))
        if not code:
            continue
        sym = norm_sym(code)
        rows.append({
            'symbol': sym,
            'name': str(row.get('名称', '')),
            'price': float(row['最新价']) if row.get('最新价') not in (None, '-', '') else 0,
            'change_pct': float(row['涨跌幅']) if row.get('涨跌幅') not in (None, '-', '') else 0,
            'change_abs': float(row['涨跌额']) if row.get('涨跌额') not in (None, '-', '') else 0,
            'volume': float(row['成交量']) if row.get('成交量') not in (None, '-', '') else 0,
            'amount': float(row['成交额']) if row.get('成交额') not in (None, '-', '') else 0,
            'amplitude': float(row['振幅']) if row.get('振幅') not in (None, '-', '') else 0,
            'high': float(row['最高']) if row.get('最高') not in (None, '-', '') else 0,
            'low': float(row['最低']) if row.get('最低') not in (None, '-', '') else 0,
            'open': float(row['今开']) if row.get('今开') not in (None, '-', '') else 0,
            'prev_close': float(row['昨收']) if row.get('昨收') not in (None, '-', '') else 0,
            'update_time': int(time.time()),
            'pe': float(row['市盈率-动态']) if row.get('市盈率-动态') not in (None, '-', '') else None,
            'pb': float(row['市净率']) if row.get('市净率') not in (None, '-', '') else None,
            'market_cap': float(row['总市值']) if row.get('总市值') not in (None, '-', '') else None,
            'float_market_cap': float(row['流通市值']) if row.get('流通市值') not in (None, '-', '') else None,
        })

    return rows


def write_to_db(rows: list[dict], conn: sqlite3.Connection):
    """写入 realtime_spot 表"""
    upsert = '''
        INSERT INTO realtime_spot
            (symbol, name, price, change_pct, change_abs, volume, amount, amplitude,
             high, low, open, prev_close, update_time, pe, pb, market_cap, float_market_cap)
        VALUES
            (:symbol, :name, :price, :change_pct, :change_abs, :volume, :amount, :amplitude,
             :high, :low, :open, :prev_close, :update_time, :pe, :pb, :market_cap, :float_market_cap)
        ON CONFLICT(symbol) DO UPDATE SET
            name=excluded.name,
            price=excluded.price,
            change_pct=excluded.change_pct,
            change_abs=excluded.change_abs,
            volume=excluded.volume,
            amount=excluded.amount,
            update_time=excluded.update_time
    '''
    conn.execute('DELETE FROM realtime_spot')
    conn.executemany(upsert, rows)
    conn.commit()
    logger.info(f'写入 {len(rows)} 条记录到 realtime_spot')


def main():
    logger.info('=' * 50)
    logger.info('AlphaTerminal A股全量数据初始化开始')
    logger.info('=' * 50)

    conn = get_db()
    init_schema(conn)

    try:
        rows = fetch_all_stocks()
        write_to_db(rows, conn)
        logger.info(f'初始化完成: {len(rows)} 只股票')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
