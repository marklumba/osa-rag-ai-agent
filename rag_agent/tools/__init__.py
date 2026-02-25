"""
RAG Tools package for interacting with Vertex AI RAG corpora.
"""

# RAG tools
from .add_data import add_data
from .create_corpus import create_corpus
from .delete_corpus import delete_corpus
from .delete_document import delete_document
from .get_corpus_info import get_corpus_info
from .list_corpora import list_corpora
from .rag_query import rag_query
from .utils import (
    check_corpus_exists,
    get_corpus_resource_name,
    set_current_corpus,
)

# Pandas tools (NEW)
from .load_dataframe import load_dataframe
from .query_dataframe import query_dataframe
from .list_dataframes import list_dataframes


__all__ = [
    # RAG tools
    "add_data",
    "create_corpus",
    "list_corpora",
    "rag_query",
    "get_corpus_info",
    "delete_corpus",
    "delete_document",
    "check_corpus_exists",
    "get_corpus_resource_name",
    "set_current_corpus",
    # Pandas tools
    "load_dataframe",
    "query_dataframe",
    "list_dataframes",
    "compare_dataframes"
  
    
]


