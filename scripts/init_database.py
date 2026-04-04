#!/usr/bin/env python3
"""
数据库初始化脚本
创建 market_data_daily 表
"""
import sqlite3
import sys
import os
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 数据库路径（使用绝对路径）
DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database.db')

def create_tables():
    """创建必要的数据库表"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        # 创建市场数据表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS market_data_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume INTEGER NOT NULL,
            timestamp INTEGER NOT NULL,
            data_type TEXT NOT NULL DEFAULT 'daily',
            UNIQUE(symbol, date)
        )
        ''')

        # 创建索引
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_market_data_daily_symbol_date
        ON market_data_daily(symbol, date)
        ''')

        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_market_data_daily_symbol
        ON market_data_daily(symbol)
        ''')

        conn.commit()
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 数据库表创建成功: {DB_FILE}")

    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 数据库表创建失败: {e}")
        sys.exit(1)
    finally:
        conn.close()
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 数据库初始化完成")

if __name__ == "__main__":
    create_tables()
