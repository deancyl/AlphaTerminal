#!/usr/bin/env python3
"""
WebSocket Debug Tool - 测试WebSocket连接和消息流
Usage: python3 scripts/websocket_debug.py [--url ws://localhost:8002/ws/market] [--duration 10]
"""
import asyncio
import json
import argparse
import sys
import time
from datetime import datetime
from typing import Optional

try:
    import websockets
except ImportError:
    print("Installing websockets...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--break-system-packages", "websockets"])
    import websockets


class WebSocketDebugger:
    def __init__(self, url: str, duration: int = 10, verbose: bool = False):
        self.url = url
        self.duration = duration
        self.verbose = verbose
        self.messages_received = 0
        self.messages_sent = 0
        self.errors = []
        self.latencies = []
        self.start_time = None
        
    async def connect_and_test(self) -> dict:
        """连接WebSocket并运行测试"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "url": self.url,
            "duration": self.duration,
            "connection": {"success": False, "latency_ms": 0, "error": None},
            "messages": {"sent": 0, "received": 0, "errors": []},
            "performance": {"avg_latency_ms": 0, "min_latency_ms": 0, "max_latency_ms": 0},
            "status": "unknown"
        }
        
        try:
            # 测试连接
            conn_start = time.time()
            async with websockets.connect(self.url, timeout=5) as ws:
                conn_latency = (time.time() - conn_start) * 1000
                results["connection"]["success"] = True
                results["connection"]["latency_ms"] = round(conn_latency, 2)
                
                if self.verbose:
                    print(f"✓ Connected in {conn_latency:.2f}ms")
                
                # 发送ping测试
                ping_data = json.dumps({"action": "ping", "timestamp": time.time()})
                await ws.send(ping_data)
                self.messages_sent += 1
                results["messages"]["sent"] = self.messages_sent
                
                # 监听消息
                self.start_time = time.time()
                while time.time() - self.start_time < self.duration:
                    try:
                        msg_start = time.time()
                        msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        msg_latency = (time.time() - msg_start) * 1000
                        
                        self.messages_received += 1
                        self.latencies.append(msg_latency)
                        results["messages"]["received"] = self.messages_received
                        
                        if self.verbose:
                            print(f"  Received ({msg_latency:.2f}ms): {msg[:100]}...")
                            
                    except asyncio.TimeoutError:
                        # 超时是正常的，继续等待
                        continue
                    except Exception as e:
                        error_msg = str(e)
                        self.errors.append(error_msg)
                        results["messages"]["errors"].append(error_msg)
                        if self.verbose:
                            print(f"  Error: {error_msg}")
                            
                # 计算性能指标
                if self.latencies:
                    results["performance"]["avg_latency_ms"] = round(sum(self.latencies) / len(self.latencies), 2)
                    results["performance"]["min_latency_ms"] = round(min(self.latencies), 2)
                    results["performance"]["max_latency_ms"] = round(max(self.latencies), 2)
                
                # 确定状态
                if results["connection"]["success"] and len(self.errors) == 0:
                    results["status"] = "healthy"
                elif results["connection"]["success"]:
                    results["status"] = "degraded"
                else:
                    results["status"] = "failed"
                    
        except Exception as e:
            results["connection"]["error"] = str(e)
            results["status"] = "failed"
            if self.verbose:
                print(f"✗ Connection failed: {e}")
                
        return results


def main():
    parser = argparse.ArgumentParser(description="WebSocket Debug Tool")
    parser.add_argument("--url", default="ws://localhost:8002/ws/market", help="WebSocket URL")
    parser.add_argument("--duration", type=int, default=10, help="Test duration in seconds")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()
    
    debugger = WebSocketDebugger(args.url, args.duration, args.verbose)
    results = asyncio.run(debugger.connect_and_test())
    
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print("\n" + "="*60)
        print("  WebSocket Debug Results")
        print("="*60)
        print(f"URL:      {results['url']}")
        print(f"Status:   {results['status'].upper()}")
        print(f"Duration: {results['duration']}s")
        print("")
        
        conn = results['connection']
        if conn['success']:
            print(f"✓ Connected in {conn['latency_ms']}ms")
        else:
            print(f"✗ Connection failed: {conn.get('error', 'Unknown error')}")
            
        print(f"Messages: {results['messages']['sent']} sent, {results['messages']['received']} received")
        
        if results['messages']['errors']:
            print(f"Errors:   {len(results['messages']['errors'])}")
            
        perf = results['performance']
        if perf['avg_latency_ms'] > 0:
            print(f"Latency:  avg={perf['avg_latency_ms']}ms, min={perf['min_latency_ms']}ms, max={perf['max_latency_ms']}ms")
            
        print("="*60)
    
    # Exit code based on status
    sys.exit(0 if results['status'] in ['healthy', 'degraded'] else 1)


if __name__ == "__main__":
    main()
