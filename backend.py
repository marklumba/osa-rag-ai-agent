"""
ADK Hybrid RAG AI Agent Backend — v6.1.0
─────────────────────────────────────────
Key changes from v5.8:
  - Passes session_id into agent state so tools can call get_session_id()
    and read/write DataFrames from GCS persistently.
  - Removes reload-prompt injection (tools handle their own GCS restore).
  - Keeps InMemorySessionService but seeds state with session_id on creation.
  - Adds /api/session/{id}/dataframes debug endpoint.
"""

import uuid
import os
import traceback
import time
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ADK
from rag_agent.agent import root_agent
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

# Vertex AI
import vertexai
vertexai.init(
    project=os.environ.get("GOOGLE_CLOUD_PROJECT", "osa-rag-ai-agent"),
    location=os.environ.get("GOOGLE_CLOUD_LOCATION", "asia-southeast1"),
)

# GCS (for the debug listing endpoint)
from google.cloud import storage

# Retry
from tenacity import (
    retry, wait_random_exponential,
    stop_after_attempt, retry_if_exception_type,
)
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

PROJECT_ID     = os.environ.get("GOOGLE_CLOUD_PROJECT", "osa-rag-ai-agent")
BUCKET_NAME    = os.environ.get("GCS_BUCKET", "osa-rag-ai-agent-bucket")
SESSION_FOLDER = "sessions"

storage_client = storage.Client()

# ─────────────────────────────────────────────────────────────────────────────
# FASTAPI
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="ADK Hybrid RAG AI Agent API",
    description="RAG Agent with GCS-backed DataFrame persistence",
    version="6.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# ADK RUNNER  (InMemory is fine — state is seeded with session_id)
# ─────────────────────────────────────────────────────────────────────────────

session_service = InMemorySessionService()
agent_runner = Runner(
    app_name="rag-agent",
    agent=root_agent,
    session_service=session_service,
)

# ─────────────────────────────────────────────────────────────────────────────
# REQUEST MODEL
# ─────────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = "default-user"

# ─────────────────────────────────────────────────────────────────────────────
# SESSION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

async def get_or_create_session(user_id: str, session_id: str):
    """
    Return existing ADK session or create a fresh one.

    CRITICAL: We seed state['session_id'] on creation so every tool
    can call get_session_id(tool_context) and get the right value,
    enabling GCS reads/writes under the correct session prefix:
        sessions/{session_id}/{df_name}.pkl
    """
    session = await session_service.get_session(
        app_name=agent_runner.app_name,
        user_id=user_id,
        session_id=session_id,
    )

    if session:
        # Always ensure session_id is in state
        if session.state.get("session_id") != session_id:
            session.state["session_id"] = session_id
        print(f"[SESSION] Reusing {session_id[:20]}...")
        return session

    # Create new session with session_id baked into state
    print(f"[SESSION] Creating new {session_id[:20]}...")
    session = await session_service.create_session(
        app_name=agent_runner.app_name,
        user_id=user_id,
        session_id=session_id,
        state={
            "session_id": session_id,    # ← tools read this via get_session_id()
            "user_id": user_id,
            "dataframes": {},            # populated by load_dataframe tool
            "dataframe_registry": {},    # metadata snapshots
        },
    )
    print(f"[SESSION] Created. State keys: {list(session.state.keys())}")
    return session

# ─────────────────────────────────────────────────────────────────────────────
# AGENT EXECUTION
# ─────────────────────────────────────────────────────────────────────────────

@retry(
    wait=wait_random_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type((ResourceExhausted, ServiceUnavailable)),
    reraise=True,
)
async def execute_agent(user_id: str, session_id: str, message: str) -> str:
    """Run the ADK agent and return the final text response."""

    user_message = types.Content(
        role="user",
        parts=[types.Part(text=message)],
    )

    event_generator = agent_runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_message,
    )

    response_parts = []
    tool_activity  = False

    async for event in event_generator:
        event_type = type(event).__name__
        print(f"  [EVENT] {event_type}")

        if "ToolCall" in event_type or "ToolResponse" in event_type:
            tool_activity = True

        if hasattr(event, "content") and event.content:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    response_parts.append(part.text)

        if hasattr(event, "response") and event.response:
            res = event.response
            if hasattr(res, "candidates") and res.candidates:
                for cand in res.candidates:
                    if cand.content and cand.content.parts:
                        for part in cand.content.parts:
                            if hasattr(part, "text") and part.text:
                                response_parts.append(part.text)

    final = "".join(response_parts).strip()

    if not final:
        if tool_activity:
            return "The agent searched your data but couldn't find a specific answer. Try rephrasing your question."
        return "The agent processed your request but didn't return a response. Please try rephrasing."

    return final

# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Empty message")

    session_id = request.session_id or str(uuid.uuid4())
    user_id    = request.user_id

    try:
        start = time.time()

        print(f"\n{'='*60}")
        print(f"[CHAT] session={session_id[:20]} | user={user_id}")
        print(f"[MSG]  {message[:100]}")
        print(f"{'='*60}")

        # Ensure session exists with session_id seeded into state
        await get_or_create_session(user_id, session_id)

        # Run agent — tools will auto-restore DataFrames from GCS as needed
        response_text = await execute_agent(user_id, session_id, message)

        elapsed = time.time() - start
        print(f"[DONE] {elapsed:.2f}s | {len(response_text)} chars")

        return {
            "status": "success",
            "response": response_text,
            "session_id": session_id,
        }

    except Exception as e:
        print(f"[CRITICAL] {traceback.format_exc()}")
        return {
            "status": "error",
            "response": f"Error: {str(e)}",
            "session_id": session_id,
        }


@app.get("/api/status")
async def get_status():
    return {
        "status": "ready",
        "version": "6.1.0",
        "persistence": "GCS — tools auto-restore DataFrames per session",
        "session_service": "InMemory + session_id seeded in state",
        "bucket": BUCKET_NAME,
        "project": PROJECT_ID,
    }


@app.get("/api/session/{session_id}/dataframes")
async def list_session_dataframes(session_id: str):
    """
    Debug: list all DataFrames saved in GCS for this session.
    Use this to verify persistence is working after loading files.
    """
    try:
        prefix = f"{SESSION_FOLDER}/{session_id}/"
        bucket = storage_client.bucket(BUCKET_NAME)
        blobs  = list(bucket.list_blobs(prefix=prefix))

        df_list = [
            {
                "name": b.name.split("/")[-1].replace(".pkl", ""),
                "size_kb": round(b.size / 1024, 1) if b.size else 0,
                "updated": b.updated.isoformat() if b.updated else None,
                "gcs_path": b.name,
            }
            for b in blobs
        ]

        return {
            "session_id": session_id,
            "dataframes": df_list,
            "count": len(df_list),
            "status": "✅ DataFrames in GCS" if df_list else "⚠️ No DataFrames saved yet",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/session/{session_id}/dataframes")
async def clear_session_dataframes(session_id: str):
    """Clear all GCS DataFrames for a session (full reset)."""
    try:
        prefix = f"{SESSION_FOLDER}/{session_id}/"
        bucket = storage_client.bucket(BUCKET_NAME)
        blobs  = list(bucket.list_blobs(prefix=prefix))
        for blob in blobs:
            blob.delete()
        return {
            "status": "success",
            "deleted": len(blobs),
            "message": f"Cleared {len(blobs)} DataFrames for session {session_id}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 ADK Backend v6.1.0 on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)