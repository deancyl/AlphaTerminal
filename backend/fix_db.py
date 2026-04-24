#!/usr/bin/env python3
"""
fix_db.py — 数据库迁移修复脚本 (Phase 6.7)

修复内容:
1. portfolios 表添加缺失的 7 个字段
2. 创建 backtest_strategies 和 backtest_results 表
"""
import sqlite3
import sys

DB_PATH = "/vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal/database.db"

def fix_portfolios_table(conn):
    """修复 portfolios 表缺失字段"""
    cursor = conn.cursor()
    
    # 检查现有列
    cursor.execute("PRAGMA table_info(portfolios)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    print(f"现有 portfolios 列：{existing_cols}")
    
    # 需要添加的列
    new_cols = [
        ("currency", "TEXT DEFAULT 'CNY'"),
        ("asset_class", "TEXT DEFAULT 'mixed'"),
        ("strategy", "TEXT DEFAULT ''"),
        ("benchmark", "TEXT DEFAULT '000300'"),
        ("status", "TEXT DEFAULT 'active'"),
        ("initial_capital", "REAL DEFAULT 0"),
        ("description", "TEXT DEFAULT ''"),
    ]
    
    added = 0
    for col_name, col_def in new_cols:
        if col_name not in existing_cols:
            sql = f"ALTER TABLE portfolios ADD COLUMN {col_name} {col_def}"
            try:
                cursor.execute(sql)
                print(f"✅ ALTER TABLE portfolios ADD {col_name}")
                added += 1
            except sqlite3.OperationalError as e:
                print(f"⚠️  {col_name} 可能已存在：{e}")
    
    conn.commit()
    print(f"portfolios 表修复完成，新增 {added} 列")
    return added

def create_backtest_tables(conn):
    """创建回测相关表"""
    cursor = conn.cursor()
    
    # backtest_strategies 表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS backtest_strategies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        params TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    print("✅ CREATE TABLE backtest_strategies")
    
    # backtest_results 表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS backtest_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        strategy_id INTEGER,
        portfolio_id INTEGER,
        start_date TEXT,
        end_date TEXT,
        initial_capital REAL,
        final_capital REAL,
        total_return REAL,
        annual_return REAL,
        sharpe_ratio REAL,
        max_drawdown REAL,
        win_rate REAL,
        trades_count INTEGER,
        details TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (strategy_id) REFERENCES backtest_strategies(id),
        FOREIGN KEY (portfolio_id) REFERENCES portfolios(id)
    )
    """)
    print("✅ CREATE TABLE backtest_results")
    
    conn.commit()
    print("回测表创建完成")

def verify_fix(conn):
    """验证修复结果"""
    cursor = conn.cursor()
    
    print("\n=== 验证 portfolios 表结构 ===")
    cursor.execute("PRAGMA table_info(portfolios)")
    cols = [row[1] for row in cursor.fetchall()]
    print(f"列数：{len(cols)}")
    print(f"列名：{cols}")
    
    print("\n=== 验证 backtest 表 ===")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'backtest%'")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"回测相关表：{tables}")
    
    print("\n=== 验证 portfolios 数据 ===")
    cursor.execute("SELECT COUNT(*) FROM portfolios")
    count = cursor.fetchone()[0]
    print(f"现有投资组合数：{count}")

if __name__ == "__main__":
    print("=" * 60)
    print("Phase 6.7: 数据库迁移修复脚本")
    print("=" * 60)
    
    try:
        conn = sqlite3.connect(DB_PATH)
        print(f"✅ 数据库连接成功：{DB_PATH}")
        
        # 执行修复
        fix_portfolios_table(conn)
        create_backtest_tables(conn)
        
        # 验证
        verify_fix(conn)
        
        conn.close()
        print("\n✅ 数据库迁移修复完成！")
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ 修复失败：{type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
