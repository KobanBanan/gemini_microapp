#!/bin/bash

# Set environment variables
export GEMINI_API_KEY=""

echo "===== Google Docs Analyzer ====="
echo ""
echo "Starting application..."
echo ""
echo "Application will be available at: http://localhost:8501"
echo ""
echo "Authentication: Uses Google OAuth2 for user authentication and document access"
echo ""
echo "Press Ctrl+C to stop the application"
echo ""

# Start main application
echo "Starting application on port 8502..."
streamlit run app.py --server.port 8502 --server.address 0.0.0.0