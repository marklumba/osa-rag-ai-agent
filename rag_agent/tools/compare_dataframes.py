"""
Tool for comparing two previously loaded dataframes.

FIX: Now loads from GCS when dataframe_registry is not in tool_context.state.
     This ensures cross-request persistence works correctly.
"""

import os
import uuid
import pickle
from typing import Optional

import pandas as pd
from google.adk.tools.tool_context import ToolContext
from google.cloud import storage

# ── GCS config ────────────────────────────────────────────────────────────────
BUCKET_NAME    = "osa-rag-ai-agent-bucket"
SESSION_FOLDER = "sessions"
storage_client = storage.Client()


def get_session_id(tool_context: ToolContext) -> str:
    """Extract session ID from ADK tool context state."""
    if hasattr(tool_context, "state"):
        sid = tool_context.state.get("session_id")
        if sid:
            return str(sid)
    return os.getenv("TEST_SESSION_ID", "local_dev_session_001")


def load_df_from_gcs(session_id: str, name: str) -> Optional[pd.DataFrame]:
    """Load a pickled DataFrame from GCS. Returns None if not found."""
    blob_path = f"{SESSION_FOLDER}/{session_id}/{name}.pkl"
    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob   = bucket.blob(blob_path)
        if not blob.exists():
            return None
        temp_path = f"/tmp/{uuid.uuid4()}_{name}_dl.pkl"
        blob.download_to_filename(temp_path)
        with open(temp_path, "rb") as f:
            df = pickle.load(f)
        os.remove(temp_path)
        print(f"[GCS LOAD] Restored '{name}' from GCS for compare")
        return df
    except Exception as e:
        print(f"[GCS LOAD ERROR] {name}: {e}")
        return None


def build_registry_entry(df: pd.DataFrame) -> dict:
    """Build a metadata snapshot from a live DataFrame."""
    return {
        "columns":      [str(c) for c in df.columns],
        "row_count":    int(len(df)),
        "dtypes":       {str(c): str(t) for c, t in df.dtypes.items()},
        "numeric_stats": (
            df.describe(include="number").round(2).to_dict()
            if not df.select_dtypes(include="number").empty else {}
        ),
        "null_counts": {
            str(c): int(n)
            for c, n in df.isnull().sum().items() if n > 0
        },
        "sample": df.head(5).fillna("null").astype(str).to_dict(orient="records"),
    }


def get_registry_entry(
    name: str,
    tool_context: ToolContext,
    session_id: str,
) -> Optional[dict]:
    """
    Get metadata for a dataframe.
    Priority:
    1. tool_context.state['dataframe_registry'] (same-request, fastest)
    2. Rebuild from GCS pickle (cross-request persistence)
    """
    # Check in-memory registry first
    registry = tool_context.state.get("dataframe_registry", {})
    if name in registry:
        print(f"[STATE HIT] '{name}' registry found in state")
        return registry[name]

    # Fall back to GCS — load the actual DataFrame and rebuild registry
    print(f"[GCS FALLBACK] '{name}' not in state registry, loading from GCS...")
    df = load_df_from_gcs(session_id, name)
    if df is None:
        return None

    # Rebuild registry entry and cache it back into state
    entry = build_registry_entry(df)
    if "dataframe_registry" not in tool_context.state:
        tool_context.state["dataframe_registry"] = {}
    tool_context.state["dataframe_registry"][name] = entry
    print(f"[GCS FALLBACK] Rebuilt registry for '{name}' from GCS ✅")
    return entry


def compare_dataframes(
    left_name: str,
    right_name: str,
    compare_on: Optional[str] = None,
    tool_context: ToolContext = None,
) -> dict:
    """
    Compare two dataframes using metadata snapshots.
    Automatically restores from GCS if not in current session state.

    Args:
        left_name:  Name of the first dataframe
        right_name: Name of the second dataframe
        compare_on: Optional column name to highlight value-level intent
        tool_context: Tool context

    Returns:
        dict: Text-only comparison results
    """
    session_id = get_session_id(tool_context)
    print(f"[COMPARE] session={session_id} | {left_name} vs {right_name}")

    # ── Get registry entries (state or GCS) ───────────────────────────────────

    left = get_registry_entry(left_name, tool_context, session_id)
    if left is None:
        # List what IS available in GCS for helpful error
        try:
            bucket = storage_client.bucket(BUCKET_NAME)
            blobs  = list(bucket.list_blobs(prefix=f"{SESSION_FOLDER}/{session_id}/"))
            available = [b.name.split("/")[-1].replace(".pkl", "") for b in blobs]
        except Exception:
            available = []
        return {
            "status":  "error",
            "message": f"DataFrame '{left_name}' not found in session or GCS.",
            "available_dataframes": available,
            "hint":    f"Load '{left_name}' first using load_dataframe().",
        }

    right = get_registry_entry(right_name, tool_context, session_id)
    if right is None:
        try:
            bucket = storage_client.bucket(BUCKET_NAME)
            blobs  = list(bucket.list_blobs(prefix=f"{SESSION_FOLDER}/{session_id}/"))
            available = [b.name.split("/")[-1].replace(".pkl", "") for b in blobs]
        except Exception:
            available = []
        return {
            "status":  "error",
            "message": f"DataFrame '{right_name}' not found in session or GCS.",
            "available_dataframes": available,
            "hint":    f"Load '{right_name}' first using load_dataframe().",
        }

    # ── Schema comparison ─────────────────────────────────────────────────────

    left_cols  = set(left["columns"])
    right_cols = set(right["columns"])

    schema_diff = {
        "only_in_left":   sorted(left_cols - right_cols),
        "only_in_right":  sorted(right_cols - left_cols),
        "common_columns": sorted(left_cols & right_cols),
    }

    # ── Row count comparison ──────────────────────────────────────────────────

    row_diff = {
        left_name:   left["row_count"],
        right_name:  right["row_count"],
        "difference": right["row_count"] - left["row_count"],
    }

    # ── Numeric stat comparison (common columns only) ─────────────────────────

    numeric_diff = {}
    for col in schema_diff["common_columns"]:
        l_stats = left.get("numeric_stats", {})
        r_stats = right.get("numeric_stats", {})
        if col in l_stats and col in r_stats:
            numeric_diff[col] = {}
            for stat in ["mean", "min", "max"]:
                l_val = l_stats.get(stat, {}).get(col)
                r_val = r_stats.get(stat, {}).get(col)
                if l_val is not None and r_val is not None:
                    numeric_diff[col][stat] = {
                        left_name:  round(l_val, 2),
                        right_name: round(r_val, 2),
                        "delta":    round(r_val - l_val, 2),
                    }

    # ── Null count comparison ─────────────────────────────────────────────────

    null_diff = {}
    all_cols = schema_diff["common_columns"]
    for col in all_cols:
        l_null = left.get("null_counts", {}).get(col, 0)
        r_null = right.get("null_counts", {}).get(col, 0)
        if l_null != r_null:
            null_diff[col] = {
                left_name:  l_null,
                right_name: r_null,
                "delta":    r_null - l_null,
            }

    # ── Optional column hint ──────────────────────────────────────────────────

    compare_hint = None
    if compare_on:
        if compare_on not in schema_diff["common_columns"]:
            compare_hint = f"Column '{compare_on}' not found in both dataframes."
        else:
            compare_hint = (
                f"Both dataframes contain '{compare_on}'. "
                f"Use execute_pandas_code() for row-level comparison."
            )

    # ── Return ────────────────────────────────────────────────────────────────

    return {
        "status":                   "success",
        "left":                     left_name,
        "right":                    right_name,
        "schema_difference":        schema_diff,
        "row_count_comparison":     row_diff,
        "numeric_stat_differences": numeric_diff,
        "null_count_differences":   null_diff,
        "note":                     compare_hint,
    }