#!/usr/bin/env python3
"""Optional MCP server for PROJECT_INDEX.json queries.

Wraps QueryEngine methods as MCP tools using FastMCP.
Requires: pip install fastmcp (optional dependency)

Usage:
    python3 mcp_server.py

All tools are read-only (readOnlyHint: true).
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


def find_index() -> Path:
    """Find PROJECT_INDEX.json by searching up from CWD."""
    current = Path.cwd()
    while current != current.parent:
        index_path = current / 'PROJECT_INDEX.json'
        if index_path.exists():
            return index_path
        current = current.parent
    fallback = Path.cwd() / 'PROJECT_INDEX.json'
    if fallback.exists():
        return fallback
    raise FileNotFoundError("PROJECT_INDEX.json not found")


def create_mcp_server() -> 'FastMCP':
    """Create and configure the MCP server with all query tools."""
    if not HAS_FASTMCP:
        raise ImportError(
            "FastMCP is required for the MCP server. Install with: pip install fastmcp"
        )

    mcp = FastMCP("project-index-query")

    # Load index
    index_path = find_index()
    qe = QueryEngine.from_file(index_path)

    @mcp.tool()
    def who_calls(symbol: str, depth: int = 1) -> str:
        """Find all callers of a symbol. readOnlyHint: true"""
        result = qe.who_calls(symbol, depth=depth)
        return json.dumps(result, indent=2)

    @mcp.tool()
    def blast_radius(symbol: str, max_depth: int = 3) -> str:
        """Estimate impact of changing a symbol. readOnlyHint: true"""
        result = qe.blast_radius(symbol, max_depth=max_depth)
        return json.dumps(result, indent=2)

    @mcp.tool()
    def dead_code() -> str:
        """Find functions with no callers. readOnlyHint: true"""
        result = qe.dead_code()
        return json.dumps(result, indent=2)

    @mcp.tool()
    def dependency_chain(file_path: str, max_depth: int = 5) -> str:
        """Trace import dependencies of a file. readOnlyHint: true"""
        result = qe.dependency_chain(file_path, max_depth=max_depth)
        return json.dumps(result, indent=2)

    @mcp.tool()
    def search_symbols(pattern: str, max_results: int = 50) -> str:
        """Search for symbols matching a regex pattern. readOnlyHint: true"""
        result = qe.search_symbols(pattern, max_results=max_results)
        return json.dumps(result, indent=2)

    @mcp.tool()
    def file_summary(file_path: str) -> str:
        """Summarize a file's contents. readOnlyHint: true"""
        result = qe.file_summary(file_path)
        if result:
            return json.dumps(result, indent=2)
        return json.dumps({"error": f"File not found: {file_path}"})

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
