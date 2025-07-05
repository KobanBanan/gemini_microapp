#!/bin/bash

# Set environment variables
export GEMINI_API_KEY=""

echo "===== Google Docs Analyzer ====="
echo ""
echo "Starting application..."
echo ""
echo "Application will be available at: http://localhost:8501"
echo ""
echo "Authentication: Uses Google refresh token with credentials from creds.json"
echo ""
echo "Press Ctrl+C to stop the application"
echo ""

# Start main application
echo "Starting application on port 8501..."
streamlit run app.py --server.port 8501 --server.address 0.0.0.0