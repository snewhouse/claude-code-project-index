# project-index-upgrade Reference

## Immutable Facts and Constants

_These are non-negotiable facts extracted from the plan and research._

### Python Version Requirement

- Minimum: Python 3.9+ (required for `ast.unparse()`)
- Fallback: Regex parser used if Python < 3.9

### API Endpoints

- No external API endpoints. This is a local CLI/hook tool.

### File Paths

#### Files to Modify

| File | Lines | Context |
|------|-------|---------|
| `scripts/index_utils.py` | Multiple | Add shared utilities, AST parser, cross-file resolution, type fixes |
| `scripts/index_utils.py:14-16` | 14-16 | Duplicate `__pycache__` in IGNORE_DIRS |
| `scripts/index_utils.py:133-513` | 133-513 | `extract_python_signatures` (god function to decompose) |
| `scripts/index_utils.py:516` | 516 | Type annotation `any` to `Any` |
| `scripts/index_utils.py:898` | 898 | Type annotation `any` to `Any` |
| `scripts/index_utils.py:969` | 969 | Type annotation `any` to `Any` |
| `scripts/index_utils.py:1175` | 1175 | Type annotation `any` to `Any` |
| `scripts/index_utils.py:1175-1200` | 1175-1200 | PARSER_REGISTRY location |
| `scripts/index_utils.py:567,609,662,744,825` | Multiple | 5 inline brace-counting instances to extract |
| `scripts/i_flag_hook.py:31-51` | 31-51 | `_validate_python_cmd` (remove, replace with import) |
| `scripts/i_flag_hook.py:135-170` | 135-170 | `calculate_files_hash` (remove, replace with import) |
| `scripts/i_flag_hook.py:204-309` | 204-309 | `generate_index_at_size` (test target) |
| `scripts/i_flag_hook.py:274-293` | 274-293 | Atomic write pattern (replace with shared utility) |
| `scripts/i_flag_hook.py:413` | 413 | `subprocess.run(['which', 'xclip'])` to `shutil.which` |
| `scripts/i_flag_hook.py:501-508` | 501-508 | `ssh_file_large` dead branch |
| `scripts/stop_hook.py:13-33` | 13-33 | `_validate_python_cmd` (remove, replace with import) |
| `scripts/stop_hook.py:36-68` | 36-68 | `should_regenerate` (test target) |
| `scripts/stop_hook.py:45-59` | 45-59 | Inline hash logic (replace with shared utility) |
| `scripts/stop_hook.py:115-125` | 115-125 | Python fallback loop needs `validate_python_cmd()` |
| `scripts/project_index.py:129-411` | 129-411 | `build_index` (god function to decompose) |
| `scripts/project_index.py:550-551` | 550-551 | MAX_ITERATIONS dead guard |
| `scripts/project_index.py:752-768` | 752-768 | Atomic write pattern (replace with shared utility) |
| `tests/test_security.py` | N/A | Update imports from `_validate_python_cmd` to `validate_python_cmd` |
| `tests/test_compression.py` | N/A | Add size verification assertion |

#### Files to Create

| File | Context |
|------|---------|
| `tests/test_shared_utils.py` | Tests for calculate_files_hash, atomic_write_json |
| `tests/test_build_index.py` | Integration tests for build_index |
| `tests/test_generate_index.py` | Tests for generate_index_at_size |
| `tests/test_staleness.py` | Tests for should_regenerate |
| `tests/test_brace_matching.py` | Tests for _find_matching_brace |
| `tests/test_ast_parser.py` | Tests for AstPythonParser |
| `tests/test_cross_file.py` | Tests for build_import_map, resolve_cross_file_edges |
| `scripts/cache_db.py` | SQLite cache backend for incremental indexing |
| `tests/test_cache_db.py` | Tests for cache operations |
| `scripts/query_engine.py` | Query engine core (who_calls, blast_radius, etc.) |
| `tests/test_query_engine.py` | Tests for query engine |
| `scripts/cli.py` | CLI interface for queries |
| `scripts/mcp_server.py` | Optional MCP server (FastMCP 2.2.x) |
| `scripts/pagerank.py` | PageRank symbol importance |
| `tests/test_pagerank.py` | Tests for PageRank |
| `tests/test_ast_grep.py` | Tests for ast-grep integration |

### Configuration

| Key | Value | Context |
|-----|-------|---------|
| `V2_AST_PARSER` | `1` (default enabled) / `0` (disable) | Feature flag for AST parser |
| `INDEX_TARGET_SIZE_K` | Env var | Target size for index generation |
| SQLite cache path | `~/.claude-code-project-index/cache.db` | Incremental indexing cache |
| SQLite PRAGMA | `journal_mode=WAL`, `synchronous=NORMAL` | Cache concurrency settings |
| `CURRENT_TOOL_VERSION` | `"1.0.0"` | Cache version invalidation key |

### Dependencies

| Package | Version | Classification | Milestone |
|---------|---------|---------------|-----------|
| Python stdlib: ast | 3.9+ | Required | M4 |
| Python stdlib: sqlite3 | 3.9+ | Required | M6 |
| Python stdlib: json | 3.9+ | Required | All |
| Python stdlib: pathlib | 3.9+ | Required | All |
| Python stdlib: hashlib | 3.9+ | Required | M1, M6 |
| Python stdlib: shutil | 3.9+ | Required | M1 |
| FastMCP | 2.2.x | Optional (M7 only) | M7 |
| pyperclip | Any | Optional (clipboard) | Existing |

### Constants

| Constant | Value | Location |
|----------|-------|----------|
| `MAX_FILES` | 10000 | `scripts/project_index.py` |
| `MAX_INDEX_SIZE` | 1MB | `scripts/project_index.py` |
| `MAX_TREE_DEPTH` | 5 | `scripts/project_index.py` |
| `DEFAULT_SIZE_K` | 50 | `scripts/i_flag_hook.py` |
| `CLAUDE_MAX_K` | 100 | `scripts/i_flag_hook.py` |
| `EXTERNAL_MAX_K` | 800 | `scripts/i_flag_hook.py` |
| `KEY_FILES` | `'f'` | Dense format (project_index.py) |
| `KEY_GRAPH` | `'g'` | Dense format (project_index.py) |
| `KEY_DOCS` | `'d'` | Dense format (project_index.py) |
| `KEY_DEPS` | `'deps'` | Dense format (project_index.py) |
| `LANG_LETTERS` | Abbreviation map | Dense format (project_index.py) |

### Tightened Validation Regex

```python
re.fullmatch(r'python\d*(\.\d+)?', basename)
```

Accepts: `python`, `python3`, `python3.12`, `python3.13`
Rejects: `python3-malicious`, `python3.12.1-extra`

### Test Baseline

- Current test count: 79 tests (after M3)
- Current test files: 17
- Target after all milestones: ~135 tests (79 + ~56 new)

### Research Document Paths

| Document | Path |
|----------|------|
| Python AST research | `codebase-deep-dive-20260317-094939/research-python-ast.md` |
| Cross-file resolution | `codebase-deep-dive-20260317-094939/research-cross-file-resolution.md` |
| Incremental indexing | `codebase-deep-dive-20260317-094939/research-incremental-indexing.md` |
| MCP code intelligence | `codebase-deep-dive-20260317-094939/research-mcp-code-intelligence.md` |
| Recommendations | `codebase-deep-dive-20260317-094939/08-recommendations.md` |

### Priority Issue Assignments

| ID | Priority | Issue | Milestone |
|----|----------|-------|-----------|
| I-01 | P0 | Replace Python regex parser with `ast` module | M4 |
| I-02 | P0 | Consolidate `_validate_python_cmd` to index_utils.py | M1 |
| I-03 | P0 | Tighten basename regex validation | M1 |
| I-04 | P1 | Cross-file call graph via import resolution | M5 |
| I-05 | P1 | Incremental indexing with per-file hash cache | M6 |
| I-06 | P1 | Extract shared utilities (hash calc, atomic write) | M1 |
| I-07 | P1 | MCP server for structured queries | M7 |
| I-08 | P2 | ast-grep augmentation for unlisted languages | M8 |
| I-09 | P2 | Decompose god functions (380-line parsers) | M3 |
| I-10 | P2 | Add integration tests for build_index, generate_index_at_size | M2 |
| I-11 | P3 | PageRank-based symbol importance ranking | M8 |
| I-12 | P3 | CLI query interface | M7 |

### Cross-File Schema Extension

New key added to index: `xg` (cross-file graph edges)
Format: `{"xg": [["file_a.py:func_x", "file_b.py:func_y", "call"], ...]}`
Backward-compatible: additive only, never replaces existing `g` key.

### Query Engine Methods

6 required methods: `who_calls`, `blast_radius`, `dead_code`, `dependency_chain`, `search_symbols`, `file_summary`
Performance target: <25ms p99 on 10k-file index

### Cache Schema

```sql
CREATE TABLE file_cache (
    path TEXT PRIMARY KEY,
    mtime REAL NOT NULL,
    size INTEGER NOT NULL,
    content_hash TEXT,
    lang TEXT,
    parse_result TEXT NOT NULL,
    tool_version TEXT NOT NULL,
    indexed_at REAL NOT NULL
);
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

Dirty threshold: >50% dirty files triggers full rebuild.

_Last Updated: 2026-03-17 10:35_
