#!/usr/bin/env python3
"""Optional MCP server for PROJECT_INDEX.json queries.

Wraps QueryEngine methods as MCP tools using FastMCP.
Requires: pip install fastmcp (optional dependency)

Usage:
    python3 mcp_server.py

All tools are read-only (readOnlyHint: true).
Gracefully degrades when no PROJECT_INDEX.json exists.
"""

import json
import sys
from pathlib import Path

# Add scripts/ to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from fastmcp import FastMCP
    HAS_FASTMCP = True
except ImportError:
    HAS_FASTMCP = False

from query_engine import QueryEngine

# Cached engine instance (lazy-loaded on first tool call)
_engine_cache = {"engine": None, "path": None}

NO_INDEX_MSG = json.dumps({
    "error": "No PROJECT_INDEX.json found",
    "hint": "Run /index or `python3 ~/.claude-code-project-index/scripts/project_index.py` to generate one."
})

SERVER_INSTRUCTIONS = (
    "Project Index Query Server — provides structural code intelligence from PROJECT_INDEX.json. "
    "Use these tools to answer questions about code architecture: who calls a function (who_calls), "
    "what breaks if you change something (blast_radius), unused code (dead_code), "
    "import chains (dependency_chain), find symbols by name (search_symbols), "
    "or get a file overview (file_summary). All tools are read-only."
)


def find_index() -> Path | None:
    """Find PROJECT_INDEX.json by searching up from CWD. Returns None if not found."""
    current = Path.cwd()
    while current != current.parent:
        index_path = current / 'PROJECT_INDEX.json'
        if index_path.exists():
            return index_path
        current = current.parent
    fallback = Path.cwd() / 'PROJECT_INDEX.json'
    if fallback.exists():
        return fallback
    return None


def _get_engine() -> QueryEngine | None:
    """Lazy-load QueryEngine, returning None if no index available."""
    index_path = find_index()
    if index_path is None:
        _engine_cache["engine"] = None
        _engine_cache["path"] = None
        return None
    # Reload if path changed (e.g., CWD changed between calls)
    if _engine_cache["engine"] is not None and _engine_cache["path"] == index_path:
        return _engine_cache["engine"]
    try:
        engine = QueryEngine.from_file(index_path)
        _engine_cache["engine"] = engine
        _engine_cache["path"] = index_path
        return engine
    except (json.JSONDecodeError, OSError):
        return None


def create_mcp_server() -> 'FastMCP':
    """Create and configure the MCP server with all query tools."""
    if not HAS_FASTMCP:
        raise ImportError(
            "FastMCP is required for the MCP server. Install with: pip install fastmcp"
        )

    mcp = FastMCP("project-index-query", instructions=SERVER_INSTRUCTIONS)

    @mcp.tool()
    def who_calls(symbol: str, depth: int = 1) -> str:
        """Find all callers of a symbol. readOnlyHint: true"""
        qe = _get_engine()
        if qe is None:
            return NO_INDEX_MSG
        result = qe.who_calls(symbol, depth=depth)
        return json.dumps(result, indent=2)

    @mcp.tool()
    def blast_radius(symbol: str, max_depth: int = 3) -> str:
        """Estimate impact of changing a symbol. readOnlyHint: true"""
        qe = _get_engine()
        if qe is None:
            return NO_INDEX_MSG
        result = qe.blast_radius(symbol, max_depth=max_depth)
        return json.dumps(result, indent=2)

    @mcp.tool()
    def dead_code() -> str:
        """Find functions with no callers. readOnlyHint: true"""
        qe = _get_engine()
        if qe is None:
            return NO_INDEX_MSG
        result = qe.dead_code()
        return json.dumps(result, indent=2)

    @mcp.tool()
    def dependency_chain(file_path: str, max_depth: int = 5) -> str:
        """Trace import dependencies of a file. readOnlyHint: true"""
        qe = _get_engine()
        if qe is None:
            return NO_INDEX_MSG
        result = qe.dependency_chain(file_path, max_depth=max_depth)
        return json.dumps(result, indent=2)

    @mcp.tool()
    def search_symbols(pattern: str, max_results: int = 50) -> str:
        """Search for symbols matching a regex pattern. readOnlyHint: true"""
        qe = _get_engine()
        if qe is None:
            return NO_INDEX_MSG
        result = qe.search_symbols(pattern, max_results=max_results)
        return json.dumps(result, indent=2)

    @mcp.tool()
    def file_summary(file_path: str) -> str:
        """Summarize a file's contents. readOnlyHint: true"""
        qe = _get_engine()
        if qe is None:
            return NO_INDEX_MSG
        result = qe.file_summary(file_path)
        if result:
            return json.dumps(result, indent=2)
        return json.dumps({"error": f"File not found in index: {file_path}"})

    return mcp


def main():
    if not HAS_FASTMCP:
        print("Error: FastMCP not installed. Install with: pip install fastmcp",
              file=sys.stderr)
        sys.exit(1)

    mcp = create_mcp_server()
    mcp.run(transport="stdio")


if __name__ == '__main__':
    main()
