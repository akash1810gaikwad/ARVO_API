#!/bin/bash

echo "============================================================"
echo "Cleaning up __pycache__ directories (Linux/Mac)"
echo "============================================================"
echo ""

# Remove __pycache__ directories recursively, excluding venv
find . -type d -name "__pycache__" ! -path "*/venv/*" ! -path "*/env/*" -exec rm -rf {} + 2>/dev/null

echo ""
echo "============================================================"
echo "✅ Cleanup complete!"
echo "============================================================"
echo ""
echo "Note: Python will automatically recreate these directories"
echo "when you run your application. They are already in .gitignore"
echo ""
