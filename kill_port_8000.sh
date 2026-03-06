#!/bin/bash

echo "============================================================"
echo "Finding and killing process on port 8000"
echo "============================================================"
echo ""

# Find the process using port 8000
PID=$(lsof -ti:8000)

if [ -n "$PID" ]; then
    echo "Found process using port 8000: PID $PID"
    echo ""
    echo "Killing process..."
    kill -9 $PID
    echo ""
    echo "✅ Process killed successfully!"
else
    echo "❌ No process found using port 8000"
fi

echo ""
echo "============================================================"
