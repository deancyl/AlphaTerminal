#!/usr/bin/env python3
"""
A 股数据迁移脚本
从 /tmp/alpha_ultimate_active.db 迁移 A 股历史数据到 workspace/database.db
"""
import sqlite3
import os
import sys
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 数据库路径
SOURCE_DB = '/tmp/alpha_ultimate_active.db'
TARGET_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database.db')

# 要迁移的标的（A 股指数）
A_SHARE_SYMBOLS = ['000001', '000300', '399001', '399006']

def migrate_data():
    """迁移 A 股数据"""
    if not os.path.exists(SOURCE_DB):
        print(f"错误：源数据库不存在: {SOURCE_DB}")
        return False

    if not os.path.exists(TARGET_DB):
        print(f"错误：目标数据库不存在: {TARGET_DB}")
        print("请先运行 scripts/init_database.py 初始化数据库")
        return False

    # 连接数据库
    source_conn = sqlite3.connect(SOURCE_DB)
    target_conn = sqlite3.connect(TARGET_DB)

    source_cursor = source_conn.cursor()
    target_cursor = target_conn.cursor()

    try:
        print("="*60)
        print("A 股数据迁移")
        print("="*60)
        print(f"源数据库: {SOURCE_DB}")
        print(f"目标数据库: {TARGET_DB}")
        print("="*60)

        total_migrated = 0

        for symbol in A_SHARE_SYMBOLS:
            print(f"\n处理 {symbol}...")

            # 检查源数据库中的数据
            source_cursor.execute(f'SELECT COUNT(*) FROM market_data_daily WHERE symbol="{symbol}"')
            source_count = source_cursor.fetchone()[0]

            if source_count == 0:
                print(f"  源数据库中无数据，跳过")
                continue

            # 检查目标数据库中的数据
            target_cursor.execute(f'SELECT COUNT(*) FROM market_data_daily WHERE symbol="{symbol}"')
            target_count = target_cursor.fetchone()[0]

            if target_count > 0:
                print(f"  目标数据库中已有 {target_count} 条记录，跳过")
                continue

            # 从源数据库读取数据
            source_cursor.execute(f'''
                SELECT symbol, date, open, high, low, close, volume, timestamp, data_type
                FROM market_data_daily
                WHERE symbol="{symbol}"
                ORDER BY date
            ''')

            rows = source_cursor.fetchall()

            if not rows:
                print(f"  无法读取数据")
                continue

            # 写入目标数据库
            for row in rows:
                target_cursor.execute(f'''
                    INSERT INTO market_data_daily (symbol, date, open, high, low, close, volume, timestamp, data_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', row)

            target_conn.commit()
            total_migrated += len(rows)

            # 获取日期范围
            dates = [row[1] for row in rows]
            print(f"  迁移 {len(rows)} 条记录")
            print(f"  日期范围: {dates[0]} ~ {dates[-1]}")

        print("\n" + "="*60)
        print(f"迁移完成: 总共 {total_migrated} 条记录")
        print("="*60)

        # 验证迁移结果
        print("\n验证结果:")
        for symbol in A_SHARE_SYMBOLS:
            target_cursor.execute(f'SELECT COUNT(*) FROM market_data_daily WHERE symbol="{symbol}"')
            count = target_cursor.fetchone()[0]
            print(f"  {symbol}: {count} rows")

        return True

    except Exception as e:
        print(f"迁移失败: {e}")
        target_conn.rollback()
        return False
    finally:
        source_conn.close()
        target_conn.close()

if __name__ == "__main__":
    success = migrate_data()
    sys.exit(0 if success else 1)
