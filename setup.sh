#!/bin/bash

echo "Setting up Python API Project..."
echo ""

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Check if .env exists
if [ ! -f .env ]; then
    echo "WARNING: .env file not found!"
    echo "Please configure .env file with your database credentials."
    echo ""
fi

# Create logs directory
if [ ! -d logs ]; then
    mkdir logs
fi

echo ""
echo "Setup completed successfully!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your database credentials"
echo "2. Run './run.sh' to start the API server"
echo ""
