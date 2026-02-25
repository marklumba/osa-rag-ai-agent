"""
Tool for loading Excel/CSV/Google Sheets files into pandas DataFrames.

FIX: Stores DataFrames in GCS (persistent) instead of only tool_context.state (in-memory).
     This ensures DataFrames survive across requests and container restarts.
"""

import tempfile
import pickle
import os
import uuid
from typing import Optional

import pandas as pd
import requests
from google.adk.tools.tool_context import ToolContext
from google.cloud import storage

from ..config import PROJECT_ID

# ── GCS config (same bucket as list_dataframes.py) ───────────────────────────
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

def save_df_to_gcs(session_id: str, name: str, df: pd.DataFrame) -> str:
    """Pickle a DataFrame and save it to GCS. Returns blob path."""
    blob_path = f"{SESSION_FOLDER}/{session_id}/{name}.pkl"
    temp_path = f"/tmp/{uuid.uuid4()}_{name}.pkl"
    try:
        with open(temp_path, "wb") as f:
            pickle.dump(df, f)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(blob_path)
        blob.upload_from_filename(temp_path)
        return blob_path
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def load_dataframe(
    file_url: str,
    dataframe_name: str,
    sheet_name: Optional[str] = None,
    tool_context: ToolContext = None,
) -> dict:
    """
    Load an Excel/CSV/Google Sheets file into memory as a pandas DataFrame.
    Stores full DataFrame in GCS for cross-request persistence.
    Also stores in tool_context.state for same-request access.
    """
    try:
        # ── 1. Resolve file URL to local path ────────────────────────────────

        if "docs.google.com/spreadsheets" in file_url:
            if "/d/" not in file_url:
                return {"status": "error", "message": "Invalid Google Sheets URL", "file_url": file_url}
            sheet_id = file_url.split("/d/")[1].split("/")[0]
            export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
            try:
                resp = requests.get(export_url, timeout=30)
                resp.raise_for_status()
            except requests.exceptions.HTTPError as e:
                if resp.status_code == 403:
                    return {
                        "status": "error",
                        "message": "Access denied. Make sure the Google Sheet is shared: 'Anyone with the link can view'.",
                        "file_url": file_url,
                        "hint": "Share → Change to 'Anyone with the link' → Viewer",
                    }
                return {"status": "error", "message": f"Failed to download Google Sheet: {str(e)}", "file_url": file_url}
            tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv", encoding="utf-8")
            tmp.write(resp.text)
            tmp.close()
            file_path = tmp.name

        elif "drive.google.com" in file_url:
            if "/file/d/" in file_url:
                file_id = file_url.split("/file/d/")[1].split("/")[0]
            elif "id=" in file_url:
                file_id = file_url.split("id=")[1].split("&")[0]
            else:
                return {"status": "error", "message": "Invalid Google Drive URL", "file_url": file_url}
            download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            resp = requests.get(download_url, timeout=30)
            resp.raise_for_status()
            suffix = ".xlsx" if "spreadsheet" in resp.headers.get("content-type", "") else ".csv"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(resp.content)
            tmp.close()
            file_path = tmp.name

        elif file_url.startswith("gs://"):
            bucket_name, blob_name = file_url[5:].split("/", 1)
            gcs = storage.Client(project=PROJECT_ID)
            blob = gcs.bucket(bucket_name).blob(blob_name)
            suffix = f".{blob_name.split('.')[-1]}"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            blob.download_to_filename(tmp.name)
            file_path = tmp.name

        else:
            file_path = file_url

        # ── 2. Load into DataFrame ────────────────────────────────────────────

        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        elif file_path.endswith(".tsv"):
            df = pd.read_csv(file_path, sep="\t")
        elif file_path.endswith((".xlsx", ".xls")):
            df = pd.read_excel(file_path, sheet_name=sheet_name or 0)
        elif file_path.endswith(".json"):
            df = pd.read_json(file_path)
        elif file_path.endswith(".parquet"):
            df = pd.read_parquet(file_path)
        else:
            return {"status": "error", "message": "Unsupported file format (.csv .xlsx .xls .json .parquet supported)", "file_url": file_url}

        # ── 3. Save to GCS (PERSISTENT — survives container restarts) ─────────

        session_id = get_session_id(tool_context)
        blob_path = save_df_to_gcs(session_id, dataframe_name, df)
        print(f"[GCS SAVED] {dataframe_name} -> gs://{BUCKET_NAME}/{blob_path}")

        # ── 4. Also store in tool_context.state for same-request access ───────
        #    (execute_pandas_code and query_dataframe read from state)

        import base64
        state = tool_context.state
        if "dataframes" not in state:
            state["dataframes"] = {}
        if "dataframe_registry" not in state:
            state["dataframe_registry"] = {}

        df_b64 = base64.b64encode(pickle.dumps(df)).decode("utf-8")
        state["dataframes"][dataframe_name] = df_b64

        # Metadata snapshot for multi-table reasoning
        state["dataframe_registry"][dataframe_name] = {
            "columns": [str(c) for c in df.columns],
            "row_count": int(len(df)),
            "dtypes": {str(c): str(t) for c, t in df.dtypes.items()},
            "numeric_stats": (
                df.describe(include="number").round(2).to_dict()
                if not df.select_dtypes(include="number").empty else {}
            ),
            "null_counts": {str(c): int(n) for c, n in df.isnull().sum().items() if n > 0},
            "sample": df.head(5).fillna("null").astype(str).to_dict(orient="records"),
            "source_url": file_url,
            "gcs_path": blob_path,
        }

        # ── 5. Return text-only summary ───────────────────────────────────────

        null_info = {str(c): int(n) for c, n in df.isnull().sum().items() if n > 0}
        sample_rows = df.head(5).fillna("null").astype(str).to_dict(orient="records")

        return {
            "status": "success",
            "message": f"✅ DataFrame '{dataframe_name}' loaded and saved persistently.",
            "file_url": file_url,
            "dataframe_name": dataframe_name,
            "shape": {"rows": int(len(df)), "columns": int(len(df.columns))},
            "columns": [str(c) for c in df.columns],
            "dtypes": {str(c): str(t) for c, t in df.dtypes.items()},
            "null_counts": null_info,
            "sample_data": sample_rows,
            "memory_usage_mb": round(float(df.memory_usage(deep=True).sum() / 1024 / 1024), 2),
            "gcs_path": blob_path,
            "persistent": True,
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to load dataframe: {str(e)}",
            "file_url": file_url,
            "dataframe_name": dataframe_name,
            "error_type": type(e).__name__,
        }