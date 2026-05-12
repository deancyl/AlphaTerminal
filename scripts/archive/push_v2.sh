#!/bin/bash
# AlphaTerminal Git Push Script - v2
# 使用 HTTP 代理端口

set -e

# 尝试不同的代理配置
export https_proxy=http://192.168.1.50:7897
export http_proxy=http://192.168.1.50:7897
# 不使用 all_proxy (SOCKS5)

cd /vol3/@apphome/picoclaw/.picoclaw/workspace/AlphaTerminal

# 配置 Git 使用代理
git config --global http.proxy http://192.168.1.50:7897
git config --global https.proxy http://192.168.1.50:7897

# 验证网络
echo "=== 检查 GitHub 连接 ===" 
curl -s -x http://192.168.1.50:7897 https://api.github.com/zen && echo "✅ GitHub 连接正常"

# 推送代码
echo "=== 执行 git push ==="
git push origin master --verbose 2>&1

# 推送标签
echo "=== 推送标签 v0.5.140 ==="
git push origin v0.5.140 2>&1

echo "=== 完成 ==="