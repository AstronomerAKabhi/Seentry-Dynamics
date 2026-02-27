@echo off
TITLE Behavioral FIM Launcher
color 0A
echo ==================================================
echo   BEHAVIORAL FILE INTEGRITY MONITOR
echo   Starting System...
echo ==================================================
echo.

echo [1/2] Launching FIM Core & Server...
:: Starts main.py in a new window with the title "FIM Core"
start "FIM Core" cmd /k "python main.py"

echo [2/2] Waiting for server initialization...
timeout /t 5 /nobreak >nul

echo [3/3] Opening Dashboard...
start http://localhost:8000

echo.
echo ==================================================
echo   SYSTEM ACTIVE
echo   Close the "FIM Core" window to stop monitoring.
echo ==================================================
pause
