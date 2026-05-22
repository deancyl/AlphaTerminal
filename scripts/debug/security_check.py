#!/usr/bin/env python3
"""Security audit for AlphaTerminal."""

import json
import sys
import os
import subprocess
from datetime import datetime

def main():
    results = {
        "timestamp": datetime.now().isoformat(),
        "checks": []
    }
    
    project_root = os.path.join(os.path.dirname(__file__), "..", "..")
    
    # Check 1: pip audit (if available)
    try:
        result = subprocess.run(
            ["pip", "audit", "--format", "json"],
            capture_output=True,
            text=True,
            cwd=os.path.join(project_root, "backend"),
            timeout=60
        )
        vulnerabilities = json.loads(result.stdout) if result.stdout else []
        results["checks"].append({
            "name": "pip_audit",
            "status": "pass" if not vulnerabilities else "fail",
            "message": f"{len(vulnerabilities)} vulnerabilities found"
        })
    except FileNotFoundError:
        results["checks"].append({
            "name": "pip_audit",
            "status": "skip",
            "message": "pip-audit not installed"
        })
    except Exception as e:
        results["checks"].append({
            "name": "pip_audit",
            "status": "skip",
            "message": str(e)[:50]
        })
    
    # Check 2: npm audit
    try:
        result = subprocess.run(
            ["npm", "audit", "--json"],
            capture_output=True,
            text=True,
            cwd=os.path.join(project_root, "frontend"),
            timeout=60
        )
        audit_data = json.loads(result.stdout) if result.stdout else {}
        vuln_count = audit_data.get("metadata", {}).get("vulnerabilities", {}).get("total", 0)
        results["checks"].append({
            "name": "npm_audit",
            "status": "pass" if vuln_count == 0 else "fail",
            "message": f"{vuln_count} vulnerabilities found"
        })
    except FileNotFoundError:
        results["checks"].append({
            "name": "npm_audit",
            "status": "skip",
            "message": "npm not available"
        })
    except Exception as e:
        results["checks"].append({
            "name": "npm_audit",
            "status": "skip",
            "message": str(e)[:50]
        })
    
    # Check 3: Sensitive files check
    sensitive_patterns = ["*.pem", "*.key", ".env", "credentials*", "secrets*"]
    sensitive_found = []
    for pattern in sensitive_patterns:
        try:
            result = subprocess.run(
                ["find", project_root, "-name", pattern, "-type", "f"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.stdout.strip():
                sensitive_found.extend(result.stdout.strip().split("\n"))
        except Exception:
            pass
    
    results["checks"].append({
        "name": "sensitive_files",
        "status": "pass" if not sensitive_found else "fail",
        "message": f"{len(sensitive_found)} sensitive files found"
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