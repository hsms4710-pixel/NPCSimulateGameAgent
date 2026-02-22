# MRAG Enhanced NPC Simulator - 启动脚本
# 用法: powershell -ExecutionPolicy Bypass -File start.ps1

$Host.UI.RawUI.WindowTitle = "MRAG Enhanced NPC Simulator"

Write-Host ""
Write-Host " ╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host " ║      MRAG Enhanced NPC Simulator             ║" -ForegroundColor Cyan
Write-Host " ║      多层记忆增强型 NPC 行为模拟系统          ║" -ForegroundColor Cyan
Write-Host " ╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

Set-Location $PSScriptRoot

# 检查 Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host " [错误] 未找到 Python，请先安装 Python 3.10+" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}

$pyVer = python -c "import sys; print(sys.version_info.major, sys.version_info.minor)"
Write-Host " [OK] Python $pyVer" -ForegroundColor Green

# 激活虚拟环境（如果存在）
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host " [*] 激活虚拟环境..." -ForegroundColor Yellow
    & ".venv\Scripts\Activate.ps1"
}

# 检查关键依赖
$depsOk = python -c "import fastapi, uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host " [*] 安装依赖中，请稍候..." -ForegroundColor Yellow
    pip install -r requirements.txt -q
    if ($LASTEXITCODE -ne 0) {
        Write-Host " [错误] 依赖安装失败，请手动运行: pip install -r requirements.txt" -ForegroundColor Red
        Read-Host "按回车退出"
        exit 1
    }
    Write-Host " [OK] 依赖安装完成" -ForegroundColor Green
} else {
    Write-Host " [OK] 依赖已就绪" -ForegroundColor Green
}

# 检查 API 配置
if (Test-Path "api_config.json") {
    $cfg = Get-Content "api_config.json" | ConvertFrom-Json
    Write-Host " [OK] API 配置: $($cfg.provider) / $($cfg.model)" -ForegroundColor Green
} else {
    Write-Host " [警告] 未找到 api_config.json，请在游戏内 '设置' 中配置 API Key" -ForegroundColor Yellow
}

Write-Host ""
Write-Host " [*] 启动服务器..." -ForegroundColor Cyan
Write-Host " [*] 访问地址: http://localhost:8000" -ForegroundColor White
Write-Host " [*] 按 Ctrl+C 停止服务" -ForegroundColor White
Write-Host ""

# 延迟2秒后打开浏览器
Start-Job -ScriptBlock {
    Start-Sleep 2
    Start-Process "http://localhost:8000"
} | Out-Null

# 启动 FastAPI 服务
python -m uvicorn backend.api_server:app --host 0.0.0.0 --port 8000 --reload
