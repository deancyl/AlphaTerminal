#!/usr/bin/env pwsh
###############################################################################
# AlphaTerminal 一键启动脚本 (Windows PowerShell)
# 
# 功能:
#   - 检查环境（Python、Node.js）
#   - 自动安装依赖
#   - 启动后端（FastAPI）
#   - 启动前端（Vite）
#
# 用法:
#   .\start.ps1              # 启动前后端
#   .\start.ps1 backend      # 仅启动后端
#   .\start.ps1 frontend     # 仅启动前端
#   .\start.ps1 stop         # 停止所有服务
###############################################################################

# ── 配置 ──────────────────────────────────────────────────────────────────
$PROJECT_ROOT = Split-Path -Parent $PSScriptRoot
$BACKEND_DIR = Join-Path $PROJECT_ROOT "backend"
$FRONTEND_DIR = Join-Path $PROJECT_ROOT "frontend"
$LOG_DIR = Join-Path $PROJECT_ROOT "logs"

$BACKEND_PORT = 8002
$FRONTEND_PORT = 60100

$BACKEND_PID_FILE = Join-Path $PROJECT_ROOT ".backend.pid"
$FRONTEND_PID_FILE = Join-Path $PROJECT_ROOT ".frontend.pid"

# ── 颜色函数 ────────────────────────────────────────────────────────────────
function Write-Info { param([string]$Message) Write-Host "[INFO] $Message" -ForegroundColor Green }
function Write-Warn { param([string]$Message) Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-Error { param([string]$Message) Write-Host "[ERROR] $Message" -ForegroundColor Red }
function Write-Step { param([string]$Message) Write-Host "[STEP] $Message" -ForegroundColor Cyan }

# ── 检查命令 ────────────────────────────────────────────────────────────────
function Test-Command { param([string]$Command) 
    return [bool](Get-Command -Name $Command -ErrorAction SilentlyContinue)
}

# ── 检查端口 ────────────────────────────────────────────────────────────────
function Test-Port { param([int]$Port)
    $connection = Test-NetConnection -ComputerName localhost -Port $Port -WarningAction SilentlyContinue
    return $connection.TcpTestSucceeded
}

# ── 检查 Python ─────────────────────────────────────────────────────────────
function Check-Python {
    Write-Step "检查 Python 环境..."
    
    if (Test-Command "python") {
        $script:PYTHON = "python"
    } elseif (Test-Command "python3") {
        $script:PYTHON = "python3"
    } else {
        Write-Error "未找到 Python！请安装 Python 3.11+"
        Write-Info "下载地址: https://www.python.org/downloads/"
        exit 1
    }
    
    $version = & $PYTHON --version 2>&1
    Write-Info "Python 版本: $version"
}

# ── 检查 Node.js ────────────────────────────────────────────────────────────
function Check-NodeJS {
    Write-Step "检查 Node.js 环境..."
    
    if (Test-Command "node") {
        $script:NODE = "node"
        $version = node --version
        Write-Info "Node.js 版本: $version"
    } else {
        Write-Error "未找到 Node.js！请安装 Node.js 20+"
        Write-Info "下载地址: https://nodejs.org/"
        exit 1
    }
    
    if (Test-Command "npm") {
        $script:NPM = "npm"
        $npmVersion = npm --version
        Write-Info "npm 版本: $npmVersion"
    } else {
        Write-Warn "未找到 npm"
        $script:NPM = $null
    }
}

# ── 安装后端依赖 ────────────────────────────────────────────────────────────
function Install-BackendDeps {
    Write-Step "安装后端依赖..."
    
    Set-Location $BACKEND_DIR
    
    # 创建虚拟环境
    if (-not (Test-Path ".venv")) {
        Write-Info "创建 Python 虚拟环境..."
        & $PYTHON -m venv .venv
    }
    
    # 激活虚拟环境
    $venvPython = Join-Path $BACKEND_DIR ".venv\Scripts\python.exe"
    $venvPip = Join-Path $BACKEND_DIR ".venv\Scripts\pip.exe"
    
    # 升级 pip
    & $venvPip install --upgrade pip | Out-Null
    
    # 安装依赖
    Write-Info "安装 Python 依赖（这可能需要几分钟）..."
    & $venvPip install -r requirements.txt | Out-Null
    
    # 检查额外依赖
    try {
        & $venvPython -c "import psutil" | Out-Null
    } catch {
        Write-Info "安装额外依赖 psutil..."
        & $venvPip install psutil | Out-Null
    }
    
    Write-Info "后端依赖安装完成"
}

# ── 安装前端依赖 ────────────────────────────────────────────────────────────
function Install-FrontendDeps {
    Write-Step "安装前端依赖..."
    
    Set-Location $FRONTEND_DIR
    
    # 检查 node_modules
    if (-not (Test-Path "node_modules") -or -not (Test-Path "node_modules\.bin")) {
        Write-Info "node_modules 缺失，需要重新安装..."
        
        if ($NPM) {
            & $NPM install
        } else {
            Write-Error "无法找到 npm"
            exit 1
        }
    } else {
        Write-Info "前端依赖已存在"
    }
    
    Write-Info "前端依赖准备完成"
}

# ── 启动后端 ────────────────────────────────────────────────────────────────
function Start-Backend {
    Write-Step "启动后端服务..."
    
    Set-Location $BACKEND_DIR
    
    # 检查端口占用
    if (Test-Port $BACKEND_PORT) {
        Write-Warn "端口 $BACKEND_PORT 已被占用"
        Write-Info "尝试停止占用进程..."
        Get-Process -Id (Get-NetTCPConnection -LocalPort $BACKEND_PORT).OwningProcess -ErrorAction SilentlyContinue | Stop-Process -Force
        Start-Sleep -Seconds 2
    }
    
    $venvPython = Join-Path $BACKEND_DIR ".venv\Scripts\python.exe"
    
    # 启动后端
    Write-Info "启动 FastAPI 服务 (端口: $BACKEND_PORT)..."
    $process = Start-Process -FilePath $venvPython -ArgumentList "start_backend.py" -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $LOG_DIR "backend.log") -RedirectStandardError (Join-Path $LOG_DIR "backend.err")
    $process.Id | Out-File $BACKEND_PID_FILE
    
    # 等待启动
    Write-Info "等待后端启动..."
    for ($i = 0; $i -lt 30; $i++) {
        if (Test-Port $BACKEND_PORT) {
            Write-Info "✅ 后端启动成功！PID: $($process.Id)"
            Write-Info "   API 地址: http://localhost:$BACKEND_PORT"
            return
        }
        Start-Sleep -Seconds 1
    }
    
    Write-Error "后端启动失败！请检查日志: logs\backend.log"
}

# ── 启动前端 ────────────────────────────────────────────────────────────────
function Start-Frontend {
    Write-Step "启动前端服务..."
    
    Set-Location $FRONTEND_DIR
    
    # 检查端口占用
    if (Test-Port $FRONTEND_PORT) {
        Write-Warn "端口 $FRONTEND_PORT 已被占用"
        Write-Info "尝试停止占用进程..."
        Get-Process -Id (Get-NetTCPConnection -LocalPort $FRONTEND_PORT).OwningProcess -ErrorAction SilentlyContinue | Stop-Process -Force
        Start-Sleep -Seconds 2
    }
    
    # 启动前端
    Write-Info "启动 Vite 开发服务器 (端口: $FRONTEND_PORT)..."
    
    if ($NPM) {
        $process = Start-Process -FilePath $NPM -ArgumentList "run", "dev" -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $LOG_DIR "frontend.log") -RedirectStandardError (Join-Path $LOG_DIR "frontend.err")
    } else {
        $vitePath = Join-Path $FRONTEND_DIR "node_modules\.bin\vite.cmd"
        $process = Start-Process -FilePath $vitePath -ArgumentList "--host", "0.0.0.0" -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $LOG_DIR "frontend.log") -RedirectStandardError (Join-Path $LOG_DIR "frontend.err")
    }
    
    $process.Id | Out-File $FRONTEND_PID_FILE
    
    # 等待启动
    Write-Info "等待前端启动..."
    for ($i = 0; $i -lt 30; $i++) {
        if (Test-Port $FRONTEND_PORT) {
            Write-Info "✅ 前端启动成功！PID: $($process.Id)"
            Write-Info "   访问地址: http://localhost:$FRONTEND_PORT"
            return
        }
        Start-Sleep -Seconds 1
    }
    
    Write-Error "前端启动失败！请检查日志: logs\frontend.log"
}

# ── 停止服务 ────────────────────────────────────────────────────────────────
function Stop-Services {
    Write-Step "停止服务..."
    
    # 停止后端
    if (Test-Path $BACKEND_PID_FILE) {
        $pid = Get-Content $BACKEND_PID_FILE
        if ($pid) {
            Write-Info "停止后端 (PID: $pid)..."
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
        Remove-Item $BACKEND_PID_FILE -Force -ErrorAction SilentlyContinue
    }
    
    # 停止前端
    if (Test-Path $FRONTEND_PID_FILE) {
        $pid = Get-Content $FRONTEND_PID_FILE
        if ($pid) {
            Write-Info "停止前端 (PID: $pid)..."
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
        Remove-Item $FRONTEND_PID_FILE -Force -ErrorAction SilentlyContinue
    }
    
    # 强制清理端口
    if (Test-Port $BACKEND_PORT) {
        Write-Warn "强制清理后端端口 $BACKEND_PORT..."
        Get-Process -Id (Get-NetTCPConnection -LocalPort $BACKEND_PORT).OwningProcess -ErrorAction SilentlyContinue | Stop-Process -Force
    }
    
    if (Test-Port $FRONTEND_PORT) {
        Write-Warn "强制清理前端端口 $FRONTEND_PORT..."
        Get-Process -Id (Get-NetTCPConnection -LocalPort $FRONTEND_PORT).OwningProcess -ErrorAction SilentlyContinue | Stop-Process -Force
    }
    
    Write-Info "✅ 所有服务已停止"
}

# ── 显示状态 ────────────────────────────────────────────────────────────────
function Show-Status {
    Write-Step "服务状态"
    
    if (Test-Port $BACKEND_PORT) {
        Write-Info "✅ 后端运行中 (端口: $BACKEND_PORT)"
    } else {
        Write-Warn "❌ 后端未运行"
    }
    
    if (Test-Port $FRONTEND_PORT) {
        Write-Info "✅ 前端运行中 (端口: $FRONTEND_PORT)"
    } else {
        Write-Warn "❌ 前端未运行"
    }
}

# ── 主函数 ──────────────────────────────────────────────────────────────────
function Main {
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║                                                              ║" -ForegroundColor Cyan
    Write-Host "║          AlphaTerminal 一键启动脚本 (Windows)                ║" -ForegroundColor Cyan
    Write-Host "║                                                              ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
    
    # 创建日志目录
    New-Item -ItemType Directory -Force -Path $LOG_DIR | Out-Null
    
    switch ($args[0]) {
        "stop" { Stop-Services }
        "status" { Show-Status }
        "backend" {
            Check-Python
            Install-BackendDeps
            Start-Backend
        }
        "frontend" {
            Check-NodeJS
            Install-FrontendDeps
            Start-Frontend
        }
        "install" {
            Check-Python
            Check-NodeJS
            Install-BackendDeps
            Install-FrontendDeps
            Write-Info "✅ 依赖安装完成！"
        }
        default {
            Check-Python
            Check-NodeJS
            Install-BackendDeps
            Install-FrontendDeps
            Start-Backend
            Start-Frontend
            
            Write-Host ""
            Write-Host "══════════════════════════════════════════════════════════════" -ForegroundColor Green
            Write-Host "  ✅ AlphaTerminal 启动成功！                                  " -ForegroundColor Green
            Write-Host "══════════════════════════════════════════════════════════════" -ForegroundColor Green
            Write-Host ""
            Write-Host "  🌐 前端访问: http://localhost:$FRONTEND_PORT" -ForegroundColor Cyan
            Write-Host "  🔌 API 地址: http://localhost:$BACKEND_PORT" -ForegroundColor Cyan
            Write-Host "  📊 API 文档: http://localhost:$BACKEND_PORT/docs" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "  📋 常用命令:" -ForegroundColor Yellow
            Write-Host "     查看状态: .\start.ps1 status" -ForegroundColor Yellow
            Write-Host "     停止服务: .\start.ps1 stop" -ForegroundColor Yellow
            Write-Host "     仅后端:   .\start.ps1 backend" -ForegroundColor Yellow
            Write-Host "     仅前端:   .\start.ps1 frontend" -ForegroundColor Yellow
            Write-Host ""
            Write-Host "  📝 日志文件:" -ForegroundColor Blue
            Write-Host "     后端: logs\backend.log" -ForegroundColor Blue
            Write-Host "     前端: logs\frontend.log" -ForegroundColor Blue
            Write-Host ""
        }
    }
}

# 执行主函数
Main @args