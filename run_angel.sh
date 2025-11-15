#!/bin/bash

# Script to run the Angel One trading system

echo "🚀 Starting Angel One Trading System..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements
echo "Installing/updating requirements..."
pip install -r requirements.txt

# Load environment variables from .env file
if [ -f ".env" ]; then
    export $(cat .env | xargs)
    echo "Environment variables loaded from .env file"
else
    echo "Warning: .env file not found. Please create it with your credentials."
fi

# Run the application
echo "Starting the application..."
python angel.py

echo "Application finished."