@echo off
echo ============================================================
echo Finding and killing process on port 8000
echo ============================================================
echo.

REM Find the process using port 8000
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do (
    set PID=%%a
)

if defined PID (
    echo Found process using port 8000: PID %PID%
    echo.
    echo Killing process...
    taskkill /F /PID %PID%
    echo.
    echo ✅ Process killed successfully!
) else (
    echo ❌ No process found using port 8000
)

echo.
echo ============================================================
pause
