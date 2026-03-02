@echo off
echo ========================================
echo User Journey Tracking - Database Fix
echo ========================================
echo.
echo This script will fix the user_journeys table schema
echo.

REM Check if .env file exists
if not exist .env (
    echo ERROR: .env file not found!
    echo Please create .env file with database connection details
    pause
    exit /b 1
)

echo Step 1: Running SQL fix script...
echo.

REM You'll need to update these with your actual SQL Server connection details
REM Or run the SQL script manually in SQL Server Management Studio

echo Please run fix_all_journey_issues.sql in SQL Server Management Studio
echo.
echo OR use sqlcmd:
echo sqlcmd -S your_server -d ARVO_DATABASE -U your_user -P your_password -i fix_all_journey_issues.sql
echo.

pause

echo.
echo Step 2: Verifying the fix...
echo.

python verify_journey_tracking.py

echo.
echo ========================================
echo Fix Complete!
echo ========================================
echo.
echo Next steps:
echo   1. Restart your application (run.bat)
echo   2. Test creating a new customer and subscription
echo   3. Verify journey tracking with: python verify_journey_tracking.py CUSTOMER_ID
echo.

pause
