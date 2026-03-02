@echo off
echo Setting up Python API Project...
echo.

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Check if .env exists
if not exist .env (
    echo WARNING: .env file not found!
    echo Please configure .env file with your database credentials.
    echo.
)

REM Create logs directory
if not exist logs mkdir logs

echo.
echo Setup completed successfully!
echo.
echo Next steps:
echo 1. Edit .env file with your database credentials
echo 2. Run 'run.bat' to start the API server
echo.
pause
