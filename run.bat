@echo off
echo Starting API Server...
echo.

REM Activate virtual environment if it exists
if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Run the FastAPI application
echo Starting FastAPI server on http://localhost:8000
echo API Documentation available at http://localhost:8000/docs
echo.
python app.py

pause
