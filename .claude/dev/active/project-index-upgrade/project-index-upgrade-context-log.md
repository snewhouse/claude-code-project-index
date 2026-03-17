# project-index-upgrade Context Log

_This log captures architectural decisions, trade-offs, and unresolved issues._

## 2026-03-17 Initial Context

**Feature Request (Phase 1):**
Address ALL P0-P3 issues identified in the codebase deep-dive analysis (12 issues total across security, accuracy, DRY violations, testing gaps, and new features). Implement Phases 1-5 of the recommended roadmap covering foundation & security fixes, Python AST parser replacement, cross-file resolution, incremental indexing, query engine with MCP server, and multi-language augmentation.

**Key Decisions (Phase 2 Brainstorming):**

- **Decision AD-001:** Dependency-driven milestone ordering (Approach C)
  - **Rationale:** Milestones are ordered by technical dependency rather than strict priority or phase alignment. This produces testable, shippable increments at each milestone boundary.
  - **Alternatives Considered:**
    - Approach A: Phase-aligned ordering (Phases 1-5 sequentially) -- rejected because phases contain mixed dependencies
    - Approach B: Strict priority ordering (all P0 first, then P1, etc.) -- rejected because P0 AST parser depends on test infrastructure (P2)
  - **Trade-offs:** Approach C may delay some P0 fixes slightly (AST parser is M4 not M1), but ensures each milestone has its prerequisites met. Reduces rework and integration issues.

- **Decision AD-002:** Decompose Python regex parser before replacing with AST
  - **Rationale:** User explicitly requested decomposition as M3 before AST replacement as M4, even though the regex parser will be replaced. Decomposed helpers inform AST parser design and provide characterization test targets.
  - **Alternatives Considered:**
    - Skip decomposition, go straight to AST replacement -- recommended by analysis but overridden by user preference
  - **Trade-offs:** 3-4 hours of effort on code that will be replaced. However, the decomposition creates testable units that validate the characterization test suite, and the helper signatures inform the AST parser's output contract.

- **Decision AD-003:** Python 3.9+ minimum version
  - **Rationale:** `ast.unparse()` was added in Python 3.9 and is essential for reconstructing type annotations and function signatures from the AST. Without it, the AST parser would need custom unparsing logic.
  - **Alternatives Considered:**
    - Python 3.8+ with custom `ast_unparse()` backport -- adds complexity and maintenance burden
    - Python 3.10+ -- unnecessarily restrictive
  - **Trade-offs:** Drops Python 3.8 support. Acceptable because Python 3.8 reached EOL in October 2024.

- **Decision AD-004:** SQLite via stdlib sqlite3 for incremental cache
  - **Rationale:** Zero additional dependencies. SQLite provides ACID transactions, WAL mode for concurrent reads, and integrity checking. Cache stored at `~/.claude-code-project-index/cache.db`.
  - **Alternatives Considered:**
    - JSON file cache -- no concurrent access safety, no integrity checking
    - shelve/dbm -- less portable, no SQL for querying cache state
    - External database (Redis, etc.) -- unnecessary complexity for a local tool
  - **Trade-offs:** SQLite file can corrupt (mitigated by integrity check on open + delete-and-rebuild). Slightly more complex than JSON but dramatically more robust.

**Research Findings (Phase 3):**

Seven research reports were analyzed from the `codebase-deep-dive-20260317-094939/` directory:

- **research-python-ast.md:** `ast.NodeVisitor` pattern is the standard approach. `ast.unparse()` (3.9+) reconstructs source from AST nodes. `ast.get_docstring()` extracts docstrings. SyntaxError fallback to regex is essential for partial/invalid files.
- **research-cross-file-resolution.md:** Import map pattern (`dotted.name` to `relative/path.py`) is straightforward for standard imports. Namespace packages and dynamic imports should be skipped (precision over recall). Depth limit of 2 for `__init__.py` re-export chains prevents performance issues.
- **research-incremental-indexing.md:** Two-tier dirty detection (mtime+size fast path, SHA-256 on mismatch) is the standard pattern. `git diff --name-only` catches committed changes. >50% dirty threshold should trigger full rebuild.
- **research-mcp-code-intelligence.md:** FastMCP 2.2.x provides clean Python API for MCP servers. stdio transport is simplest. `readOnlyHint: true` signals read-only tools. Query engine should be standalone (MCP is optional wrapper).
- **08-recommendations.md:** 12 issues prioritized P0-P3 with 5-phase roadmap. 3 P0 issues (security + accuracy), 4 P1 issues (features + DRY), 3 P2 issues (quality), 2 P3 issues (nice-to-have).
- Additional reports covered code structure analysis, dead code identification, and type annotation issues.

## 2026-03-17 Milestone 1 Completion: Foundation & Security
- Status: COMPLETE
- Key outcome: Consolidated 3 duplicate functions into shared utilities in index_utils.py, tightened security regex, cleaned dead code, fixed type annotations
- Artifacts: Modified scripts/index_utils.py, scripts/i_flag_hook.py, scripts/stop_hook.py, scripts/project_index.py. Created tests/test_shared_utils.py. Updated tests/test_security.py, tests/test_atomic_writes.py.
- Tests: 54 pass (46 original + 8 new)
- Notable: The tightened basename regex `python\d*(\.\d+)?` is stricter than the original `startswith('python')` check, properly rejecting paths like `python3-malicious`

## 2026-03-17 Milestone 8 Completion: Multi-Language Augmentation + Polish (FINAL)
- Status: COMPLETE
- Key outcome: Added optional ast-grep integration for Go/Rust/Java/Ruby parsing and PageRank-based symbol importance scoring. Both features degrade gracefully when unavailable. All 8 milestones now complete.
- Artifacts: Created scripts/pagerank.py, tests/test_pagerank.py (7 tests), tests/test_ast_grep.py (6 tests). Modified scripts/index_utils.py (sg integration), scripts/project_index.py (PageRank integration).
- Tests: 135 pass (122 from M7 + 13 new)

## 2026-03-17 Milestone 7 Completion: Query Engine + MCP Server
- Status: COMPLETE
- Key outcome: Created QueryEngine with 6 structural query methods, CLI with argparse, and optional MCP server (FastMCP guard). All tools work against both verbose and dense index formats.
- Artifacts: Created scripts/query_engine.py, scripts/cli.py, scripts/mcp_server.py, tests/test_query_engine.py (10 tests).
- Tests: 122 pass (112 from M6 + 10 new)

## 2026-03-17 Milestone 6 Completion: Incremental Indexing
- Status: COMPLETE
- Key outcome: Created SQLite-backed cache (cache_db.py) with two-tier dirty detection, version invalidation, and corrupt-db recovery. Integrated into project_index.py via --incremental flag. Second run shows 28/29 cache hits.
- Artifacts: Created scripts/cache_db.py, tests/test_cache_db.py (10 tests). Modified scripts/project_index.py (incremental parameter + cache integration).
- Tests: 112 pass (102 from M5 + 10 new)

## 2026-03-17 Milestone 5 Completion: Cross-File Resolution
- Status: COMPLETE
- Key outcome: Implemented build_import_map and resolve_cross_file_edges for cross-file call graph edges. Schema extended with backward-compatible xg key. Projects using standard package imports get cross-file edges; projects using sys.path manipulation (like this one) correctly get no edges.
- Artifacts: Modified scripts/index_utils.py (2 functions), scripts/project_index.py (2 integration points). Created tests/test_cross_file.py (9 tests).
- Tests: 102 pass (93 from M4 + 9 new)

## 2026-03-17 Milestone 4 Completion: Python AST Parser
- Status: COMPLETE
- Key outcome: Implemented extract_python_signatures_ast using Python's ast module for 100% accurate parsing. Feature flag V2_AST_PARSER controls selection, SyntaxError falls back to regex parser. Output format compatible with dense format conversion.
- Artifacts: Created tests/test_ast_parser.py (13 tests). Modified scripts/index_utils.py (added AST parser), scripts/project_index.py (removed dead import), tests/test_registry.py (+1 test).
- Tests: 93 pass (79 from M3 + 14 new)
- Decision: PARSER_REGISTRY['.py'] still points to regex parser. AST selection happens at parse_file() call time via env var check. This keeps backward compatibility and allows per-test toggling.

## 2026-03-17 Milestone 3 Completion: God Function Decomposition
- Status: COMPLETE
- Key outcome: Decomposed 5 god functions (381, 358, 283, 122, 111 lines) into 18 focused helpers. No function exceeds 100 lines. Pure refactoring — all tests pass unchanged.
- Artifacts: Modified scripts/index_utils.py (major), scripts/project_index.py (major). Created tests/test_brace_matching.py (9 tests).
- Tests: 79 pass (70 from M2 + 9 new)

## 2026-03-17 Milestone 2 Completion: Critical Test Coverage
- Status: COMPLETE
- Key outcome: Added 16 new tests across 4 test files covering build_index, generate_index_at_size, should_regenerate, and compress_if_needed target verification
- Artifacts: Created tests/test_build_index.py (5 tests), tests/test_generate_index.py (5 tests), tests/test_staleness.py (5 tests). Updated tests/test_compression.py (+1 test).
- Tests: 70 pass (54 from M1 + 16 new)
- Notable: All 3 new test files were created by parallel subagents and passed on first run

**Remaining Questions / Unresolved Issues:**

- **PageRank convergence parameters:** The plan specifies 20 iterations for power iteration, but optimal parameters depend on actual graph density. Will need empirical tuning during M8 implementation.
- **MCP server authentication:** Not addressed in plan. For local stdio transport this is likely unnecessary, but should be considered if network transport is ever added.
- **ast-grep pattern coverage:** The plan lists Go/Rust/Java/Ruby but the specific `sg` patterns for each language need to be researched during M8 implementation.
