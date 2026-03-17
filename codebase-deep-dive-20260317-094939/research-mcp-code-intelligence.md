# MCP Server Design for Code Intelligence Queries

**Research Date:** 2026-03-17
**Context:** claude-code-project-index — adding an optional MCP server that exposes structured queries over PROJECT_INDEX.json instead of having Claude load the raw file.

---

## 1. Existing MCP Servers for Code Intelligence

### Key Players (as of early 2026)

| Server | Approach | Blast Radius | Call Graph | Dead Code | Stars/Status |
|--------|----------|:---:|:---:|:---:|---|
| **CodeMCP (CKB)** | SCIP indexes, 76 tools with preset system | Yes | Yes | Yes | Active, commercial |
| **Code Pathfinder** | Natural language over call graphs | Yes | Yes | No | 2026, cloud |
| **Axon** | KuzuDB knowledge graph, 7 MCP tools | Yes | Yes | Yes | Open source |
| **mcp-codebase-index** | Pickle cache + git HEAD validation, 18 tools | Partial | Partial | No | Open source, Python |
| **Code-Index-MCP** | SQLite/FTS5 + tree-sitter, 48 languages | No | No | No | Open source |

### Key insight: what makes them different from a raw index dump

All successful implementations share one pattern: **they refuse to send the full index to Claude**. Instead they expose narrow, answerable queries. The token savings are dramatic — mcp-codebase-index reports 87% average reduction vs. reading entire source files, and query response times are sub-millisecond for in-memory structures.

---

## 2. Tool vs Resource Patterns in MCP

### When to use a Tool

Tools are invocations with parameters that compute a result. Use tools for:
- Queries with variable arguments (`who_calls("parse_file", depth=3)`)
- Computations over the graph (BFS traversal, reachability)
- Write operations that change server state (`reindex()`)
- Anything where Claude needs to ask a specific question

### When to use a Resource

Resources are addressable data endpoints, roughly equivalent to "read this URI". Use resources for:
- The PROJECT_INDEX.json metadata (`index://meta`)
- A specific file summary (`index://file/{path}`)
- Static stats (`index://stats`)

Resources are pulled by Claude on demand via `@` mention syntax in prompts. They suit large, cacheable blobs better than tools do. However, for code intelligence the tool pattern dominates because Claude needs to ask questions, not pull blobs.

**Recommendation for our use case:** Use tools primarily. Expose the index metadata as a resource as a secondary convenience.

---

## 3. Query Tool Design — Six Core Tools

### 3.1 `who_calls(symbol, depth=2)`

**Purpose:** Reverse BFS — finds all callers of a symbol up to `depth` hops.

**Algorithm:**
1. Build reverse adjacency list from `KEY_GRAPH` edges: `callee → [callers]`
2. BFS from `symbol` in the reverse direction, bounded by `depth`
3. Group results by depth level
4. Return callers with their file paths

**Parameter schema:**
```python
from pydantic import Field
from typing import Annotated

@mcp.tool(annotations={"readOnlyHint": True})
def who_calls(
    symbol: Annotated[str, Field(description="Function or method name. Supports 'ClassName.method' format.")],
    depth: Annotated[int, Field(default=2, ge=1, le=5, description="BFS depth limit. Higher depths are slower.")] = 2,
    file_filter: Annotated[str | None, Field(default=None, description="Optional glob to restrict callers to matching files.")] = None,
) -> dict:
    """Find all functions/methods that call the given symbol, up to depth hops away."""
```

**Expected output structure:**
```json
{
  "symbol": "parse_file",
  "total_callers": 3,
  "by_depth": {
    "1": [{"caller": "build_index", "file": "scripts/project_index.py", "line": 244}],
    "2": [{"caller": "main", "file": "scripts/project_index.py", "line": 734}]
  }
}
```

### 3.2 `blast_radius(symbol, depth=3)`

**Purpose:** Forward + reverse BFS — "if I change this, what breaks?"

**Algorithm:**
1. Forward BFS: what does `symbol` call (transitive callees)
2. Reverse BFS: what calls `symbol` (transitive callers)
3. Union both sets, annotated with direction and depth
4. Optional: estimate risk score based on caller count and depth

**Parameter schema:**
```python
@mcp.tool(annotations={"readOnlyHint": True})
def blast_radius(
    symbol: Annotated[str, Field(description="Symbol to analyze for change impact.")],
    depth: Annotated[int, Field(default=3, ge=1, le=5)] = 3,
    include_risk_score: Annotated[bool, Field(default=True)] = True,
) -> dict:
    """Full impact analysis: what the symbol calls and what calls it, with risk scoring."""
```

**Expected output structure:**
```json
{
  "symbol": "build_index",
  "risk_score": 72,
  "direct_callers": 1,
  "transitive_callers": 3,
  "direct_callees": 8,
  "callers": {"depth_1": [...], "depth_2": [...]},
  "callees": {"depth_1": [...], "depth_2": [...]},
  "affected_files": ["scripts/project_index.py", "scripts/i_flag_hook.py"]
}
```

**Risk score formula:** `min(100, callers_d1 * 20 + callers_d2 * 10 + callers_d3 * 5 + is_entry_point * 30)`

### 3.3 `dead_code(entry_points=None)`

**Purpose:** Find symbols unreachable from any entry point.

**Algorithm:**
1. Identify entry points: functions called from `__main__`, hook registrations, explicitly provided list
2. Forward BFS from all entry points across full call graph
3. Compute `all_symbols - reachable_symbols`
4. Return unreachable symbols grouped by file

**Parameter schema:**
```python
@mcp.tool(annotations={"readOnlyHint": True})
def dead_code(
    entry_points: Annotated[list[str] | None, Field(default=None, description="Explicit entry point symbols. Defaults to 'main', '__init__', and any function with no callers.")] = None,
    min_lines: Annotated[int, Field(default=5, ge=1, description="Minimum function length to report (filters trivial stubs).")] = 5,
) -> dict:
    """Find unreachable symbols (potential dead code) by BFS from entry points."""
```

**Expected output structure:**
```json
{
  "entry_points_used": ["main", "run_hook"],
  "unreachable_count": 4,
  "unreachable": {
    "scripts/index_utils.py": [
      {"symbol": "_legacy_parse", "line": 412, "reason": "no callers found"}
    ]
  }
}
```

### 3.4 `dependency_chain(file, direction="imports")`

**Purpose:** Traverse the import graph for a given file.

**Algorithm:**
1. Use `KEY_DEPS` from the index (already a file→imports map)
2. BFS from `file` following import edges
3. Return chain as an ordered list (topological if possible)

**Parameter schema:**
```python
@mcp.tool(annotations={"readOnlyHint": True})
def dependency_chain(
    file: Annotated[str, Field(description="Relative file path (e.g., 'scripts/project_index.py').")],
    direction: Annotated[Literal["imports", "imported_by", "both"], Field(default="imports")] = "imports",
    depth: Annotated[int, Field(default=5, ge=1, le=10)] = 5,
) -> dict:
    """Trace the import dependency graph for a file."""
```

### 3.5 `search_symbols(pattern, type_filter=None)`

**Purpose:** Fuzzy symbol search across the full index.

**Algorithm:**
1. Gather all function names, class names, method names from `KEY_FILES`
2. Score each against `pattern` using simple substring match or regex
3. Return top-N ranked results with file context

**Parameter schema:**
```python
@mcp.tool(annotations={"readOnlyHint": True})
def search_symbols(
    pattern: Annotated[str, Field(description="Name substring or regex pattern to search.")],
    type_filter: Annotated[Literal["function", "class", "method"] | None, Field(default=None)] = None,
    limit: Annotated[int, Field(default=20, ge=1, le=100)] = 20,
    use_regex: Annotated[bool, Field(default=False)] = False,
) -> dict:
    """Fuzzy search for symbol names across the entire index."""
```

### 3.6 `file_summary(path)`

**Purpose:** Return all functions, classes, imports, and purpose for a single file.

**Algorithm:** Direct lookup in `KEY_FILES` — no traversal needed.

**Parameter schema:**
```python
@mcp.tool(annotations={"readOnlyHint": True})
def file_summary(
    path: Annotated[str, Field(description="Relative file path. Supports partial match (e.g., 'i_flag' matches 'scripts/i_flag_hook.py').")],
) -> dict:
    """Get the full parsed structure of a single file: functions, classes, imports, purpose."""
```

### Additional utility tools (lower priority)

| Tool | Purpose |
|------|---------|
| `list_files(pattern=None)` | List indexed files, optionally filtered by glob |
| `index_status()` | Staleness info, file count, last-indexed timestamp |
| `reindex()` | Force regeneration of PROJECT_INDEX.json |
| `get_call_path(source, target)` | Shortest path between two symbols (BFS) |

---

## 4. FastMCP Framework — Current API (2026)

### Installation

```bash
pip install fastmcp   # standalone, not the mcp SDK bundled version
# Current: 2.2.x series
```

### Server skeleton

```python
from fastmcp import FastMCP, Context
from contextlib import asynccontextmanager
import json
from pathlib import Path

@asynccontextmanager
async def lifespan(mcp: FastMCP):
    """Load the PROJECT_INDEX.json once at startup; make it available to all tools."""
    index_path = Path("PROJECT_INDEX.json")
    if not index_path.exists():
        raise RuntimeError(f"No index found at {index_path}. Run: python scripts/project_index.py")

    index = json.loads(index_path.read_text())
    # Pre-compute reverse call graph for who_calls / blast_radius
    reverse_graph = build_reverse_graph(index.get("g", []))

    yield {
        "index": index,
        "reverse_graph": reverse_graph,
        "index_path": str(index_path),
    }
    # No async cleanup needed for a JSON index

mcp = FastMCP(
    name="project-index",
    instructions="Code intelligence server for the current project. Use who_calls, blast_radius, dead_code, dependency_chain, search_symbols, and file_summary to answer questions about the codebase without loading the full index.",
    lifespan=lifespan,
)
```

### Tool with lifespan context access

```python
@mcp.tool(annotations={"readOnlyHint": True})
async def who_calls(
    symbol: str,
    depth: int = 2,
    ctx: Context = None,
) -> dict:
    """Find all callers of a symbol up to depth hops."""
    data = ctx.lifespan_context
    reverse_graph = data["reverse_graph"]
    return _bfs_callers(reverse_graph, symbol, depth)
```

### Resource for the index metadata

```python
@mcp.resource("index://meta")
async def index_metadata(ctx: Context) -> dict:
    """Index metadata: timestamp, file count, root path, staleness."""
    data = ctx.lifespan_context
    index = data["index"]
    meta = index.get("_meta", {})
    return {
        "root": index.get("root", "."),
        "indexed_at": index.get("at", "unknown"),
        "file_count": len(index.get("f", {})),
        "target_size_k": meta.get("target_size_k"),
        "index_path": data["index_path"],
    }
```

### Key FastMCP patterns to use

| Pattern | Usage |
|---------|-------|
| `@mcp.tool(annotations={"readOnlyHint": True})` | All read-only query tools — skips Claude confirmation |
| `ctx.lifespan_context` | Access the loaded index from within any tool |
| `Annotated[T, Field(description="...")]` | Rich parameter docs for Claude |
| `ToolError` for user errors | `raise ToolError("Symbol 'X' not found in index.")` |
| Structured return types | Return `dict` with consistent schema; Claude gets both human and machine-readable output |
| Async tools | Use `async def` since Python stdlib JSON loading is sync but BFS is CPU-bound — keep sync for simplicity |

### What NOT to do with FastMCP for this use case

- **Do not use SSE or HTTP transport.** Stdio is correct for a local development tool.
- **Do not expose resources for individual symbols.** Too chatty; use tools instead.
- **Do not return raw index sections.** Tools should return specifically the data Claude asked for.
- **Avoid tool-count explosion.** The context token cost of >20 tool definitions is significant. Keep to 6-10 core tools. Claude Code's Tool Search feature will defer loading if count exceeds 10% of context.

---

## 5. Performance Considerations

### Loading strategy: eager at startup

For our use case (PROJECT_INDEX.json, typically 50KB–4MB), **eager loading at startup is correct**:
- JSON parse + reverse graph build: <100ms for any reasonable index
- All queries are in-memory after that: sub-millisecond
- No cold-start penalty per query

The lazy loading pattern (load on first query) is only needed for indexes >100MB or multi-repo setups.

### Pre-compute the reverse graph

The `KEY_GRAPH` in our index is stored as `[[caller, callee], ...]` — forward edges only. Pre-computing the reverse adjacency list at startup is essential:

```python
def build_reverse_graph(edges: list) -> dict[str, list[str]]:
    """Build callee→[callers] map from [[caller, callee], ...] edge list."""
    reverse = {}
    for caller, callee in edges:
        reverse.setdefault(callee, []).append(caller)
    return reverse
```

For 50k edges this takes <10ms and enables O(1) lookup per node in BFS.

### Memory footprint estimates

| Index size | JSON bytes | Parsed dict (Python) | Reverse graph | Total RSS |
|-----------|-----------|---------------------|---------------|-----------|
| Small (50 files) | ~50KB | ~400KB | ~50KB | ~5MB |
| Medium (500 files) | ~500KB | ~4MB | ~500KB | ~25MB |
| Large (5000 files) | ~5MB | ~40MB | ~5MB | ~80MB |
| At limit (10k files, 1MB max) | ~1MB | ~8MB | ~1MB | ~30MB |

Python dict overhead is roughly 8x the raw JSON bytes. For our max index of 1MB, the server will consume ~30MB RSS — entirely acceptable.

### Query response time targets

| Tool | Expected p50 | Expected p99 |
|------|-------------|-------------|
| `file_summary` | <1ms | <5ms |
| `search_symbols` | <5ms | <20ms |
| `who_calls(depth=2)` | <2ms | <10ms |
| `blast_radius(depth=3)` | <5ms | <25ms |
| `dead_code()` | <50ms | <200ms |
| `dependency_chain` | <2ms | <10ms |

All under 100ms. No async needed — the GIL is not a bottleneck here.

### Handling index staleness

Two approaches; recommend implementing both:

1. **Staleness warning in every tool response:** Check `index["_meta"]["files_hash"]` against current git HEAD on each call. If stale, include `"warning": "Index may be stale. Run reindex() or python scripts/project_index.py."` in the response.

2. **`reindex()` tool:** Triggers `subprocess.run(["python3", "scripts/project_index.py"])` and reloads the index into the lifespan context. Requires mutable state (use a threading.Lock and replace the dict reference).

---

## 6. Integration with Claude Code

### Registration in `.mcp.json` (project-scoped, checked into git)

```json
{
  "mcpServers": {
    "project-index": {
      "command": "python3",
      "args": ["${PROJECT_ROOT}/scripts/mcp_server.py"],
      "env": {
        "INDEX_PATH": "${PROJECT_ROOT}/PROJECT_INDEX.json"
      }
    }
  }
}
```

Or via CLI (user-scoped, private to this developer):

```bash
claude mcp add --transport stdio project-index -- \
  python3 /path/to/scripts/mcp_server.py
```

### Scope recommendation

- **Project-scoped (`.mcp.json`):** Correct for a tool that's part of the repository. All team members get it automatically. Requires approval on first use — Claude Code will prompt the user.
- **User-scoped:** Appropriate if the server is installed globally (e.g., `~/.claude-code-project-index/`) and works across all projects.

### Auto-start behavior

Claude Code starts stdio MCP servers automatically when a session begins in the project directory. The server process persists for the session duration. There is **no continuous background process** — the server starts on `claude` invocation and exits when the session ends. This means startup cost is paid once per session, which is fine given our <100ms startup time.

### Environment variable for index path

To support running from different directories, the MCP server should resolve the index path relative to the project root (or from `INDEX_PATH` env var):

```python
import os

INDEX_PATH = Path(os.environ.get("INDEX_PATH", "PROJECT_INDEX.json"))
```

### Connection management: stdio vs SSE/HTTP

**Use stdio exclusively** for this tool. Rationale:
- The server runs on the same machine as Claude Code
- No network overhead
- Simplest security model (no auth needed)
- Claude Code's preferred transport for local tools
- SSE is deprecated as of 2025; Streamable HTTP is the successor for remote servers but unnecessary here

### How hooks and MCP servers interact

Claude Code hooks (UserPromptSubmit, PostToolUse, Stop) are completely independent from MCP servers. They run as subprocess calls at defined lifecycle points. The MCP server is a long-running process connected via stdio. They do not share process space or state.

The existing `-i` hook in `i_flag_hook.py` and the MCP server are complementary:
- Hook: intercepts `-i` flag, generates index, injects context blob into Claude's system prompt
- MCP server: provides on-demand structured queries during the session

The MCP server does not replace the hook. It augments it — the hook gives Claude the project overview upfront, the MCP server lets Claude drill into specifics without re-reading the full index.

### Token budget impact

Tool definitions cost tokens in Claude's context window. Each of our 6-10 tools with docstrings will cost approximately:
- ~100-200 tokens per tool definition
- Total for 10 tools: ~1,500-2,000 tokens

Claude Code's Tool Search feature (enabled by default in Sonnet 4+) will defer loading tools if total MCP tool definitions exceed 10% of context. With 10 small tools this threshold is unlikely to trigger. If it does, Claude discovers tools on demand — no behavior change, slight latency on first use.

### MCP output token limit

Default: 25,000 tokens. The `MAX_MCP_OUTPUT_TOKENS` environment variable controls this. Our tools should never approach this — a `blast_radius` result for a large symbol should stay under 2,000 tokens with good output design.

---

## 7. CLI vs MCP: Pros, Cons, and the Hybrid Answer

### Quantified tradeoffs (2025-2026 benchmarks)

| Dimension | MCP Server | CLI Tool |
|-----------|-----------|---------|
| Context window cost (schema) | ~1,500 tokens for 10 tools | 0 tokens |
| Query execution cost | ~50-200 tokens per result | ~50-200 tokens per result |
| Structured output | Native (JSON schema) | Requires parsing |
| Claude training data | No specific training | Trained on shell commands |
| Human usability | Machine-only | Both human and Claude |
| Setup complexity | Moderate | Minimal |
| State across queries | Shared in-memory index | Cold start each time |
| Token efficiency vs full index | 87% saving | 87% saving |

The "CLI beats MCP" argument in the literature is strongest for servers with 50+ tools (like the GitHub MCP server at 55,000 tokens of schema). For our 6-10 tool server, the schema cost is marginal.

### Recommendation: implement both, CLI is the foundation

**Phase 1 (now):** CLI query interface. Zero dependencies, works in any shell, human-readable.

```bash
python3 scripts/query_index.py who_calls parse_file --depth 2
python3 scripts/query_index.py blast_radius build_index
python3 scripts/query_index.py dead_code
python3 scripts/query_index.py search_symbols "extract.*sign"
```

The CLI reads PROJECT_INDEX.json, runs the query, prints JSON/text, exits. Cold-start cost is ~50ms (Python startup + JSON parse). This is acceptable for occasional human use but not ideal for Claude making 10+ queries per session.

**Phase 2:** MCP server wrapping the same query logic. The CLI functions become the implementation; MCP is a thin wrapper:

```python
# query_engine.py — shared logic
def who_calls(index, symbol, depth=2): ...
def blast_radius(index, symbol, depth=3): ...

# query_cli.py — thin CLI wrapper
# mcp_server.py — thin MCP wrapper
```

This architecture gives:
- Humans: `python3 scripts/query_index.py who_calls foo`
- Claude via MCP: `who_calls("foo", depth=2)`
- Claude via hook: full index blob (existing behavior, unchanged)

### When to prefer CLI over MCP

- Non-Claude AI environments (no MCP support)
- CI/CD pipelines checking dead code
- Human developers auditing impact before a refactor
- Scripting (pipe output to `jq`, `grep`, etc.)

### When to prefer MCP over CLI

- Interactive Claude Code sessions with repeated queries
- Claude needs to follow a chain of calls across multiple queries
- The shared in-memory index matters (10+ queries per session)

---

## 8. Recommended Implementation Architecture

### File structure

```
scripts/
├── project_index.py      # Existing — index generation
├── index_utils.py        # Existing — parsers
├── i_flag_hook.py        # Existing — prompt hook
├── stop_hook.py          # Existing — regeneration
├── query_engine.py       # NEW — pure query logic (no I/O)
├── query_cli.py          # NEW — CLI wrapper for query_engine
└── mcp_server.py         # NEW — FastMCP wrapper for query_engine
```

### `query_engine.py` key interface

```python
class IndexQueryEngine:
    def __init__(self, index: dict):
        self.index = index
        self.files = index.get("f", {})
        self.edges = index.get("g", [])
        self.deps = index.get("deps", {})
        self._forward = self._build_forward_graph()
        self._reverse = self._build_reverse_graph()

    def who_calls(self, symbol: str, depth: int = 2) -> dict: ...
    def blast_radius(self, symbol: str, depth: int = 3) -> dict: ...
    def dead_code(self, entry_points: list[str] | None = None) -> dict: ...
    def dependency_chain(self, file: str, direction: str = "imports", depth: int = 5) -> dict: ...
    def search_symbols(self, pattern: str, type_filter: str | None = None, limit: int = 20) -> dict: ...
    def file_summary(self, path: str) -> dict: ...
```

### `mcp_server.py` skeleton

```python
#!/usr/bin/env python3
"""MCP server for PROJECT_INDEX.json code intelligence queries."""

from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
from typing import Annotated, Literal
from pydantic import Field

# Import shared logic
import sys
sys.path.insert(0, str(Path(__file__).parent))
from query_engine import IndexQueryEngine

@asynccontextmanager
async def lifespan(mcp: FastMCP):
    index_path = Path(os.environ.get("INDEX_PATH", "PROJECT_INDEX.json"))
    if not index_path.exists():
        raise RuntimeError(f"Index not found: {index_path}. Run: python3 scripts/project_index.py")
    engine = IndexQueryEngine(json.loads(index_path.read_text()))
    yield {"engine": engine, "index_path": str(index_path)}

mcp = FastMCP(
    name="project-index",
    instructions=(
        "Code intelligence for the current project. "
        "Query the call graph, find dead code, trace dependencies. "
        "All queries are sub-100ms. Use file_summary for a single file, "
        "search_symbols to find a symbol by name, who_calls/blast_radius for impact analysis."
    ),
    lifespan=lifespan,
)

def _get_engine(ctx: Context) -> IndexQueryEngine:
    return ctx.lifespan_context["engine"]

@mcp.tool(annotations={"readOnlyHint": True})
async def who_calls(
    symbol: Annotated[str, Field(description="Function or method name (e.g., 'parse_file' or 'MyClass.method').")],
    depth: Annotated[int, Field(default=2, ge=1, le=5, description="BFS hop limit.")] = 2,
    ctx: Context = None,
) -> dict:
    """Find all callers of a symbol, traversing the call graph up to depth hops."""
    engine = _get_engine(ctx)
    result = engine.who_calls(symbol, depth)
    if result["total_callers"] == 0:
        raise ToolError(f"Symbol '{symbol}' not found in call graph or has no callers.")
    return result

@mcp.tool(annotations={"readOnlyHint": True})
async def blast_radius(
    symbol: Annotated[str, Field(description="Symbol to analyze for change impact.")],
    depth: Annotated[int, Field(default=3, ge=1, le=5)] = 3,
    ctx: Context = None,
) -> dict:
    """Full impact analysis: what calls the symbol and what the symbol calls."""
    engine = _get_engine(ctx)
    return engine.blast_radius(symbol, depth)

@mcp.tool(annotations={"readOnlyHint": True})
async def dead_code(
    entry_points: Annotated[list[str] | None, Field(default=None, description="Explicit entry points. Defaults to 'main' and functions with no callers.")] = None,
    ctx: Context = None,
) -> dict:
    """Find symbols unreachable from entry points (potential dead code)."""
    engine = _get_engine(ctx)
    return engine.dead_code(entry_points)

@mcp.tool(annotations={"readOnlyHint": True})
async def dependency_chain(
    file: Annotated[str, Field(description="Relative file path (e.g., 'scripts/project_index.py').")],
    direction: Annotated[Literal["imports", "imported_by", "both"], Field(default="imports")] = "imports",
    depth: Annotated[int, Field(default=5, ge=1, le=10)] = 5,
    ctx: Context = None,
) -> dict:
    """Trace import dependencies for a file."""
    engine = _get_engine(ctx)
    return engine.dependency_chain(file, direction, depth)

@mcp.tool(annotations={"readOnlyHint": True})
async def search_symbols(
    pattern: Annotated[str, Field(description="Name substring or regex to match.")],
    type_filter: Annotated[Literal["function", "class", "method"] | None, Field(default=None)] = None,
    limit: Annotated[int, Field(default=20, ge=1, le=100)] = 20,
    ctx: Context = None,
) -> dict:
    """Search for symbol names across the entire index."""
    engine = _get_engine(ctx)
    return engine.search_symbols(pattern, type_filter, limit)

@mcp.tool(annotations={"readOnlyHint": True})
async def file_summary(
    path: Annotated[str, Field(description="Relative file path. Partial match supported.")],
    ctx: Context = None,
) -> dict:
    """Get the parsed structure of a file: functions, classes, imports."""
    engine = _get_engine(ctx)
    result = engine.file_summary(path)
    if result is None:
        raise ToolError(f"File '{path}' not found in index.")
    return result

@mcp.tool(annotations={"readOnlyHint": False})
async def reindex(ctx: Context = None) -> dict:
    """Force regeneration of the project index. Use when the index is stale."""
    import subprocess
    index_path = Path(ctx.lifespan_context["index_path"])
    result = subprocess.run(
        ["python3", str(Path(__file__).parent / "project_index.py")],
        capture_output=True, text=True,
        cwd=str(index_path.parent),
    )
    if result.returncode != 0:
        raise ToolError(f"Reindex failed: {result.stderr}")
    # Reload engine
    new_engine = IndexQueryEngine(json.loads(index_path.read_text()))
    ctx.lifespan_context["engine"] = new_engine
    return {"status": "ok", "output": result.stdout[-500:]}

@mcp.resource("index://meta")
async def index_meta(ctx: Context) -> dict:
    """Index metadata: file count, timestamp, staleness."""
    engine = _get_engine(ctx)
    return {
        "root": engine.index.get("root", "."),
        "indexed_at": engine.index.get("at", "unknown"),
        "file_count": len(engine.files),
        "index_path": ctx.lifespan_context["index_path"],
    }

if __name__ == "__main__":
    mcp.run()  # stdio transport, default
```

---

## 9. The Index Format: What We Already Have

The existing `PROJECT_INDEX.json` already contains everything needed for all six tools:

| Tool | Data source in index |
|------|---------------------|
| `who_calls` | `KEY_GRAPH` (`"g"`) — `[[caller, callee], ...]` edges |
| `blast_radius` | `KEY_GRAPH` — same, bidirectional BFS |
| `dead_code` | `KEY_GRAPH` — BFS reachability from entry points |
| `dependency_chain` | `KEY_DEPS` (`"deps"`) — file→imports map |
| `search_symbols` | `KEY_FILES` (`"f"`) — all parsed function/class names |
| `file_summary` | `KEY_FILES` — full per-file structure |

No index changes are needed. The MCP server is purely a query layer over the existing format.

**One gap:** The `called_by` relationship is built during index generation but may be partially stored in the dense format. The reverse graph must be computed from `KEY_GRAPH` edges at MCP startup (not from `called_by` fields in `KEY_FILES`, which may be incomplete due to compression). This is the correct approach anyway — it's faster and avoids data inconsistency.

---

## 10. Open Questions and Risks

| Question | Assessment |
|----------|-----------|
| Will FastMCP's lifespan correctly persist the index across all tool calls? | Yes — confirmed by docs and deepwiki source analysis. Lifespan yields once at server start, persists until shutdown. |
| Is `ctx.lifespan_context["engine"] = new_engine` safe in `reindex()`? | Partially. Mutating a shared dict is not thread-safe. For single-user stdio this is fine; add a `threading.Lock` if parallelism is needed. |
| Does the compressed `"f"` format have enough data for all queries? | Yes for search_symbols and file_summary. For who_calls/blast_radius the `"g"` edge list is the authoritative source. |
| What if the index has no call graph (project with no parseable files)? | Return empty results with a warning. Do not raise an error. |
| Does Claude Code auto-start the MCP server when `.mcp.json` is in the project root? | Yes — project-scoped `.mcp.json` is read at startup. User will see a one-time approval prompt. |
| FastMCP version stability? | 2.x series is actively maintained under jlowin/fastmcp (originally PrefectHQ). Use `fastmcp>=2.2.0`. Pin to avoid breaking changes. |

---

## Sources Consulted

- [FastMCP Server API — gofastmcp.com](https://gofastmcp.com/servers/server)
- [FastMCP Tools Reference — gofastmcp.com](https://gofastmcp.com/servers/tools)
- [FastMCP Dependency Injection — gofastmcp.com](https://gofastmcp.com/servers/dependency-injection)
- [FastMCP Server Lifecycle — DeepWiki](https://deepwiki.com/jlowin/fastmcp/2.1-server-lifecycle-and-initialization)
- [Connect Claude Code to tools via MCP — code.claude.com](https://code.claude.com/docs/en/mcp)
- [CodeMCP (CKB) — SimplyLiz/CodeMCP on GitHub](https://github.com/SimplyLiz/CodeMCP)
- [Axon knowledge graph engine — harshkedia177/axon on GitHub](https://github.com/harshkedia177/axon)
- [mcp-codebase-index — mcpservers.org](https://mcpservers.org/en/servers/mikerecognex/mcp-codebase-index)
- [Code-Index-MCP — mcpservers.org](https://mcpservers.org/servers/ViperJuice/Code-Index-MCP)
- [Code Pathfinder MCP — codepathfinder.dev](https://codepathfinder.dev/mcp)
- [FastMCP on PyPI — pypi.org/project/fastmcp](https://pypi.org/project/fastmcp/2.2.7/)
- [Managing MCP Servers at Scale — ByteBridge, Medium](https://bytebridge.medium.com/managing-mcp-servers-at-scale-the-case-for-gateways-lazy-loading-and-automation-06e79b7b964f)
- [MCP vs CLI: Why CLI Tools Are Beating MCP — jannikreinhard.com](https://jannikreinhard.com/2026/02/22/why-cli-tools-are-beating-mcp-for-ai-agents/)
- [MCP vs CLI Benchmarks — mariozechner.at](https://mariozechner.at/posts/2025-08-15-mcp-vs-cli/)
- [Feature Request: Lazy Loading MCP Servers — claude-code/issues/7336](https://github.com/anthropics/claude-code/issues/7336)
- [Building MCP Server with FastMCP 2.0 — DataCamp](https://www.datacamp.com/tutorial/building-mcp-server-client-fastmcp)
- [FastMCP GitHub — jlowin/fastmcp](https://github.com/jlowin/fastmcp)
