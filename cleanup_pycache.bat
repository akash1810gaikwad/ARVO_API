@echo off
echo ============================================================
echo Cleaning up __pycache__ directories (Windows)
echo ============================================================
echo.

REM Remove __pycache__ directories recursively, excluding venv
for /d /r %%d in (__pycache__) do (
    echo %%d | findstr /i "venv" >nul
    if errorlevel 1 (
        if exist "%%d" (
            echo Removing: %%d
            rmdir /s /q "%%d"
        )
    )
)

echo.
echo ============================================================
echo Cleanup complete!
echo ============================================================
echo.
echo Note: Python will automatically recreate these directories
echo when you run your application. They are already in .gitignore
echo.
pause
