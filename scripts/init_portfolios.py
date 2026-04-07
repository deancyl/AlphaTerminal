#!/usr/bin/env python3
"""
P3 多账户体系初始化脚本
运行一次即可，创建"主账户"和"涵涵专项账户"

用法: python scripts/init_portfolios.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))

from datetime import datetime
from app.db.database import _get_conn

def init():
    # 确保所有表已创建（幂等）
    from app.db.database import init_tables
    init_tables()
    print("[OK] 数据库表初始化完成")

    accounts = [
        {"name": "主账户",       "type": "main"},
        {"name": "子账户", "type": "special_plan"},
    ]

    now = datetime.now().isoformat()
    conn = _get_conn()

    for acc in accounts:
        try:
            cur = conn.execute(
                "INSERT INTO portfolios (name, type, created_at) VALUES (?,?,?)",
                (acc["name"], acc["type"], now)
            )
            conn.commit()
            print(f"[OK] 创建账户: {acc['name']} (id={cur.lastrowid})")
        except Exception as e:
            rows = conn.execute(
                "SELECT id FROM portfolios WHERE name=?", (acc["name"],)
            ).fetchall()
            if rows:
                print(f"[SKIP] 账户已存在: {acc['name']} (id={rows[0][0]})")
            else:
                print(f"[WARN] {acc['name']} 创建失败: {e}")

    rows = conn.execute(
        "SELECT id, name, type, created_at FROM portfolios ORDER BY id"
    ).fetchall()
    conn.close()

    print(f"\n[完成] 当前账户列表 ({len(rows)} 个):")
    for r in rows:
        print(f"  id={r[0]}  name={r[1]}  type={r[2]}  created={r[3]}")

if __name__ == "__main__":
    init()
