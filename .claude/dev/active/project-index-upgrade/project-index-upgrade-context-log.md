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

**Remaining Questions / Unresolved Issues:**

- **PageRank convergence parameters:** The plan specifies 20 iterations for power iteration, but optimal parameters depend on actual graph density. Will need empirical tuning during M8 implementation.
- **MCP server authentication:** Not addressed in plan. For local stdio transport this is likely unnecessary, but should be considered if network transport is ever added.
- **ast-grep pattern coverage:** The plan lists Go/Rust/Java/Ruby but the specific `sg` patterns for each language need to be researched during M8 implementation.
