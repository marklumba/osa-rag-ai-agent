"""
Persistent DataFrame Management Utilities for Hybrid RAG Agent
-------------------------------------------------------------
Stores DataFrames in Cloud Storage instead of in-memory state,
so they survive across messages and reasoning turns.
"""

import pandas as pd
import pickle
import os
import uuid
from typing import List, Dict, Any, Optional
from google.cloud import storage
from google.adk.tools.tool_context import ToolContext

# ────────────────────────────────────────────────
# CONFIGURATION
# ────────────────────────────────────────────────

BUCKET_NAME = "osa-rag-ai-agent-bucket"          # ← your existing bucket
SESSION_FOLDER = "sessions"                      # path prefix: sessions/{session_id}/{df_name}.pkl

storage_client = storage.Client()


def get_session_id(tool_context: ToolContext) -> str:
    """
    Retrieve or generate session ID.
    
    Priority:
    1. From tool_context.metadata (preferred in deployed environment)
    2. From tool_context.state (sometimes available)
    3. Generate a new stable ID or use fixed fallback for local testing
    """
    # Try ADK / Reasoning Engine standard locations
    if hasattr(tool_context, "metadata") and isinstance(tool_context.metadata, dict):
        if "session_id" in tool_context.metadata:
            return str(tool_context.metadata["session_id"])

    if hasattr(tool_context, "state") and isinstance(tool_context.state, dict):
        if "session_id" in tool_context.state:
            return str(tool_context.state["session_id"])

    # Fallback for local development / testing
    # You can replace this with a fixed value during local testing
    # In production you should ensure session_id is always passed
    fallback = os.getenv("TEST_SESSION_ID", "local_dev_session_001")
    return fallback


# ────────────────────────────────────────────────
# CORE FUNCTIONS
# ────────────────────────────────────────────────

def save_dataframe(
    tool_context: ToolContext,
    name: str,
    df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Persist a DataFrame to Cloud Storage under the current session.
    """
    session_id = get_session_id(tool_context)
    blob_path = f"{SESSION_FOLDER}/{session_id}/{name}.pkl"

    try:
        # Serialize to temporary file
        temp_path = f"/tmp/{uuid.uuid4()}_{name}.pkl"
        with open(temp_path, "wb") as f:
            pickle.dump(df, f)

        # Upload
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(blob_path)
        blob.upload_from_filename(temp_path)

        # Clean up
        os.remove(temp_path)

        return {
            "status": "success",
            "message": f"DataFrame '{name}' saved to gs://{BUCKET_NAME}/{blob_path}",
            "session_id": session_id,
            "shape": [len(df), len(df.columns)],
            "columns": list(df.columns),
            "storage_path": blob_path,
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to save DataFrame '{name}': {str(e)}",
        }


def load_dataframe(
    tool_context: ToolContext,
    name: str
) -> Optional[pd.DataFrame]:
    """
    Load a DataFrame from Cloud Storage for the current session.
    Returns None if not found.
    """
    session_id = get_session_id(tool_context)
    blob_path = f"{SESSION_FOLDER}/{session_id}/{name}.pkl"

    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(blob_path)

        if not blob.exists():
            return None

        temp_path = f"/tmp/{uuid.uuid4()}_{name}_download.pkl"
        blob.download_to_filename(temp_path)

        df = pd.read_pickle(temp_path)
        os.remove(temp_path)

        return df

    except Exception:
        return None


def list_dataframes(tool_context: ToolContext) -> Dict[str, Any]:
    """
    List all DataFrames saved in the current session from Cloud Storage.
    """
    session_id = get_session_id(tool_context)
    prefix = f"{SESSION_FOLDER}/{session_id}/"

    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blobs = list(bucket.list_blobs(prefix=prefix))

        if not blobs:
            return {
                "status": "info",
                "message": "No DataFrames saved in this session yet",
                "dataframes": [],
                "total": 0,
            }

        df_info = []
        for blob in blobs:
            name = blob.name.split("/")[-1].replace(".pkl", "")
            df = load_dataframe(tool_context, name)
            if df is not None:
                df_info.append({
                    "name": name,
                    "rows": len(df),
                    "columns_count": len(df.columns),
                    "column_names": list(df.columns),
                    "memory_mb": round(df.memory_usage(deep=True).sum() / 1024**2, 2),
                    "storage_path": blob.name,
                    "updated": blob.updated.isoformat() if blob.updated else None,
                })

        return {
            "status": "success",
            "message": f"Found {len(df_info)} saved DataFrame(s) in session {session_id}",
            "dataframes": df_info,
            "total": len(df_info),
            "total_memory_mb": round(sum(d["memory_mb"] for d in df_info), 2) if df_info else 0,
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to list dataframes: {str(e)}",
            "dataframes": [],
        }


def compare_dataframes(
    tool_context: ToolContext,
    df_names: List[str]
) -> Dict[str, Any]:
    """
    Compare multiple DataFrames loaded from persistent storage.
    """
    loaded = {}
    missing = []

    for name in df_names:
        df = load_dataframe(tool_context, name)
        if df is not None:
            loaded[name] = df
        else:
            missing.append(name)

    if not loaded:
        return {
            "status": "error",
            "message": f"None of the requested DataFrames were found: {', '.join(df_names)}",
            "missing": missing,
            "tables_compared": [],
        }

    comparison = {
        name: {
            "rows": len(df),
            "columns_count": len(df.columns),
            "column_names": list(df.columns),
        }
        for name, df in loaded.items()
    }

    common_columns = set.intersection(*(set(df.columns) for df in loaded.values())) \
        if len(loaded) > 1 else set()

    return {
        "status": "success",
        "tables_compared": list(loaded.keys()),
        "missing": missing,
        "common_columns": list(common_columns),
        "details": comparison,
    }



