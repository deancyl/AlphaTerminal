#!/usr/bin/env python3
"""Quick health check for AlphaTerminal."""

import json
import sys
import os
from datetime import datetime

def main():
    results = {
        "timestamp": datetime.now().isoformat(),
        "checks": []
    }
    
    # Check 1: Backend health
    try:
        import httpx
        resp = httpx.get("http://localhost:8002/health", timeout=5)
        results["checks"].append({
            "name": "backend_health",
            "status": "pass" if resp.status_code == 200 else "fail",
            "message": f"Status: {resp.status_code}"
        })
    except Exception as e:
        results["checks"].append({
            "name": "backend_health",
            "status": "skip",
            "message": f"Not running: {str(e)[:50]}"
        })
    
    # Check 2: Database
    db_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend", "database.db")
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.execute("SELECT 1")
        conn.close()
        results["checks"].append({
            "name": "database",
            "status": "pass",
            "message": "SQLite OK"
        })
    except Exception as e:
        results["checks"].append({
            "name": "database",
            "status": "fail",
            "message": str(e)[:50]
        })
    
    # Check 3: Python version
    results["checks"].append({
        "name": "python_version",
        "status": "pass",
        "message": f"Python {sys.version_info.major}.{sys.version_info.minor}"
    })
    
    # Output
    if "--json" in sys.argv:
        print(json.dumps(results, indent=2))
    else:
        for check in results["checks"]:
            status_icon = "✅" if check["status"] == "pass" else "❌" if check["status"] == "fail" else "⏭️"
            print(f"{status_icon} {check['name']}: {check['message']}")

if __name__ == "__main__":
    main()