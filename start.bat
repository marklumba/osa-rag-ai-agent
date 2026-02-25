@echo off
echo 🚀 Starting ADK Hybrid RAG AI Agent
echo ==================================

echo 📡 Starting backend server...
start "Backend" cmd /k "python backend.py"

echo Waiting for backend to start...
timeout /t 3 /nobreak >nul

echo 🌐 Starting frontend...
cd adk-agent-ui
start "Frontend" cmd /k "npm start"

echo ✅ Both services started!
echo 📡 Backend: http://localhost:8000
echo 🌐 Frontend: http://localhost:3000
echo.
echo Press any key to exit...
pause >nul