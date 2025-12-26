#!/bin/bash
# Start API Server - Standalone Script
# This script is self-contained and can be run from the /api folder

echo "========================================"
echo "  Meal Plan API Server"
echo "========================================"
echo ""

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed or not in PATH"
    echo "Please install Python 3.8+ from https://www.python.org/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo "Python: $PYTHON_VERSION"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create virtual environment"
        exit 1
    fi
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to activate virtual environment"
    exit 1
fi

# Install/upgrade dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo ""
    echo "WARNING: .env file not found!"
    echo "Creating .env from .env.example..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "Created .env file. Please edit it with your configuration."
    else
        echo "ERROR: .env.example not found. Please create .env manually."
        exit 1
    fi
fi

# Create storage directory if it doesn't exist
if [ ! -d "storage/pdfs" ]; then
    mkdir -p storage/pdfs
    echo "Created storage directory"
fi

# Start the server
echo ""
echo "========================================"
echo "  Starting FastAPI server..."
echo "  URL: http://localhost:8000"
echo "  Docs: http://localhost:8000/docs"
echo "========================================"
echo ""

uvicorn main:app --reload --host 0.0.0.0 --port 8000

