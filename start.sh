#!/bin/bash

echo "🚀 Starting ADK Hybrid RAG AI Agent"
echo "=================================="

# Start backend in background
echo "📡 Starting backend server..."
cd "$(dirname "$0")"
uvicorn backend:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Start frontend
echo "🌐 Starting frontend..."
cd adk-agent-ui
npm start &
FRONTEND_PID=$!

echo "✅ Both services started!"
echo "📡 Backend: http://localhost:8000"
echo "🌐 Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both services"

# Wait for user to stop
wait $FRONTEND_PID

# Clean up
echo "🛑 Stopping services..."
kill $BACKEND_PID 2>/dev/null
kill $FRONTEND_PID 2>/dev/null

echo "✅ Services stopped"