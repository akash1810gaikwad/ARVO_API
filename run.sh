#!/bin/bash

echo "Starting API Server..."
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Run the FastAPI application
echo "Starting FastAPI server on http://localhost:8000"
echo "API Documentation available at http://localhost:8000/docs"
echo ""
python app.py
