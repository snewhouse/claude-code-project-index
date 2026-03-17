# Claude Code Project Index — Usage Guide

Complete guide to the upgraded project indexing system (v0.2.0-beta, M1–M8).

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Core Usage: The -i Flag](#core-usage-the--i-flag)
- [Index Generation](#index-generation)
- [Incremental Indexing](#incremental-indexing)
- [Query Engine CLI](#query-engine-cli)
- [AST Parser and Feature Flag](#ast-parser-and-feature-flag)
- [Multi-Language Support](#multi-language-support)
- [MCP Server (Optional)](#mcp-server-optional)
- [Architecture Overview](#architecture-overview)
- [Configuration Reference](#configuration-reference)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Overview

**claude-code-project-index** gives Claude Code architectural awareness of any codebase. It generates a compressed `PROJECT_INDEX.json` containing function signatures, call graphs, cross-file dependencies, and project structure — then injects this context into Claude sessions via hooks.

### What Changed in the Upgrade (M1–M8)

| Milestone | Feature | Impact |
|-----------|---------|--------|
| M1 | Foundation & Security | Consolidated shared utilities, tightened validation regex |
| M2 | Critical Test Coverage | 46 → 70 tests, covering previously untested functions |
| M3 | God Function Decomposition | All functions ≤100 lines (18 helpers extracted) |
| M4 | Python AST Parser | `ast.parse()` replaces regex for 100% accurate Python parsing |
| M5 | Cross-File Resolution | Import-based cross-file call graph edges (`xg` key) |
| M6 | Incremental Indexing | SQLite cache — only re-parses changed files |
| M7 | Query Engine + MCP Server | 6 structural queries + CLI + optional MCP server |
| M8 | Multi-Language + Polish | ast-grep for Go/Rust/Java/Ruby, PageRank importance scores |

**Final test count:** 135 tests (from 46 baseline).

---

## Installation

### Fresh Install

```bash
# From the repository
cd ~/biorelate/projects/gitlab/claude-code-project-index
bash install.sh
```

### Update Existing Installation

The same command updates an existing install — it detects the previous version and re-installs:

```bash
cd ~/biorelate/projects/gitlab/claude-code-project-index
bash install.sh
```

### What Gets Installed

| Location | Contents |
|----------|----------|
| `~/.claude-code-project-index/scripts/` | All Python scripts (index generation, hooks, query engine, cache, etc.) |
| `~/.claude-code-project-index/.python_cmd` | Saved Python interpreter path |
| `~/.claude-code-project-index/cache.db` | SQLite cache for incremental indexing (created on first use) |
| `~/.claude/settings.json` | Hook configuration (UserPromptSubmit + Stop hooks) |
| `~/.claude/commands/index.md` | The `/index` slash command |
| `~/.claude/agents/index-analyzer.md` | Subagent for deep index analysis |

### Prerequisites

- Python 3.9+ (required for `ast.unparse()`)
- `git` and `jq` (for installation)
- Claude Code with hooks support
- macOS or Linux (including WSL2)

### Optional Dependencies

| Package | Purpose | Install |
|---------|---------|---------|
| `sg` (ast-grep) | Full parsing for Go, Rust, Java, Ruby | `pip install ast-grep-cli` or `cargo install ast-grep` |
| `fastmcp` | MCP server for Claude tool integration | `pip install fastmcp` |
| `pyperclip` | Clipboard support (fallback) | `pip install pyperclip` |
| `xclip` | Clipboard on Linux/X11 | `sudo apt install xclip` |

---

## Core Usage: The -i Flag

The primary interface is the `-i` flag added to any Claude Code prompt.

### Basic Usage

```bash
# Add -i to any prompt — index is created/updated automatically
claude "fix the auth bug -i"

# The -i flag is stripped from your prompt before Claude sees it
# Claude receives: "fix the auth bug" + architectural context
```

### With Size Targets

```bash
# Default: 50k tokens (remembered per project)
claude "refactor database code -i"

# Custom size: target ~75k tokens
claude "analyze architecture -i75"

# Size is remembered — next -i uses the same target
claude "continue refactoring -i"   # Still uses 75k
```

### Clipboard Export Mode (-ic)

For external AI tools with larger context windows (Gemini, ChatGPT, etc.):

```bash
# Export to clipboard (up to 200k tokens)
claude "analyze entire codebase -ic200"

# Maximum clipboard export (800k tokens)
claude "full architecture review -ic800"
```

Content is copied via: OSC 52 (SSH) → tmux buffer → xclip (X11) → pyperclip → file fallback.

### How It Works Under the Hood

1. You type: `claude "fix bug -i50"`
2. **UserPromptSubmit hook** (`i_flag_hook.py`) intercepts the prompt
3. Hook detects `-i50`, checks if index needs regeneration (via file hash)
4. If stale: runs `project_index.py` with `INDEX_TARGET_SIZE_K=50`
5. Index generates with AST parser, cross-file resolution, PageRank
6. Hook injects context telling Claude to use the `index-analyzer` subagent
7. Subagent reads `PROJECT_INDEX.json` and provides targeted code intelligence
8. Claude proceeds with your original prompt + architectural awareness

### Stop Hook (Auto-Refresh)

When a Claude session ends, the **Stop hook** (`stop_hook.py`) checks if the index is stale and refreshes it silently. This ensures the index captures any changes made during the session.

---

## Index Generation

### Manual Generation

```bash
# From any project directory
python3 ~/.claude-code-project-index/scripts/project_index.py

# Or use the /index command in Claude
/index
```

### Output: PROJECT_INDEX.json

The generated index uses compressed keys for token efficiency:

| Key | Full Name | Contents |
|-----|-----------|----------|
| `at` | timestamp | Generation timestamp |
| `root` | project root | Absolute path to project |
| `tree` | directory tree | ASCII tree structure (top 20 entries) |
| `f` | files | Parsed file signatures (abbreviated paths) |
| `g` | call graph | Intra-file call edges `[[caller, callee], ...]` |
| `xg` | cross-file graph | Cross-file call edges `[[file:func, file:func, "call"], ...]` |
| `d` | documentation | Markdown section headers |
| `deps` | dependencies | Import-based dependency graph |
| `_meta` | metadata | Generation info, symbol importance scores |

### File Entry Format (Dense)

Each file in `f` is stored as: `[lang_letter, [func_signatures...], {class_data}]`

Function signature format: `name:line:signature:calls:docstring`

Example:
```json
{
  "f": {
    "s/project_index.py": ["p", [
      "build_index:130:(root_dir: str) -> Tuple[Dict, int]:_discover_files,_parse_all_files:Build the enhanced index",
      "main:690:():build_index,compress_if_needed:Run the enhanced indexer"
    ], {}]
  }
}
```

### Path Abbreviations

| Prefix | Expanded |
|--------|----------|
| `s/` | `scripts/` |
| `sr/` | `src/` |
| `t/` | `tests/` |

---

## Incremental Indexing

Incremental mode only re-parses files that have changed since the last index generation.

### Usage

```bash
# Incremental mode — uses SQLite cache
python3 ~/.claude-code-project-index/scripts/project_index.py --incremental
```

### How It Works

1. **Open cache** at `~/.claude-code-project-index/cache.db`
2. **PRAGMA quick_check** verifies integrity (deletes and recreates if corrupt)
3. **Version check**: if tool version changed, invalidate all cache entries
4. For each file, **two-tier dirty detection**:
   - **Tier 1 (fast)**: Compare mtime + file size against cached values
   - **Tier 2 (accurate)**: If mismatch, compute SHA-256 hash and compare
5. Only dirty files are re-parsed; clean files use cached results
6. **Purge** removed files from cache
7. If **>50% files dirty**, fall back to full rebuild (cache is mostly useless)

### Cache Schema

```sql
CREATE TABLE file_cache (
    path TEXT PRIMARY KEY,
    mtime REAL NOT NULL,
    size INTEGER NOT NULL,
    content_hash TEXT,
    lang TEXT,
    parse_result TEXT NOT NULL,    -- JSON blob of parse output
    tool_version TEXT NOT NULL,
    indexed_at REAL NOT NULL
);

CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

### Cache Location

- Default: `~/.claude-code-project-index/cache.db`
- SQLite WAL mode for concurrent read safety
- Automatically recreated if corrupt

---

## Query Engine CLI

The query engine answers structural questions about your codebase using the generated index.

### Prerequisites

The index must exist: run `python3 scripts/project_index.py` first.

### Commands

#### Who Calls a Symbol

Find all callers of a function (direct and transitive):

```bash
# Direct callers only
python3 scripts/cli.py query who-calls build_index

# Transitive callers (2 levels deep)
python3 scripts/cli.py query who-calls validate_python_cmd --depth 2
```

#### Blast Radius

Estimate the impact of changing a function:

```bash
python3 scripts/cli.py query blast-radius extract_python_signatures --depth 3
```

Output groups callers by depth level, showing how changes ripple through the codebase.

#### Dead Code Detection

Find functions that are never called by any other function:

```bash
python3 scripts/cli.py query dead-code
```

Returns a list of `file:function` identifiers with zero incoming calls.

#### Dependency Chain

Trace import dependencies of a file:

```bash
python3 scripts/cli.py query deps scripts/i_flag_hook.py --depth 5
```

#### Symbol Search

Search for symbols by regex pattern:

```bash
# Find all functions containing "parse"
python3 scripts/cli.py query search "parse"

# Find functions starting with "test_"
python3 scripts/cli.py query search "^test_" --max 20

# Case-insensitive by default
python3 scripts/cli.py query search "BUILD"
```

#### File Summary

Summarize a file's contents:

```bash
python3 scripts/cli.py query summary s/project_index.py
```

Returns: language, function list, class list, imports, and purpose.

### Output Format

All commands output **JSON** to stdout, suitable for piping:

```bash
# Pretty-print dead code
python3 scripts/cli.py query dead-code | python3 -m json.tool

# Count dead code symbols
python3 scripts/cli.py query dead-code | python3 -c "import json,sys; print(len(json.load(sys.stdin)))"

# Find callers and pipe to jq
python3 scripts/cli.py query who-calls build_index | jq '.[]'
```

---

## AST Parser and Feature Flag

### What Changed

The Python parser was upgraded from regex-based to AST-based:

| Aspect | Old (Regex) | New (AST) |
|--------|-------------|-----------|
| Accuracy | ~90% (fragile on complex syntax) | 100% (same parser as CPython) |
| Multi-line signatures | Sometimes missed | Always correct |
| Nested functions | Incorrectly captured | Correctly excluded |
| Complex defaults | Often broken | Fully supported |
| Type annotations | Regex-approximated | Precisely extracted via `ast.unparse()` |
| Decorators | Basic detection | Full capture |

### Feature Flag

The AST parser is **enabled by default**. To disable it:

```bash
# Use regex parser instead (for debugging or comparison)
V2_AST_PARSER=0 python3 scripts/project_index.py

# Explicitly enable AST parser (default)
V2_AST_PARSER=1 python3 scripts/project_index.py
```

The flag is checked at **call time** inside `parse_file()`, not at import time. This means you can toggle it per-test without module reloads.

### SyntaxError Fallback

When the AST parser encounters a `SyntaxError` (e.g., partial or invalid Python files), it automatically falls back to the regex parser. This ensures robustness — you always get results, even for malformed files.

### Minimum Python Version

The AST parser requires **Python 3.9+** for full accuracy (uses `ast.unparse()`). On Python 3.8, `ast.unparse()` does not exist — the `_ast_unparse_safe()` wrapper catches the `AttributeError` and returns empty strings, producing degraded output. For best results on Python 3.8, disable the AST parser explicitly:

```bash
V2_AST_PARSER=0 python3 scripts/project_index.py
```

Note: The install script and README still say "Python 3.8+" as the minimum because the tool runs on 3.8 — only the AST parser feature is degraded. The regex parser works on any Python 3.8+ version.

---

## Multi-Language Support

### Built-in Parsers (Always Available)

| Language | Extensions | Parser |
|----------|-----------|--------|
| Python | `.py` | AST-based (with regex fallback) |
| JavaScript | `.js`, `.jsx` | Regex-based |
| TypeScript | `.ts`, `.tsx` | Regex-based |
| Shell | `.sh`, `.bash` | Regex-based |

### ast-grep Parsers (When `sg` Installed)

If `sg` (ast-grep) is on your PATH, these languages get **full signature extraction**:

| Language | Extension | sg Pattern |
|----------|-----------|------------|
| Go | `.go` | `func $NAME($$$PARAMS) $$$RET { $$$BODY }` |
| Rust | `.rs` | `fn $NAME($$$PARAMS) $$$RET { $$$BODY }` |
| Java | `.java` | `$MOD $RET $NAME($$$PARAMS) { $$$BODY }` |
| Ruby | `.rb` | `def $NAME($$$PARAMS) $$$BODY end` |

Check if `sg` is available:

```bash
sg --version   # Should show ast-grep version
```

Install `sg`:

```bash
# Via pip
pip install ast-grep-cli

# Via cargo
cargo install ast-grep

# Via npm
npm install -g @ast-grep/cli
```

### File Tracking (All Languages)

Even without parsers, these file types are **tracked** (listed in the index but not parsed for signatures):

Go, Rust, Java, C, C++, Ruby, PHP, Swift, Kotlin, Scala, C#, SQL, R, Lua, Objective-C, Elixir, Julia, Dart, Vue, Svelte, JSON, HTML, CSS.

---

## MCP Server (Optional)

The MCP server wraps the query engine as tools that Claude can invoke directly during conversations.

### Prerequisites

```bash
pip install fastmcp
```

### Running the Server

```bash
python3 ~/.claude-code-project-index/scripts/mcp_server.py
```

### Configuring in Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "project-index-query": {
      "command": "python3",
      "args": [
        "/home/YOUR_USERNAME/.claude-code-project-index/scripts/mcp_server.py"
      ]
    }
  }
}
```

### Available MCP Tools

| Tool | Description | Read-Only |
|------|-------------|-----------|
| `who_calls(symbol, depth)` | Find callers of a symbol | Yes |
| `blast_radius(symbol, max_depth)` | Estimate change impact | Yes |
| `dead_code()` | Find uncalled functions | Yes |
| `dependency_chain(file_path, max_depth)` | Trace imports | Yes |
| `search_symbols(pattern, max_results)` | Regex symbol search | Yes |
| `file_summary(file_path)` | Summarize file contents | Yes |

All tools are marked `readOnlyHint: true` — they never modify the index.

### Without FastMCP

If FastMCP is not installed, the MCP server exits gracefully with a helpful message:

```
Error: FastMCP not installed. Install with: pip install fastmcp
```

The query engine and CLI work independently — the MCP server is purely optional.

---

## Architecture Overview

### System Flow

```
User Prompt ("fix bug -i")
       │
       ▼
┌─────────────────┐
│ UserPromptSubmit │  i_flag_hook.py
│     Hook         │  Detects -i flag, checks staleness
└───────┬─────────┘
        │ (if stale)
        ▼
┌─────────────────┐
│  project_index   │  project_index.py
│    .py           │  Orchestrates: discover → parse → graph → compress
└───────┬─────────┘
        │ (delegates)
        ▼
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│  index_utils.py │────▶│  cache_db.py │     │ pagerank.py │
│  (parsers)      │     │  (SQLite)    │     │ (scoring)   │
└─────────────────┘     └──────────────┘     └─────────────┘
        │
        ▼
┌─────────────────┐
│ PROJECT_INDEX    │
│    .json         │  Output: compressed index with call graphs
└───────┬─────────┘
        │
   ┌────┴────┐
   ▼         ▼
┌──────┐  ┌──────────┐
│ CLI  │  │   MCP    │
│      │  │  Server  │
└──────┘  └──────────┘
```

### Key Files

| File | Purpose |
|------|---------|
| `scripts/project_index.py` | Main index builder (orchestrator) |
| `scripts/index_utils.py` | All parsers + shared utilities |
| `scripts/i_flag_hook.py` | UserPromptSubmit hook (detects -i flag) |
| `scripts/stop_hook.py` | Stop hook (auto-refresh on session end) |
| `scripts/cache_db.py` | SQLite cache for incremental indexing |
| `scripts/query_engine.py` | QueryEngine class (6 query methods) |
| `scripts/cli.py` | CLI interface for queries |
| `scripts/mcp_server.py` | Optional MCP server (requires FastMCP) |
| `scripts/pagerank.py` | PageRank symbol importance scoring |

---

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `V2_AST_PARSER` | `1` | Set to `0` to disable AST parser, use regex |
| `INDEX_TARGET_SIZE_K` | (set by hook) | Target index size in thousands of tokens |

### Constants (project_index.py)

| Constant | Value | Description |
|----------|-------|-------------|
| `MAX_FILES` | 10,000 | Maximum files to index |
| `MAX_INDEX_SIZE` | 1 MB | Default maximum index size |
| `MAX_TREE_DEPTH` | 5 | Directory tree depth limit |

### Constants (i_flag_hook.py)

| Constant | Value | Description |
|----------|-------|-------------|
| `DEFAULT_SIZE_K` | 50 | Default token target for `-i` |
| `CLAUDE_MAX_K` | 100 | Maximum for `-i` mode |
| `EXTERNAL_MAX_K` | 800 | Maximum for `-ic` mode |

### Constants (cache_db.py)

| Constant | Value | Description |
|----------|-------|-------------|
| `CURRENT_TOOL_VERSION` | `"1.0.0"` | Cache version — bump to invalidate all caches |
| `DIRTY_THRESHOLD` | 0.5 | If >50% dirty, do full rebuild |

---

## Testing

### Run the Full Suite

```bash
cd ~/biorelate/projects/gitlab/claude-code-project-index

# All 135 tests
python3 -m pytest tests/ -v

# Quick summary
python3 -m pytest tests/ -q
```

### Run Specific Test Categories

```bash
# Parser tests (Python, JS, Shell)
python3 -m pytest tests/test_parsers.py -v

# AST parser tests
python3 -m pytest tests/test_ast_parser.py -v

# Query engine tests
python3 -m pytest tests/test_query_engine.py -v

# Cache/incremental indexing tests
python3 -m pytest tests/test_cache_db.py -v

# Security tests
python3 -m pytest tests/test_security.py -v

# Cross-file resolution tests
python3 -m pytest tests/test_cross_file.py -v

# Integration tests (build_index end-to-end)
python3 -m pytest tests/test_build_index.py -v
```

### Test File Inventory

| File | Tests | Covers |
|------|-------|--------|
| `test_parsers.py` | 8 | Python/JS/Shell parser characterization |
| `test_ast_parser.py` | 13 | AST parser: functions, classes, async, decorators, dataclasses, enums |
| `test_build_index.py` | 5 | End-to-end build_index with tmp_path |
| `test_generate_index.py` | 5 | generate_index_at_size (mocked subprocess) |
| `test_staleness.py` | 5 | should_regenerate (hash comparison) |
| `test_compression.py` | 3 | Compression reduces size, fits target, idempotent |
| `test_cross_file.py` | 9 | Import map + cross-file edge resolution |
| `test_cache_db.py` | 10 | SQLite cache: create, dirty detection, versioning, corruption |
| `test_query_engine.py` | 10 | All 6 query methods |
| `test_brace_matching.py` | 9 | JS brace matching helpers |
| `test_security.py` | 7 | Validation, no hardcoded IPs, no author paths |
| `test_shared_utils.py` | 6 | calculate_files_hash, atomic_write_json |
| `test_atomic_writes.py` | 5 | Atomic write patterns |
| `test_flag_parsing.py` | 4 | -i/-ic flag parsing |
| `test_clipboard.py` | 5 | Clipboard transports |
| `test_registry.py` | 8 | Parser registry, AST default, dense format |
| `test_quality.py` | 5 | No bare excepts, no dead code |
| `test_utils.py` | 5 | File indexing utilities |
| `test_ast_grep.py` | 6 | ast-grep integration (mocked) |
| `test_pagerank.py` | 7 | PageRank: empty, chain, hub, cycle, normalization |

---

## Troubleshooting

### Index Not Creating

```bash
# Check Python version (need 3.9+)
python3 --version

# Verify hooks are configured
cat ~/.claude/settings.json | grep i_flag_hook

# Manual generation (see errors)
python3 ~/.claude-code-project-index/scripts/project_index.py

# Check the .python_cmd file
cat ~/.claude-code-project-index/.python_cmd
```

### -i Flag Not Working

```bash
# Re-run installer to fix hooks
cd ~/biorelate/projects/gitlab/claude-code-project-index
bash install.sh

# Test hook manually
echo '{"prompt": "test -i"}' | python3 ~/.claude-code-project-index/scripts/i_flag_hook.py
```

### Incremental Indexing Issues

```bash
# Delete cache and start fresh
rm ~/.claude-code-project-index/cache.db

# Check cache integrity manually
python3 -c "
import sqlite3
conn = sqlite3.connect('~/.claude-code-project-index/cache.db')
print(conn.execute('PRAGMA quick_check').fetchone())
print('Files cached:', conn.execute('SELECT COUNT(*) FROM file_cache').fetchone()[0])
"
```

### Query Engine Errors

```bash
# Regenerate index first
python3 ~/.claude-code-project-index/scripts/project_index.py

# Verify index is valid JSON
python3 -c "import json; json.load(open('PROJECT_INDEX.json')); print('OK')"

# Test query engine directly
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from query_engine import QueryEngine
qe = QueryEngine.from_file('PROJECT_INDEX.json')
print('Files:', len(qe.files))
print('Edges:', len(qe.call_graph))
"
```

### AST Parser Issues

```bash
# Disable AST parser temporarily
V2_AST_PARSER=0 python3 scripts/project_index.py

# Compare AST vs regex output
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from index_utils import extract_python_signatures, extract_python_signatures_ast
code = open('scripts/project_index.py').read()
regex = extract_python_signatures(code)
ast_r = extract_python_signatures_ast(code)
print('Regex functions:', len(regex.get('functions', {})))
print('AST functions:', len(ast_r.get('functions', {})))
"
```

---

## Quick Reference Card

| Task | Command |
|------|---------|
| Install / update | `cd ~/biorelate/projects/gitlab/claude-code-project-index && bash install.sh` |
| Generate index | `python3 scripts/project_index.py` |
| Incremental index | `python3 scripts/project_index.py --incremental` |
| Use with Claude | `claude "your task -i"` |
| Clipboard export | `claude "your task -ic200"` |
| Who calls X | `python3 scripts/cli.py query who-calls <symbol>` |
| Blast radius | `python3 scripts/cli.py query blast-radius <symbol>` |
| Dead code | `python3 scripts/cli.py query dead-code` |
| Dependencies | `python3 scripts/cli.py query deps <file>` |
| Search symbols | `python3 scripts/cli.py query search <pattern>` |
| File summary | `python3 scripts/cli.py query summary <file>` |
| Disable AST parser | `V2_AST_PARSER=0 python3 scripts/project_index.py` |
| Run tests | `python3 -m pytest tests/ -v` |
| Start MCP server | `python3 scripts/mcp_server.py` |
| Uninstall | `~/.claude-code-project-index/uninstall.sh` |
