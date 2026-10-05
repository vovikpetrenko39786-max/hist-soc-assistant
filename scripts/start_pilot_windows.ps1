$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path ".env")) {
    Write-Host "Файл .env не найден. Скопируйте .env.example в .env и заполните TELEGRAM_BOT_TOKEN и OPENAI_API_KEY." -ForegroundColor Red
    exit 1
}

Write-Host "1/3 Запускаю PostgreSQL..." -ForegroundColor Cyan
docker compose up -d postgres

Write-Host "2/3 Запускаю backend..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

Start-Sleep -Seconds 4

Write-Host "3/3 Запускаю Telegram-бот..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; python -m telegram_bot.main"

Write-Host ""
Write-Host "Pilot 1.0 запущен. Не закрывайте два открывшихся окна backend и Telegram bot." -ForegroundColor Green
