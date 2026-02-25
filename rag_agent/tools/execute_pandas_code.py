"""
Tool for executing pandas code on loaded DataFrames.

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
        print(f"[GCS LOAD] Restored '{name}' from GCS")
        return df
    except Exception as e:
        print(f"[GCS LOAD ERROR] {name}: {e}")
        return None


def get_dataframe(dataframe_name: str, tool_context: ToolContext):
    """
    Get a DataFrame by name.
    Priority:
    1. tool_context.state['dataframes'] (fastest, same-request)
    2. GCS persistent storage (cross-request, after container restart)
    """
    # Try in-memory state first
    dataframes = tool_context.state.get("dataframes", {})
    if dataframe_name in dataframes:
        df_b64 = dataframes[dataframe_name]
        df = pickle.loads(base64.b64decode(df_b64))
        print(f"[STATE HIT] '{dataframe_name}' found in session state")
        return df

    # Fall back to GCS
    session_id = get_session_id(tool_context)
    df = load_df_from_gcs(session_id, dataframe_name)

    if df is not None:
        # Re-cache in state for subsequent tool calls in this request
        if "dataframes" not in tool_context.state:
            tool_context.state["dataframes"] = {}
        tool_context.state["dataframes"][dataframe_name] = base64.b64encode(
            pickle.dumps(df)
        ).decode("utf-8")

    return df


def execute_pandas_code(
    dataframe_name: str,
    pandas_code: str,
    tool_context: ToolContext,
) -> dict:
    """
    Execute pandas code on a loaded dataframe.

    Args:
        dataframe_name: Name of the dataframe to operate on
        pandas_code: Pandas code to execute (use 'df' as the dataframe variable)
        tool_context: Tool context

    Returns:
        dict: Execution results

    Examples:
        pandas_code="df[df['quarter'] == 'Q3']['revenue'].sum()"
        pandas_code="df.nlargest(5, 'sales')[['customer', 'sales']]"
        pandas_code="df.groupby('region')['revenue'].mean()"
    """
    # Get DataFrame (state first, then GCS)
    df = get_dataframe(dataframe_name, tool_context)

    if df is None:
        # List what IS available for helpful error message
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
            "hint": "Use load_dataframe() to load a file first, or check list_dataframes() to see what is available.",
            "code": pandas_code,
        }

    try:
        # Safe execution namespace
        namespace = {
            "df": df,
            "pd": pd,
            "__builtins__": {
                "len": len, "sum": sum, "min": min, "max": max,
                "round": round, "abs": abs, "int": int, "float": float,
                "str": str, "list": list, "dict": dict, "print": print,
                "range": range, "enumerate": enumerate, "zip": zip,
            },
        }

        result = eval(pandas_code, namespace)

        # ── Serialize result ─────────────────────────────────────────────────

        if isinstance(result, pd.DataFrame):
            result_df = result if len(result) <= 100 else result.head(100)
            result_data = {
                "type": "dataframe",
                "shape": {"rows": len(result), "columns": len(result.columns)},
                "columns": [str(c) for c in result.columns],
                "data": result_df.fillna("null").to_dict("records"),
                "truncated": len(result) > 100,
            }

        elif isinstance(result, pd.Series):
            result_s = result if len(result) <= 100 else result.head(100)
            result_data = {
                "type": "series",
                "name": str(result.name) if result.name else "unnamed",
                "data": {str(k): str(v) for k, v in result_s.fillna("null").to_dict().items()},
                "truncated": len(result) > 100,
            }

        elif isinstance(result, (int, float)):
            result_data = {
                "type": "scalar",
                "value": "null" if pd.isna(result) else result,
            }

        elif isinstance(result, str):
            result_data = {"type": "scalar", "value": result}

        elif isinstance(result, bool):
            result_data = {"type": "scalar", "value": result}

        elif isinstance(result, (list, tuple)):
            clean = ["null" if (isinstance(v, float) and pd.isna(v)) else v for v in list(result)[:100]]
            result_data = {
                "type": "list",
                "data": clean,
                "truncated": len(result) > 100,
            }

        else:
            result_data = {"type": "other", "value": str(result)}

        return {
            "status": "success",
            "message": "Code executed successfully",
            "dataframe_name": dataframe_name,
            "code": pandas_code,
            "result": result_data,
        }

    except SyntaxError as e:
        return {
            "status": "error",
            "message": f"Syntax error: {str(e)}",
            "dataframe_name": dataframe_name,
            "code": pandas_code,
            "hint": "Use 'df' as the dataframe variable. Check pandas syntax.",
        }
    except KeyError as e:
        return {
            "status": "error",
            "message": f"Column not found: {str(e)}",
            "dataframe_name": dataframe_name,
            "code": pandas_code,
            "available_columns": [str(c) for c in df.columns],
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Execution error: {str(e)}",
            "dataframe_name": dataframe_name,
            "code": pandas_code,
        }