# backend.py
import uuid
import tempfile
import traceback
import os
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- ADK & GOOGLE IMPORTS ---
from rag_agent.agent import root_agent
from google.adk.runners import Runner
from google.adk.sessions.sqlite_session_service import SqliteSessionService
from google.genai import types
from google.api_core import exceptions
from tenacity import retry, wait_random_exponential, stop_after_attempt, retry_if_exception_type

# 1. SETUP: Ensure SQLite directory exists
SESSION_DIR = Path("rag_agent/.adk")
SESSION_DIR.mkdir(parents=True, exist_ok=True)
SESSION_STORAGE_PATH = str(SESSION_DIR / "session.db")

app = FastAPI(
    title="ADK Hybrid RAG AI Agent API",
    description="Persistent RAG Agent with 429 Retry Logic",
    version="3.0.0"
)

# 2. CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Initialize Session Service and Runner
session_service = SqliteSessionService(db_path=SESSION_STORAGE_PATH)
agent_runner = Runner(
    app_name="rag-agent",
    agent=root_agent,
    session_service=session_service,
)

# --- STABLE RETRY WRAPPER ---
@retry(
    wait=wait_random_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type((exceptions.ResourceExhausted, exceptions.ServiceUnavailable)),
    reraise=True
)
async def execute_agent_logic(user_id: str, session_id: str, message: str):
    """Handles session management and consumes the async agent stream."""
    
    # Ensure session exists in SQLite
    session = await agent_runner.session_service.get_session(
        app_name=agent_runner.app_name, user_id=user_id, session_id=session_id
    )
    if not session:
        await agent_runner.session_service.create_session(
            app_name=agent_runner.app_name, user_id=user_id, session_id=session_id
        )

    user_message = types.Content(
        role="user",
        parts=[types.Part(text=message)]
    )

    # Start the async generator
    event_generator = agent_runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_message
    )
    
    agent_response_parts = []
    tool_activity = False

    async for event in event_generator:
        event_type = type(event).__name__
        print(f"[DEBUG] Event: {event_type}")

        # Check for Tool Activity (Helpful for debugging 'empty' responses)
        if "ToolCall" in event_type or "ToolResponse" in event_type:
            tool_activity = True

        # Capture text from 'content' attribute (ADK standard)
        if hasattr(event, 'content') and event.content:
            for part in event.content.parts:
                if hasattr(part, 'text') and part.text:
                    agent_response_parts.append(part.text)
        
        # Capture text from 'response.candidates' (Gemini standard)
        if hasattr(event, 'response') and event.response:
            res = event.response
            if hasattr(res, 'candidates') and res.candidates:
                for cand in res.candidates:
                    if cand.content and cand.content.parts:
                        for part in cand.content.parts:
                            if hasattr(part, 'text') and part.text:
                                agent_response_parts.append(part.text)
                    
    final_response = "".join(agent_response_parts).strip()
    
    if not final_response:
        if tool_activity:
            return "The agent searched your data but couldn't find a specific answer to your query."
        return "I'm sorry, I couldn't generate a response. Please try rephrasing."
        
    return final_response

# --- API ENDPOINTS ---

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Empty message")

    # Reuse existing session or start new
    session_id = request.session_id if request.session_id else str(uuid.uuid4())
    
    try:
        response_text = await execute_agent_logic("default-user", session_id, message)
        
        return {
            "response": response_text,
            "status": "success",
            "session_id": session_id
        }
    except Exception as e:
        print(f"CRITICAL ERROR: {traceback.format_exc()}")
        return {
            "response": f"❌ Error: {str(e)}", 
            "status": "error",
            "session_id": session_id
        }

@app.get("/api/status")
async def get_status():
    return {
        "status": "ready",
        "persistence": "SQLite",
        "db_path": SESSION_STORAGE_PATH
    }

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        temp_dir = Path(tempfile.gettempdir()) / "adk-agent-uploads"
        temp_dir.mkdir(exist_ok=True)
        path = temp_dir / file.filename
        with open(path, "wb") as f:
            f.write(await file.read())
        return {"status": "success", "file_path": str(path), "filename": file.filename}
    except Exception as e:
        raise HTTPException(500, f"Upload failed: {str(e)}")

# --- START SERVER ---
if __name__ == "__main__":
    import uvicorn
    # Reminder: Clear port 8000 using taskkill /F /PID 17116 before running!
    print(f"🚀 Starting ADK Backend on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)




