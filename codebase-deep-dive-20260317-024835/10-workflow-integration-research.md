# Workflow Integration Research: Per-Project Code Indexing for Production Development

**Research Date:** 2026-03-17
**Context:** Biorelate Python projects, Claude Code with AA-MA methodology, 80+ skills, WSL2/Ubuntu 24.04
**Constraint:** Per-project indexing only (one PROJECT_INDEX.json per project root)

---

## 1. Multi-Project Index Management

### Per-Project Registry

Each project maintains its own `PROJECT_INDEX.json`. A lightweight global registry at `~/.claude-code-project-index/registry.json` tracks which projects are indexed and their freshness:

```json
{
  "projects": {
    "/path/to/project-a": {
      "last_generated": 1742000000.0,
      "files_hash": "a3f9c2b1",
      "file_count": 234,
      "git_branch": "main",
      "git_commit": "e58c78d"
    }
  }
}
```

**Hook integration:** Add `_update_global_registry()` call at `i_flag_hook.py:237` and `stop_hook.py:72`.

### Staleness Detection Improvements

Current hash misses three cases:

1. **Git branch switches** — Add `git rev-parse HEAD` output to hash input (one subprocess call, sub-ms)
2. **WSL2 mtime staleness** — Supplement mtime with 256-byte content sample for top 20 files
3. **No freshness TTL** — Add `_meta.max_age_hours` (configurable, default 24)

**Additional `_meta` fields:** `git_commit`, `git_branch`, `python_file_count`

### Incremental Indexing

Store per-file parse results keyed by `filepath:mtime:size` in `~/.claude-code-project-index/parse-cache/{project_hash}.json`. On next run, only re-parse files with changed keys.

**Expected speedup:** For <10% files changed, 90% reduction in parse time. The 30s timeout becomes irrelevant.

### Index History

Keep last 5 index snapshots in `.project-index-history/{git_commit}.json.gz`. Enables `index_diff.py --from HEAD~1 --to HEAD` showing functions added/removed/changed.

---

## 2. Development Workflow Integration

### Impact Analysis

**Query:** `query_index.py --blast-radius-file "src/auth/jwt.py"` — BFS on reverse dependency graph, returns files that transitively depend on target with depth.

**Current limitation:** Call graph is intra-file only. Cross-file resolution required for accurate impact analysis (see 09-code-intelligence-research.md).

**Interim approach:** Use `deps` graph as conservative proxy — if file_a imports file_b, changes to file_b potentially impact file_a.

### Dead Code Detection

**Reliable subset with current data:**
- Private functions (`_name`) with zero callers in `g` edge list
- Functions not appearing as callee anywhere AND not exported from `__init__.py`

**Full accuracy requires:** Cross-file call resolution.

**Query:** `query_index.py --dead-code --conservative`

### Code Review: PreToolUse Blast Radius Warning

A `PreToolUse` hook on `Write` tool calls that:
1. Captures the file being written
2. Queries `PROJECT_INDEX.json` for that file's dependents
3. If blast radius > 10 files, injects warning: "HIGH IMPACT WRITE: `src/core/auth.py` is imported by 23 files."

### Refactoring Safety

`query_index.py --callers-of "function_name"` returns all known callers. If empty (after cross-file resolution), function is safe to remove. Integration with `safe-refactoring` skill as a pre-condition check.

### Skills Integration

| Skill | Index Query | What It Enables |
|-------|------------|-----------------|
| `impact-analysis` | `--blast-radius-file {file}` | Automated dependency tracing |
| `system-mapping` | `tree` + `dir_purposes` + `deps` | Points 1-3 of 5-point pre-flight |
| `safe-refactoring` | `--callers-of {func}` | Pre-condition removal check |
| New: `index-query` | All queries | Structured index access |

---

## 3. Auto-Indexing Improvements

### Git Hooks

| Hook | Trigger | Command |
|------|---------|---------|
| `post-commit` | After commit | `python3 project_index.py &` (background) |
| `post-checkout` | Branch switch | Same (only if `$3` = 1) |
| `post-merge` | After merge/pull | Same |

Install via `scripts/install_git_hooks.sh` per-project. Background (`&`) means non-blocking.

### Watch Mode

**Preferred (Ubuntu 24.04):** `inotifywait` filesystem watcher:
```bash
while inotifywait -r -q -e modify,create,delete,move \
    --exclude '(\.git|node_modules|__pycache__|PROJECT_INDEX\.json)' "$ROOT"; do
    python3 ~/.claude-code-project-index/scripts/project_index.py
done
```

**Fallback (pure stdlib):** Polling with `calculate_files_hash()` every 10 seconds.

**WSL2 note:** `inotifywait` works for files modified within WSL2. VS Code running inside WSL2 triggers inotify correctly.

### Branch-Aware Indexing

Simple approach: Store `git_branch` in `_meta`. If branch differs from `_meta.git_branch` on next `-i`, force regeneration. Combined with `post-checkout` git hook running in background, branch switches produce fresh indexes.

---

## 4. Query Interface

### CLI: `scripts/query_index.py`

```bash
python3 query_index.py --callers-of "function_name"
python3 query_index.py --callees-of "function_name"
python3 query_index.py --blast-radius-file "src/auth/jwt.py"
python3 query_index.py --dead-code --conservative
python3 query_index.py --call-chain-from "main" --to "verify_token"
python3 query_index.py --dependencies-of "src/api/routes.py" --transitive
python3 query_index.py --entry-points
python3 query_index.py --stats
python3 query_index.py --format json|text|markdown
```

**Performance:** `json.load()` on 200KB index + BFS traversal completes in <50ms.

### MCP Server: `scripts/mcp_server.py`

Expose query engine as MCP tools (JSON-RPC 2.0 over stdio). Register in `settings.json`:
```json
{"mcpServers": {"project-index": {"command": "python3", "args": ["~/.../mcp_server.py"]}}}
```

Tools: `index_query_callers`, `index_query_blast_radius`, `index_query_dead_code`, `index_query_call_chain`, `index_refresh`

**Benefit:** Claude queries directly without `-i` flag or subagent — zero context token overhead.

---

## 5. Enhanced Index Content

| Enhancement | Effort | Value | Phase |
|-------------|--------|-------|-------|
| **Structured param types** | Low | Type-aware queries | 5 |
| **Return types** | Low | API documentation | 5 |
| **Docstring quality score** (0-3) | Low | Code quality reports | 5 |
| **Proxy complexity** (branch keyword count) | Low | Risk assessment | 5 |
| **Change frequency** (git log, single call) | Low | Hot file detection | 5 |
| **Module docstrings** | Low | Onboarding | 5 |
| **Entry point detection** | Low | Architecture maps | 5 |
| **Circular dependency detection** | Medium | Import error prevention | 2 |
| **Test coverage mapping** | Medium | Coverage gaps | 5+ |

---

## 6. Production Reliability

### Atomic Writes (Critical)

Replace `output_path.write_text()` with `tempfile.mkstemp()` + `os.replace()` (POSIX atomic). Add `fcntl.flock()` for read-modify-write in `i_flag_hook.py`.

### Index Validation

`validate_index(index)` checks required keys (`f`, `g`, `_meta`), types, and `files_hash` presence. Called in `should_regenerate_index()` — corrupt index forces regeneration.

### Parse Error Reporting

Collect parse errors in `build_index()`, expose in `_meta.parse_errors`. Report in `print_summary()`.

### WSL2: Add `clip.exe` Clipboard

`clip.exe` is natively available in WSL2 for Windows clipboard access. Add `_try_clip_exe(content)` to clipboard chain between pyperclip and file fallback. Promote to position 2 if WSL2 detected via `/proc/version`.

### Smart Stop Hook

Import `should_regenerate_index()` logic into `stop_hook.py`. Skip regeneration if index is already fresh. Eliminates timeout issues entirely.

---

## 7. Implementation Roadmap

| Phase | Timing | Deliverables |
|-------|--------|-------------|
| **0: Security** | Days 1-2 | Remove hardcoded IPs, validate .python_cmd, atomic writes, replace bare excepts |
| **1: Query Interface** | Days 3-5 | `query_index.py`, git metadata in `_meta`, index validation |
| **2: Performance** | Week 2 | Parse cache, smart stop hook, circular dep detection |
| **3: Multi-Project** | Week 3 | Global registry, index history, index diff |
| **4: Git Integration** | Week 4 | Git hooks installer, watch mode daemon |
| **5: Enhanced Content** | Month 2 | Cross-file calls, complexity, change frequency, types |
| **6: MCP Server** | Month 2 | JSON-RPC server, `settings.json` registration |
| **7: Skills Integration** | Month 3 | Updated agent, index-query skill, PreToolUse blast radius hook |

### AA-MA Integration Points

| AA-MA Phase | Index Integration |
|-------------|-------------------|
| Milestone planning | `--blast-radius-file` → `reference.md` impact analysis |
| Implementation | PreToolUse Write hook → automatic blast radius warnings |
| Sub-step completion | `index_diff.py` → sub-step result evidence in `tasks.md` |
| Milestone completion | `index_diff.py` → code-level evidence in `provenance.log` |

---

## Key Finding: WSL2 `clip.exe`

The most reliable clipboard method for Stephen's WSL2 environment (`clip.exe`) is entirely missing from the current transport chain. This is a quick win (add between pyperclip and file fallback, promote to position 2 if WSL2 detected).
