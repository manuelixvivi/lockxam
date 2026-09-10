@echo off
setlocal enabledelayedexpansion
title LOCKXAM x EQUIGRADE AI SYSTEM LAUNCHER
color 0A
cls

set "ROOT=%~dp0"
cd /d "%ROOT%"

echo ===============================================================================
echo            LOCKXAM x EQUIGRADE AI - UNIFIED SYSTEM LAUNCHER
echo ===============================================================================

REM Detect Python executable in local .venv or system PATH
if exist "%ROOT%.venv\Scripts\python.exe" (
    set "PY_CMD=%ROOT%.venv\Scripts\python.exe"
    echo [*] Menggunakan virtualenv lokal: .venv\Scripts\python.exe
) else (
    set "PY_CMD=python"
    echo [*] Menggunakan sistem python: python
)

echo [1/2] Menyalakan Unified FastAPI Backend (Port 8000)...
start "Lockxam Unified Backend" "%PY_CMD%" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

timeout /t 3 /nobreak >nul

REM Optional: Start Cloudflare Tunnel if installed
where cloudflared >nul 2>nul
if %errorlevel% equ 0 (
    echo [2/2] Menyalakan Cloudflare HTTPS Tunnel Publik...
    start "Cloudflare Tunnel" cmd /k "cloudflared tunnel --url http://localhost:8000"
) else (
    echo [2/2] Cloudflare tunnel tidak terdeteksi di PATH, melewati tunnel publik.
)

echo ===============================================================================
echo   SERVICE BERHASIL DIJALANKAN!
echo   -----------------------------------------------------------------------------
echo   FastAPI Unified Backend : http://127.0.0.1:8000
echo   API Documentation       : http://127.0.0.1:8000/docs
echo   Health Check            : http://127.0.0.1:8000/health
echo ===============================================================================

timeout /t 2 /nobreak >nul
start http://127.0.0.1:8000

echo Selesai! Seluruh service telah dinyalakan.
