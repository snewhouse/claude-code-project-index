# Next-Generation Code Indexer Architecture (v2)

**Design Date:** 2026-03-17
**Constraint:** Per-project indexing only (one PROJECT_INDEX.json per project root)
**Status:** Architecture Blueprint

---

## Executive Summary

This document designs a v2 indexer that addresses all 7 stated requirements while preserving v1's core strengths (zero dependencies, progressive compression, graceful degradation, clean hook protocol).

**Key changes from v1:**
1. Replace regex Python parser with `ast` module (stdlib, 100% accurate)
2. Add cross-file call graph via `importlib`-style import resolution
3. Implement incremental indexing (per-file hash cache, only re-parse dirty files)
4. Extract type information (parameter types, return types, class hierarchies)
5. Add query engine (who_calls, blast_radius, dead_code, dependency_chain)
6. Restructure as a proper Python package (still zero external deps)
7. Optional MCP server for programmatic Claude access

---

## Module Design

### Package Structure

```
~/.claude-code-project-index/
    indexer/                          # Core library package
        __init__.py
        parsers/
            __init__.py               # Parser registry (data-driven dispatch)
            base.py                   # ParserProtocol (typing.Protocol)
            python_parser.py          # ast-based (100% accuracy)
            javascript_parser.py      # Regex-based (cleaned v1 code)
            shell_parser.py           # Regex-based (deduplicated)
        graph/
            __init__.py
            builder.py                # Cross-file call graph construction
            resolver.py               # Import resolution (imports -> file paths)
            query.py                  # Query engine (who_calls, blast_radius, etc.)
        index/
            __init__.py
            schema.py                 # TypedDict definitions for v2 schema
            builder.py                # build_or_update_index() orchestrator
            compressor.py             # Progressive compression pipeline (v1 preserved)
            serializer.py             # Atomic writes (tempfile + os.replace)
            cache.py                  # Per-file hash cache for incremental indexing
        discovery/
            __init__.py
            git.py                    # git ls-files based discovery
            walk.py                   # Fallback filesystem walk
            filters.py                # Gitignore, extension, size filters
        utils/
            __init__.py
            constants.py              # All constants (moved from index_utils.py)
    hooks/
        i_flag_hook.py                # Slim (~100 lines, down from 780)
        stop_hook.py                  # Smart staleness check (~30 lines)
    agents/
        index-analyzer.md             # Updated for CLI query interface
    cli.py                            # CLI: index, query, status commands
```

### Key Architectural Decisions

1. **Direct import instead of subprocess** — Hooks import the library directly instead of spawning `project_index.py`. Eliminates double-write pattern. Fallback to subprocess if import fails.

2. **Parser registry** — Data-driven dispatch replaces if/elif chains. Adding a language = 1 file + 1 registration call.

3. **Zero external dependencies preserved** — Core indexer uses only Python stdlib. MCP server is optional (requires `mcp` package).

---

## Python AST Parser

Replace the 381-line regex parser (`extract_python_signatures`) with Python's `ast` module:

- **100% accurate** for all Python syntax (multi-line sigs, nested classes, conditional defs, string literals)
- **Structured type extraction** (parameter types, return types from annotations)
- **Complexity estimation** (cyclomatic complexity via decision point counting)
- **Call extraction** via `ast.walk` — finds all `ast.Call` nodes in function bodies
- **SyntaxError fallback** — if `ast.parse()` fails (e.g., partial file), fall back to regex parser for that file

**Minimum Python version:** 3.9+ (for `ast.unparse()`). Python 3.8 is EOL.

---

## Cross-File Call Graph

### Import Resolution

`ImportResolver` builds a module map (`dotted.name` -> `relative/file/path.py`) from the project's file list, then resolves imports:

- Absolute imports: `import foo.bar` -> `foo/bar.py`
- Relative imports: `from .utils import X` -> `sibling/utils.py`
- Package imports: `import foo` -> `foo/__init__.py`
- `__init__.py` re-exports: followed via the module map

**Not resolved** (flagged as unresolvable): dynamic imports (`importlib.import_module`), star imports (conservatively expanded), runtime manipulation.

### Graph Construction

`CrossFileGraphBuilder` connects intra-file calls through resolved imports:

```
project_index.py:build_index() --calls--> extract_python_signatures()
  which resolves via: import index_utils -> index_utils.py
  creating edge: (project_index.py, build_index) -call-> (index_utils.py, extract_python_signatures)
```

Edge types: `call`, `import`, `inherit`, `implement`, `reference`

### Schema Addition

New `xg` key in PROJECT_INDEX.json:
```json
"xg": [
  {"source_file": "s/project_index.py", "source_symbol": "build_index",
   "target_file": "s/index_utils.py", "target_symbol": "extract_python_signatures",
   "edge_type": "call"}
]
```

Backward compatible: v1 consumers ignore `xg`.

---

## Incremental Indexing

### Per-File Cache

`IndexCache` tracks content hashes per file:
```json
"_file_hashes": {
  "scripts/project_index.py": "a1b2c3d4",
  "scripts/index_utils.py": "e5f6g7h8"
}
```

On index update:
1. Compare current file hashes against cached hashes
2. Only re-parse files where hash differs (dirty files)
3. Load cached parse results for unchanged files
4. Rebuild graph from merged results
5. Write updated index with new hashes

**Performance target:** 50k-file project, 1 file changed -> <2 seconds (vs 15-30s for full re-index).

**Fallback:** If cache is corrupt or missing, fall back to full re-index silently.

---

## Query Engine

In-memory graph traversal loaded from `PROJECT_INDEX.json`:

| Query | Method | Use Case |
|-------|--------|----------|
| `who_calls(symbol, depth)` | Reverse BFS | "What depends on this function?" |
| `blast_radius(symbol)` | Forward+reverse BFS | "What breaks if I change this?" |
| `dead_code()` | Full graph scan | "What's never called from entry points?" |
| `dependency_chain(file)` | Import graph traversal | "What does this file need / what needs it?" |

### CLI Interface

```bash
# Generate/update index
python3 ~/.claude-code-project-index/cli.py index

# Query
python3 ~/.claude-code-project-index/cli.py query who-calls build_index 3
python3 ~/.claude-code-project-index/cli.py query blast-radius extract_python_signatures
python3 ~/.claude-code-project-index/cli.py query dead-code
python3 ~/.claude-code-project-index/cli.py query deps scripts/project_index.py

# Status
python3 ~/.claude-code-project-index/cli.py status
```

---

## Integration Points

### Claude Code Hooks (Simplified)
- `i_flag_hook.py` shrinks from 780 to ~100 lines
- Imports library directly (no subprocess double-write)
- Clipboard transport extracted into separate module

### MCP Server (Optional)
- Exposes query engine as MCP tools: `index_who_calls`, `index_blast_radius`, `index_dead_code`
- Requires `pip install mcp` (optional dependency)
- Claude can query directly instead of parsing JSON

### Skills Integration
- `impact-analysis` skill can invoke CLI queries
- `code-intelligence` skill uses query engine for structural answers
- `index-analyzer` agent updated to use CLI instead of raw JSON parsing

### Git Hooks (Optional)
- `post-commit` hook triggers incremental re-index in background
- Keeps index fresh between Claude Code sessions

---

## Index Schema v2 (Backward Compatible)

All v1 keys preserved. New additive keys:

| Key | Type | Content |
|-----|------|---------|
| `_schema_version` | int | `2` (v1 indexes implicitly version 1) |
| `xg` | list | Cross-file graph edges |
| `resolved_deps` | dict | Import -> file path mapping |
| `_file_hashes` | dict | Per-file content hashes |

### Extended Compression Ladder

| Step | Action | New? |
|------|--------|------|
| 0 | Remove `xg` (cross-file graph) | v2 |
| 1 | Truncate tree to 10 items | v1 |
| 2 | Remove `_file_hashes` | v2 |
| 3 | Truncate docstrings to 40 chars | v1 |
| 4 | Strip docstrings entirely | v1 |
| 5 | Remove documentation map | v1 |
| 6 | Remove `resolved_deps` | v2 |
| 7 | Emergency: keep top-N files | v1 |

v2 data is shed first under compression pressure.

---

## Migration Roadmap

### Phase 1: Foundation (Week 1-2)
Refactor into package structure. No behavioral changes. Output byte-for-byte identical to v1.

### Phase 2: AST Parser (Week 3-4)
Replace Python regex parser. A/B test against regex. Feature flag: `V2_AST_PARSER=1`.

### Phase 3: Cross-File Graph (Week 5-6)
Import resolution + graph builder. Add `xg` and `resolved_deps`.

### Phase 4: Incremental Indexing (Week 7-8)
Per-file cache. Target: <2s for 1-file change in 50k-file project.

### Phase 5: Query Engine + CLI (Week 9-10)
Query engine, CLI, updated agent, optional MCP server.

### Phase 6: Polish (Week 11-12)
Updated installer, documentation, end-to-end tests, v1 deprecation path.

---

## Socratic Challenges Addressed

1. **"Does cross-file resolution need to be complete?"** — No. Resolve the common 90% (absolute/relative imports). Flag dynamic imports as unresolvable. False negatives acceptable; false positives dangerous.

2. **"Is incremental indexing worth the complexity?"** — For 12 files, no. For 50k files, yes (15-30s -> <2s). Must degrade gracefully to full re-index on cache corruption.

3. **"Is the query engine duplicating Claude's intelligence?"** — No. Query engine answers in <10ms (vs 10-30s for Claude parsing JSON). Transitive closure is unreliable via LLM. Context efficiency: 20-line answer vs 50k-token full index load.

4. **"Should MCP server be part of this?"** — Optional module only. Core stays zero-dependency.

---

## Performance Budget

| Operation | Target |
|-----------|--------|
| Full index, 100 files | <1s |
| Full index, 10k files | <10s |
| Full index, 50k files | <30s |
| Incremental, 1 file changed | <1s |
| Query: who_calls | <50ms |
| Query: blast_radius (depth 5) | <100ms |
| Hook overhead (no regen) | <50ms |
