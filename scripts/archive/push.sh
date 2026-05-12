#!/bin/bash
# AlphaTerminal Git Push Script
# 使用代理推送代码和标签

set -e

export https_proxy=http://192.168.1.50:7897
export http_proxy=http://192.168.1.50:7897
export all_proxy=socks5://192.168.1.50:7897

cd /vol3/@apphome/picoclaw/.picoclaw/workspace/AlphaTerminal

# 验证网络连接
echo "=== 检查代理和 Token ===" 
curl -s --proxy http://192.168.1.50:7897 https://api.github.com/zen -o /dev/null && echo "✅ 代理正常"

# 获取当前提交
COMMIT_SHA=$(git rev-parse HEAD)
echo "=== 推送 commit: $COMMIT_SHA ==="

# 推送代码
echo "=== 执行 git push ==="
git push origin master -v 2>&1 | tee /tmp/git_push.log || {
  echo "❌ 推送失败"
  cat /tmp/git_push.log
  exit 1
}

# 创建并推送标签
echo "=== 创建标签 v0.5.140 ==="
git tag v0.5.140 -m "fix(admin): 完善系统管理功能"
git push origin v0.5.140 2>&1 | tee /tmp/git_tag.log || {
  echo "⚠️ 标签推送失败（代码可能已推送）"
}

echo "=== 推送完成 ==="
# 推送标签
cd /vol3/@apphome/picoclaw/.picoclaw/workspace/AlphaTerminal
git tag v0.5.141
git push origin v0.5.141
