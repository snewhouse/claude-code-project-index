# project-index-upgrade Plan

**Objective:** Address ALL P0-P3 issues from the codebase deep-dive and implement Foundation & Security, Python AST Parser, cross-file resolution, incremental indexing, query engine, and multi-language augmentation.
**Owner:** AI + Stephen Newhouse
**Created:** 2026-03-17
**Last Updated:** 2026-03-17

## Executive Summary

Address ALL P0-P3 issues from the codebase deep-dive (12 issues) and implement Phases 1-5 organized into 8 dependency-driven milestones. TDD throughout with the Python regex parser decomposed for maintainability, then replaced by an `ast.NodeVisitor`-based parser targeting 99%+ accuracy. Tech stack is Python 3.9+ stdlib only (ast, sqlite3, json, pathlib, hashlib, shutil) with optional FastMCP 2.2.x for MCP server (Milestone 7 only).

## Implementation Steps

### Context

The codebase deep-dive (2026-03-17) identified 12 prioritized issues across P0-P3 severity levels, organized into a 5-phase roadmap. This plan covers all priorities and Phases 1-5, organized by technical dependencies into 8 milestones.

### Priority Matrix (from 08-recommendations.md)

| Priority | Issue | Milestone |
|----------|-------|-----------|
| P0 | Replace Python regex parser with `ast` module | M4 |
| P0 | Consolidate `_validate_python_cmd` to index_utils.py | M1 |
| P0 | Tighten basename regex validation | M1 |
| P1 | Cross-file call graph via import resolution | M5 |
| P1 | Incremental indexing with per-file hash cache | M6 |
| P1 | Extract shared utilities (hash calc, atomic write) | M1 |
| P1 | MCP server for structured queries | M7 |
| P2 | ast-grep augmentation for unlisted languages | M8 |
| P2 | Decompose god functions (380-line parsers) | M3 |
| P2 | Add integration tests for build_index, generate_index_at_size | M2 |
| P3 | PageRank-based symbol importance ranking | M8 |
| P3 | CLI query interface | M7 |

### Milestone Dependency Graph

```
M1 (Foundation) --+--> M2 (Tests) --> M3 (Decompose) --> M4 (AST Parser)
                  |                                              |
                  |                                              v
                  |                                       M5 (Cross-File)
                  |                                              |
                  +--------------------> M6 (Incremental) ------>|
                                                                 v
                                                          M7 (Query+MCP)
                                                                 |
                                                                 v
                                                          M8 (Multi-Lang)
```

---

### Milestone 1: Foundation & Security (Complexity: 35%, Effort: 2-3 hours)

**Goal:** Eliminate all DRY violations, fix security issues, clean dead code, fix type annotations.
**Issues Covered:** P0 security (2), P1 DRY (3), P1 dead code cleanup, P2 type fixes

**Acceptance Criteria:**
- `_validate_python_cmd` exists in exactly ONE file (`index_utils.py`)
- Basename regex rejects `python3-malicious`, accepts `python3`, `python3.12`
- `calculate_files_hash()` is a shared function in `index_utils.py`
- `atomic_write_json()` is a shared function in `index_utils.py`
- `shutil.which('xclip')` replaces `subprocess.run(['which', 'xclip'], ...)`
- All 3 dead code instances removed
- All `any` type annotations replaced with `Any`
- All existing 46 tests pass
- Zero import of `_validate_python_cmd` from local scope in i_flag_hook.py or stop_hook.py

**Risks & Mitigations:**
1. Import cycle risk when moving functions to index_utils.py -- Mitigate: index_utils has no imports from hook files
2. Regex tightening breaks valid Python paths -- Mitigate: Test with python3, python3.12, python3.13
3. Atomic write behavior change -- Mitigate: Existing test_atomic_writes.py covers this

**Rollback:** `git revert HEAD~N..HEAD`

**Tasks:**
- Task 1.1: Consolidate `_validate_python_cmd` to index_utils.py with tightened regex
- Task 1.2: Extract `calculate_files_hash()` as shared utility
- Task 1.3: Extract `atomic_write_json()` as shared utility
- Task 1.4: Replace `which xclip` with `shutil.which`
- Task 1.5: Clean up dead code (MAX_ITERATIONS guard, ssh_file_large branch, duplicate __pycache__)
- Task 1.6: Fix type annotations (`any` to `Any` in 4 locations)

**Tests:** New security tests, shared utils tests, all 46 existing tests must pass.

---

### Milestone 2: Critical Test Coverage (Complexity: 40%, Effort: 2-3 hours)

**Goal:** Close critical testing gaps identified in the deep-dive. TDD foundation for subsequent milestones.
**Issues Covered:** P0 (build_index test), P2 (integration tests)
**Dependencies:** M1

**Acceptance Criteria:**
- `build_index()` has end-to-end integration test with tmp_path
- `generate_index_at_size()` has tests (mocked subprocess)
- `should_regenerate()` has tests
- `compress_if_needed()` test verifies output fits target size
- Test count increases from 46 to 56+
- All tests pass

**Risks & Mitigations:**
1. build_index requires git repo -- Mitigate: use tmp_path with `.git/` stub
2. generate_index_at_size spawns subprocess -- Mitigate: mock subprocess.run
3. Tests may be flaky with file timestamps -- Mitigate: use controlled fixtures

**Rollback:** `git revert HEAD~N..HEAD`

**Tasks:**
- Task 2.1: Integration test for `build_index`
- Task 2.2: Tests for `generate_index_at_size`
- Task 2.3: Tests for `should_regenerate`
- Task 2.4: Fix compress test to verify output fits target

**Tests:** ~10 new tests, total 56+.

---

### Milestone 3: God Function Decomposition (Complexity: 55%, Effort: 3-4 hours)

**Goal:** Break apart the 3 god functions into testable, composable helpers. Includes Python parser decomposition.
**Issues Covered:** P2 (god function decomposition), P2 (brace-counting helper)
**Dependencies:** M1, M2

**Acceptance Criteria:**
- `extract_python_signatures` decomposed into `_parse_python_imports`, `_parse_python_classes`, `_parse_python_functions` helpers
- `extract_javascript_signatures` decomposed similarly, with `_find_matching_brace` extracted (replaces 5 inline instances)
- `build_index` decomposed into `_discover_files`, `_parse_all_files`, `_build_call_graph`, `_build_dep_graph`
- No function exceeds 100 lines
- All 56+ tests still pass
- New helpers have targeted unit tests

**Risks & Mitigations:**
1. Decomposition changes subtle behavior -- Mitigate: Characterization tests lock current behavior before refactoring
2. Brace-counting extraction changes JS parser behavior -- Mitigate: Run full test suite after each extraction
3. Python decomposition is soon replaced by AST -- Mitigate: User explicitly requested this; decomposed helpers inform AST parser design

**Rollback:** `git revert HEAD~N..HEAD`

**Tasks:**
- Task 3.1: Extract `_find_matching_brace` from JS parser
- Task 3.2: Decompose `extract_python_signatures`
- Task 3.3: Decompose `extract_javascript_signatures`
- Task 3.4: Decompose `build_index`

**Tests:** ~8 new tests.

---

### Milestone 4: Python AST Parser (Complexity: 70%, Effort: 3-4 hours)

**Goal:** Replace 70%-accurate regex Python parser with 99%-accurate `ast.NodeVisitor` implementation. Single highest-ROI improvement.
**Issues Covered:** P0 (accuracy 70% to 99%)
**Dependencies:** M1, M2, M3
**Research:** `codebase-deep-dive-20260317-094939/research-python-ast.md`

**Acceptance Criteria:**
- New `AstPythonParser` class using `ast.NodeVisitor`
- Registered in `PARSER_REGISTRY` for `.py` extension
- `SyntaxError` fallback to existing regex parser
- Feature flag `V2_AST_PARSER=0` env var disables new parser
- All existing characterization tests pass (identical or better output)
- New tests for: nested functions, complex defaults, generics, async, decorators, dataclasses
- Minimum Python version: 3.9 (for `ast.unparse()`)
- Output format compatible with existing dense format conversion

**Risks & Mitigations:**
1. ast.parse fails on partial/invalid Python -- Mitigate: SyntaxError fallback to regex parser
2. Output format mismatch with existing code -- Mitigate: Output schema matches current `{functions, classes, imports}` dict
3. ast.unparse not available <3.9 -- Mitigate: Version check with graceful fallback to regex
4. RecursionError on deeply nested files -- Mitigate: `sys.setrecursionlimit` guard + catch RecursionError

**Rollback:** `export V2_AST_PARSER=0` or `git revert HEAD~N..HEAD`

**Tasks:**
- Task 4.1: Write comprehensive failing tests for AST parser
- Task 4.2: Implement AstPythonParser and register in PARSER_REGISTRY

**Tests:** ~12 new tests.

---

### Milestone 5: Cross-File Resolution (Complexity: 60%, Effort: 3-4 hours)

**Goal:** Enable cross-module call graphs by resolving imports to file paths.
**Issues Covered:** P1 (cross-file call graph)
**Dependencies:** M4
**Research:** `codebase-deep-dive-20260317-094939/research-cross-file-resolution.md`

**Acceptance Criteria:**
- `build_import_map(project_root)` resolves `dotted.name` to `relative/file/path.py`
- `resolve_cross_file_edges(index)` adds `xg` key with cross-file edges
- Handles: absolute imports, relative imports, `__init__.py` re-exports
- Does NOT guess: dynamic imports, runtime sys.path manipulation
- Schema extension is backward-compatible (additive `xg` key)
- Tests with multi-file fixtures

**Risks & Mitigations:**
1. Import resolution is ambiguous for namespace packages -- Mitigate: Prefer precision over recall
2. Performance on large projects with deep import chains -- Mitigate: Depth limit of 2 for `__init__.py` re-export chains
3. Schema change breaks consumers -- Mitigate: `xg` key is additive, never replaces `g`

**Rollback:** `git revert HEAD~N..HEAD`

**Tasks:**
- Task 5.1: Implement `build_import_map`
- Task 5.2: Implement `resolve_cross_file_edges`

**Tests:** ~6 new tests.

---

### Milestone 6: Incremental Indexing (Complexity: 65%, Effort: 4-5 hours)

**Goal:** Per-file caching with SQLite for <2s incremental updates on large projects.
**Issues Covered:** P1 (performance 15-30s to <2s)
**Dependencies:** M1
**Research:** `codebase-deep-dive-20260317-094939/research-incremental-indexing.md`

**Acceptance Criteria:**
- SQLite cache at `~/.claude-code-project-index/cache.db`
- Two-tier dirty detection: mtime+size fast path, SHA-256 on mismatch
- `git diff --name-only` for committed change detection
- Cache versioning: full invalidation on tool version change
- `--incremental` flag on project_index.py
- Fallback to full rebuild when >50% dirty or cache corrupt
- `PRAGMA integrity_check` on cache open
- Tests with SQLite fixtures

**Risks & Mitigations:**
1. SQLite file corruption -- Mitigate: integrity check on open, delete + rebuild on failure
2. Cache version mismatch -- Mitigate: tool_version in meta table, auto-invalidate
3. Concurrent access from multiple hooks -- Mitigate: WAL mode + NORMAL sync

**Rollback:** `rm ~/.claude-code-project-index/cache.db` then `git revert HEAD~N..HEAD`

**Tasks:**
- Task 6.1: SQLite cache backend
- Task 6.2: Dirty file detection
- Task 6.3: Incremental update integration

**Tests:** ~8 new tests.

---

### Milestone 7: Query Engine + MCP Server (Complexity: 60%, Effort: 5-6 hours)

**Goal:** Structured code queries (who_calls, blast_radius, dead_code) with optional MCP server.
**Issues Covered:** P1 (MCP server), P3 (CLI interface)
**Dependencies:** M5, M6
**Research:** `codebase-deep-dive-20260317-094939/research-mcp-code-intelligence.md`

**Acceptance Criteria:**
- `QueryEngine` class with 6 query methods: `who_calls`, `blast_radius`, `dead_code`, `dependency_chain`, `search_symbols`, `file_summary`
- All queries <25ms p99 on 10k-file index
- CLI: `python3 cli.py query who-calls <symbol> [depth]`
- MCP server (optional): FastMCP 2.2.x with stdio transport
- `readOnlyHint: true` on all MCP tools

**Risks & Mitigations:**
1. FastMCP is external dependency -- Mitigate: MCP server is optional, query engine works standalone
2. Graph traversal performance -- Mitigate: Pre-compute reverse call graph on load
3. CLI UX -- Mitigate: Simple argparse interface, JSON output

**Rollback:** `git revert HEAD~N..HEAD`

**Tasks:**
- Task 7.1: Query engine core
- Task 7.2: CLI interface
- Task 7.3: MCP server (optional)

**Tests:** ~10 new tests.

---

### Milestone 8: Multi-Language Augmentation + Polish (Complexity: 45%, Effort: 3-4 hours)

**Goal:** ast-grep for additional languages, PageRank symbol importance.
**Issues Covered:** P2 (ast-grep), P3 (PageRank)
**Dependencies:** M4, M7

**Acceptance Criteria:**
- If `sg` (ast-grep) on PATH, parse Go/Rust/Java/Ruby signatures
- Silent no-op if `sg` not installed
- PageRank-based importance scores in `_meta` for compression decisions
- Tests for ast-grep integration (mocked subprocess)

**Risks & Mitigations:**
1. ast-grep not installed -- Mitigate: Silent no-op, zero impact on existing behavior
2. PageRank computation on large graphs -- Mitigate: 20-iteration power iteration, <100ms

**Rollback:** `git revert HEAD~N..HEAD`

**Tasks:**
- Task 8.1: ast-grep integration
- Task 8.2: PageRank symbol importance

**Tests:** ~6 new tests.

---

## Summary

| Milestone | Effort | Complexity | Issues | Tests Added |
|-----------|--------|------------|--------|-------------|
| M1: Foundation & Security | 2-3 hrs | 35% | 7 | ~6 |
| M2: Critical Tests | 2-3 hrs | 40% | 4 | ~10 |
| M3: God Function Decomp | 3-4 hrs | 55% | 2 | ~8 |
| M4: Python AST Parser | 3-4 hrs | 70% | 1 | ~12 |
| M5: Cross-File Resolution | 3-4 hrs | 60% | 1 | ~6 |
| M6: Incremental Indexing | 4-5 hrs | 65% | 1 | ~8 |
| M7: Query Engine + MCP | 5-6 hrs | 60% | 2 | ~10 |
| M8: Multi-Language + Polish | 3-4 hrs | 45% | 2 | ~6 |
| **TOTAL** | **~26-33 hrs** | -- | **12** | **~66** |

## Dependencies & Assumptions

- Python 3.9+ required (for `ast.unparse()`)
- stdlib only for all milestones except M7 MCP server (optional FastMCP 2.2.x)
- Existing 46 tests and 11 test files form the baseline
- Research documents in `codebase-deep-dive-20260317-094939/` are the source of truth for design decisions
- No external dependencies added to the core tool

## Next Action

Begin with **Milestone 1, Task 1.1**: Consolidate `_validate_python_cmd` to `index_utils.py` with tightened basename regex. Update `project-index-upgrade-tasks.md` after completion.
