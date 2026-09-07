@echo off
title AquaShield - Start App
color 0A
echo.
echo  ============================================
echo    AquaShield Flood Warning App
echo  ============================================
echo.

set "ROOT=%~dp0"

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python from python.org
    pause
    exit /b
)

REM Install required packages
echo  Installing/checking Python packages...
python -m pip install -r "%ROOT%backend\requirements.txt" --quiet

echo  Starting AquaShield on http://localhost:8000 ...
echo.
start "AquaShield" cmd /k "cd /d "%ROOT%backend" && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

echo  Waiting 5 seconds for server to start...
timeout /t 5 /nobreak >nul

echo  Opening browser...
start "" "http://localhost:8000"

echo.
echo  ============================================
echo   App is running at: http://localhost:8000
echo  ============================================
echo.
echo  Keep the black window OPEN.
echo  Press any key to close this launcher.
echo.
pause
