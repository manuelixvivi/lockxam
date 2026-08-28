@echo off
title LOCKXAM x EQUIGRADE AI SYSTEM LAUNCHER
color 0A
cls

echo ===============================================================================
echo            LOCKXAM x EQUIGRADE AI - 1-CLICK AUTOMATIC LAUNCHER
echo ===============================================================================
echo [1/3] Menyalakan equigradeAI Engine (Port 5000)...
start "EquiGrade AI Engine" cmd /k "cd /d C:\Users\irul2\Downloads\equigradeAI 2\equigradeAI && python sandbox_app.py"

timeout /t 2 /nobreak >nul

echo [2/3] Menyalakan Lockxam Main Server (Port 1409)...
start "Lockxam Server" cmd /k "cd /d C:\Users\irul2\Downloads\Equigrade_x_Lockxam && python main.py"

timeout /t 3 /nobreak >nul

echo [3/3] Menyalakan Cloudflare HTTPS Tunnel Publik...
start "Cloudflare Tunnel" cmd /k "cloudflared tunnel --url http://localhost:1409"

echo ===============================================================================
echo   SEMUA SERVICE BERHASIL DIJALANKAN!
echo   -----------------------------------------------------------------------------
echo   1. equigradeAI Microservice : http://127.0.0.1:5000 (GPT-OSS 120B Engine)
echo   2. Lockxam Single-Port App  : http://127.0.0.1:1409 (Frontend + Backend)
echo   3. Cloudflare HTTPS Tunnel  : Lihat jendela 'Cloudflare Tunnel' untuk URL!
echo ===============================================================================

timeout /t 2 /nobreak >nul
start http://127.0.0.1:1409

echo Selesai! Seluruh service telah dinyalakan.
