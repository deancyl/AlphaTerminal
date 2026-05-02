#!/usr/bin/env python3
"""
Log Analysis Tool - 分析后端和前端日志
Usage: python3 scripts/log_analyzer.py [--backend-log /tmp/backend.log] [--frontend-log /tmp/frontend.log] [--json]
"""
import argparse
import json
import re
import sys
from datetime import datetime
from collections import Counter, defaultdict
from pathlib import Path


class LogAnalyzer:
    def __init__(self, backend_log: str = None, frontend_log: str = None):
        self.backend_log = backend_log
        self.frontend_log = frontend_log
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "backend": None,
            "frontend": None,
            "summary": {"total_errors": 0, "total_warnings": 0, "issues": []}
        }
        
    def analyze_file(self, filepath: str, name: str) -> dict:
        """分析单个日志文件"""
        result = {
            "file": filepath,
            "exists": False,
            "size_bytes": 0,
            "line_count": 0,
            "error_count": 0,
            "warning_count": 0,
            "error_patterns": Counter(),
            "recent_errors": [],
            "status": "unknown"
        }
        
        path = Path(filepath)
        if not path.exists():
            result["status"] = "missing"
            return result
            
        result["exists"] = True
        result["size_bytes"] = path.stat().st_size
        
        # 读取日志文件
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception as e:
            result["status"] = "error"
            result["read_error"] = str(e)
            return result
            
        result["line_count"] = len(lines)
        
        # 分析每一行
        error_pattern = re.compile(r'\b(ERROR|CRITICAL|FATAL)\b', re.IGNORECASE)
        warning_pattern = re.compile(r'\b(WARNING|WARN)\b', re.IGNORECASE)
        exception_pattern = re.compile(r'\b(Exception|Error|Traceback)\b')
        
        for i, line in enumerate(lines):
            if error_pattern.search(line):
                result["error_count"] += 1
                # 提取错误类型
                exc_match = exception_pattern.search(line)
                if exc_match:
                    result["error_patterns"][exc_match.group(1)] += 1
                    
                # 保存最近5个错误
                if len(result["recent_errors"]) < 5:
                    result["recent_errors"].append({
                        "line": i + 1,
                        "message": line.strip()[:200]
                    })
                    
            if warning_pattern.search(line):
                result["warning_count"] += 1
        
        # 确定状态
        if result["error_count"] == 0 and result["warning_count"] < 10:
            result["status"] = "healthy"
        elif result["error_count"] == 0:
            result["status"] = "warning"
        else:
            result["status"] = "error"
            
        return result
        
    def analyze(self) -> dict:
        """运行完整分析"""
        if self.backend_log:
            self.results["backend"] = self.analyze_file(self.backend_log, "backend")
            self.results["summary"]["total_errors"] += self.results["backend"]["error_count"]
            self.results["summary"]["total_warnings"] += self.results["backend"]["warning_count"]
            
        if self.frontend_log:
            self.results["frontend"] = self.analyze_file(self.frontend_log, "frontend")
            self.results["summary"]["total_errors"] += self.results["frontend"]["error_count"]
            self.results["summary"]["total_warnings"] += self.results["frontend"]["warning_count"]
        
        # 生成问题列表
        issues = []
        for source, data in [("backend", self.results["backend"]), ("frontend", self.results["frontend"])]:
            if data and data["exists"]:
                if data["error_count"] > 0:
                    issues.append(f"{source}: {data['error_count']} errors found")
                if data["warning_count"] > 10:
                    issues.append(f"{source}: {data['warning_count']} warnings (high)")
        
        self.results["summary"]["issues"] = issues
        
        return self.results


def main():
    parser = argparse.ArgumentParser(description="Log Analysis Tool")
    parser.add_argument("--backend-log", default="/tmp/backend.log", help="Backend log file path")
    parser.add_argument("--frontend-log", default="/tmp/frontend.log", help="Frontend log file path")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()
    
    analyzer = LogAnalyzer(args.backend_log, args.frontend_log)
    results = analyzer.analyze()
    
    if args.json:
        # Convert Counter to dict for JSON serialization
        for source in ["backend", "frontend"]:
            if results[source] and "error_patterns" in results[source]:
                results[source]["error_patterns"] = dict(results[source]["error_patterns"])
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print("\n" + "="*60)
        print("  Log Analysis Results")
        print("="*60)
        
        for source in ["backend", "frontend"]:
            data = results[source]
            if data:
                print(f"\n{source.upper()}:")
                print(f"  File:     {data['file']}")
                print(f"  Status:   {data['status'].upper()}")
                
                if data['exists']:
                    print(f"  Size:     {data['size_bytes'] / 1024:.1f} KB")
                    print(f"  Lines:    {data['line_count']}")
                    print(f"  Errors:   {data['error_count']}")
                    print(f"  Warnings: {data['warning_count']}")
                    
                    if data['error_patterns']:
                        print(f"  Top errors:")
                        for pattern, count in data['error_patterns'].most_common(3):
                            print(f"    - {pattern}: {count}")
                    
                    if data['recent_errors']:
                        print(f"  Recent errors:")
                        for err in data['recent_errors'][:3]:
                            print(f"    Line {err['line']}: {err['message'][:80]}")
        
        print("\n" + "-"*60)
        print(f"Summary: {results['summary']['total_errors']} errors, {results['summary']['total_warnings']} warnings")
        if results['summary']['issues']:
            print("Issues:")
            for issue in results['summary']['issues']:
                print(f"  ⚠ {issue}")
        print("="*60)
    
    # Exit with error if there are errors
    sys.exit(0 if results['summary']['total_errors'] == 0 else 1)


if __name__ == "__main__":
    main()
