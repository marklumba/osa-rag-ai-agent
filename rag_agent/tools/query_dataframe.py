"""
Tool for querying loaded pandas DataFrames with natural language.

FIX: Now loads from GCS when DataFrame is not in tool_context.state.
     This ensures cross-request persistence works correctly.
"""

import os
import uuid
import pickle
import base64

import pandas as pd
from google.adk.tools.tool_context import ToolContext
from google.cloud import storage

# ── GCS config ────────────────────────────────────────────────────────────────
BUCKET_NAME = "osa-rag-ai-agent-bucket"
SESSION_FOLDER = "sessions"
storage_client = storage.Client()


def get_session_id(tool_context: ToolContext) -> str:
    """Extract session ID from ADK tool context state."""
    if hasattr(tool_context, "state"):
        sid = tool_context.state.get("session_id")
        if sid:
            return str(sid)
    return os.getenv("TEST_SESSION_ID", "local_dev_session_001")


def load_df_from_gcs(session_id: str, name: str):
    """Load a pickled DataFrame from GCS. Returns DataFrame or None."""
    blob_path = f"{SESSION_FOLDER}/{session_id}/{name}.pkl"
    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(blob_path)
        if not blob.exists():
            return None
        temp_path = f"/tmp/{uuid.uuid4()}_{name}_dl.pkl"
        blob.download_to_filename(temp_path)
        with open(temp_path, "rb") as f:
            df = pickle.load(f)
        os.remove(temp_path)
        print(f"[GCS LOAD] Restored '{name}' from GCS for query")
        return df
    except Exception as e:
        print(f"[GCS LOAD ERROR] {name}: {e}")
        return None


def get_dataframe(dataframe_name: str, tool_context: ToolContext):
    """
    Get a DataFrame - checks state first, then falls back to GCS.
    Re-caches in state for subsequent calls within the same request.
    """
    dataframes = tool_context.state.get("dataframes", {})
    if dataframe_name in dataframes:
        df = pickle.loads(base64.b64decode(dataframes[dataframe_name]))
        print(f"[STATE HIT] '{dataframe_name}' found in session state")
        return df

    session_id = get_session_id(tool_context)
    df = load_df_from_gcs(session_id, dataframe_name)

    if df is not None:
        # Re-cache in state
        if "dataframes" not in tool_context.state:
            tool_context.state["dataframes"] = {}
        tool_context.state["dataframes"][dataframe_name] = base64.b64encode(
            pickle.dumps(df)
        ).decode("utf-8")

    return df


def query_dataframe(
    dataframe_name: str,
    query: str,
    tool_context: ToolContext,
) -> dict:
    """
    Query a loaded dataframe using natural language.
    Returns dataframe structure info to help the agent generate pandas code.

    Args:
        dataframe_name: Name of the loaded dataframe to query
        query: Natural language query
        tool_context: Tool context

    Returns:
        dict: Dataframe info + code generation guide
    """
    df = get_dataframe(dataframe_name, tool_context)

    if df is None:
        # List available dataframes for helpful error
        state_dfs = list(tool_context.state.get("dataframes", {}).keys())
        session_id = get_session_id(tool_context)
        try:
            bucket = storage_client.bucket(BUCKET_NAME)
            blobs = list(bucket.list_blobs(prefix=f"{SESSION_FOLDER}/{session_id}/"))
            gcs_dfs = [b.name.split("/")[-1].replace(".pkl", "") for b in blobs]
        except Exception:
            gcs_dfs = []

        available = list(set(state_dfs + gcs_dfs))
        return {
            "status": "error",
            "message": f"DataFrame '{dataframe_name}' not found.",
            "available_dataframes": available,
            "query": query,
            "hint": (
                "Use load_dataframe() to load a file first."
                if not available
                else f"Available dataframes: {available}"
            ),
        }

    # Build unique value previews for low-cardinality columns
    unique_preview = {}
    for col in df.columns:
        n_unique = df[col].nunique()
        if 0 < n_unique < 20:
            unique_preview[str(col)] = [
                str(v) for v in df[col].dropna().unique()[:10]
            ]

    return {
        "status": "success",
        "message": f"DataFrame '{dataframe_name}' is ready for querying",
        "query": query,
        "dataframe_name": dataframe_name,
        "dataframe_info": {
            "shape": {"rows": len(df), "columns": len(df.columns)},
            "columns": [str(c) for c in df.columns],
            "dtypes": {str(c): str(t) for c, t in df.dtypes.items()},
            "sample_rows": df.head(5).fillna("null").to_dict("records"),
            "numeric_columns": [str(c) for c in df.select_dtypes(include=["number"]).columns],
            "text_columns": [str(c) for c in df.select_dtypes(include=["object"]).columns],
            "null_counts": {str(c): int(n) for c, n in df.isnull().sum().items() if n > 0},
            "unique_values_preview": unique_preview,
        },
        "code_generation_guide": """
Generate pandas code based on the query and dataframe info above.

Common patterns:
1. FILTERING:    df[df['column'] == 'value']
2. AGGREGATION:  df['column'].sum() / .mean() / .count()
3. GROUPING:     df.groupby('category')['value'].sum()
4. SORTING:      df.sort_values('column', ascending=False)
5. TOP N:        df.nlargest(n, 'column')
6. SELECTION:    df[['col1', 'col2']]
7. MULTI-COND:   df[(df['a'] == 'x') & (df['b'] > 0)]

The dataframe variable is 'df'. Always verify column names match exactly.
Use execute_pandas_code() to run the generated code.
""",
    }
