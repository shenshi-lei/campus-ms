# 一键开发：创建虚拟环境、安装依赖、写入演示数据并启动服务
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot\..

if (-not (Test-Path -LiteralPath ".venv")) {
    Write-Host "创建虚拟环境 .venv ..."
    python -m venv .venv
}

. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"

Write-Host "应用数据库迁移 ..."
python -m alembic upgrade head

Write-Host "初始化演示数据 ..."
python -m campus.db.seed

Write-Host "启动 http://127.0.0.1:8000 ..."
python -m uvicorn campus.main:app --reload --port 8000
