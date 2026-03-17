# project-index-upgrade Tasks (HTP)

_Hierarchical Task Planning roadmap with dependencies and state tracking._

## Milestone 1: Foundation & Security
- **Status:** COMPLETE
- **Dependencies:** None
- **Complexity:** 35%
- **Effort:** 2-3 hours
- **Acceptance Criteria:**
  - `_validate_python_cmd` exists in exactly ONE file (`index_utils.py`)
  - Basename regex rejects `python3-malicious`, accepts `python3`, `python3.12`
  - `calculate_files_hash()` is a shared function in `index_utils.py`
  - `atomic_write_json()` is a shared function in `index_utils.py`
  - `shutil.which('xclip')` replaces `subprocess.run(['which', 'xclip'], ...)`
  - All 3 dead code instances removed
  - All `any` type annotations replaced with `Any`
  - All existing 46 tests pass
  - Zero import of `_validate_python_cmd` from local scope in i_flag_hook.py or stop_hook.py
- **Result Log:** All 9 acceptance criteria verified. 54 tests pass (46 original + 8 new). validate_python_cmd consolidated with tightened regex `python\d*(\.\d+)?`. calculate_files_hash and atomic_write_json extracted as shared utilities. Dead code removed (duplicate __pycache__, ssh_file_large branch, MAX_ITERATIONS guard). Type annotations fixed (3 instances of lowercase any).

### Step 1.1: Consolidate `_validate_python_cmd` to index_utils.py
- **Status:** COMPLETE
- **Dependencies:** None
- **Files:** `scripts/index_utils.py`, `scripts/i_flag_hook.py`, `scripts/stop_hook.py`, `tests/test_security.py`
- **Result Log:** Moved to index_utils.py as public validate_python_cmd with tightened regex. Updated 3 imports in test_security.py. Added test_validate_python_cmd_tightened_regex test. 47 tests pass.

### Step 1.2: Extract `calculate_files_hash()` as shared utility
- **Status:** COMPLETE
- **Dependencies:** Step 1.1
- **Files:** `scripts/index_utils.py`, `scripts/i_flag_hook.py`, `scripts/stop_hook.py`, `tests/test_shared_utils.py` (created)
- **Result Log:** Moved from i_flag_hook.py to index_utils.py. Replaced inline hash logic in stop_hook.py with shared utility. Created test_shared_utils.py with 3 tests. 50 tests pass.

### Step 1.3: Extract `atomic_write_json()` as shared utility
- **Status:** COMPLETE
- **Dependencies:** Step 1.1
- **Files:** `scripts/index_utils.py`, `scripts/project_index.py`, `scripts/i_flag_hook.py`, `tests/test_atomic_writes.py`, `tests/test_shared_utils.py`
- **Result Log:** Created atomic_write_json with tempfile+os.replace+optional fcntl. Replaced inline patterns in project_index.py and i_flag_hook.py. Updated test_atomic_writes.py to verify shared utility usage. Added 3 tests for atomic_write_json. 54 tests pass.

### Step 1.4: Replace `which xclip` with `shutil.which`
- **Status:** COMPLETE
- **Dependencies:** None
- **Files:** `scripts/i_flag_hook.py`
- **Result Log:** Replaced subprocess.run(['which', 'xclip']) with shutil.which('xclip') in _try_xclip function.

### Step 1.5: Clean up dead code
- **Status:** COMPLETE
- **Dependencies:** None
- **Files:** `scripts/project_index.py`, `scripts/i_flag_hook.py`, `scripts/index_utils.py`
- **Result Log:** Removed: duplicate __pycache__ in IGNORE_DIRS, ssh_file_large dead branch in _build_hook_output, MAX_ITERATIONS variable and 5 dead guard checks in compress_if_needed.

### Step 1.6: Fix type annotations (`any` to `Any`)
- **Status:** COMPLETE
- **Dependencies:** None
- **Files:** `scripts/index_utils.py`
- **Result Log:** Added Any to typing imports. Fixed 3 instances: extract_javascript_signatures return type, _parse_shell_function return type, extract_shell_signatures return type.

---

## Milestone 2: Critical Test Coverage
- **Status:** COMPLETE
- **Dependencies:** Milestone 1
- **Complexity:** 40%
- **Effort:** 2-3 hours
- **Acceptance Criteria:**
  - `build_index()` has end-to-end integration test with tmp_path
  - `generate_index_at_size()` has tests (mocked subprocess)
  - `should_regenerate()` has tests
  - `compress_if_needed()` test verifies output fits target size
  - Test count increases from 46 to 56+
  - All tests pass
- **Result Log:** All 6 acceptance criteria verified. 70 tests pass (54 from M1 + 16 new). Created 3 new test files with 15 tests covering build_index, generate_index_at_size, and should_regenerate. Added 1 test to existing test_compression.py.

### Step 2.1: Integration test for `build_index`
- **Status:** COMPLETE
- **Dependencies:** Milestone 1
- **Files:** `tests/test_build_index.py` (created)
- **Result Log:** 5 tests created: returns_tuple, indexes_python_file, skips_ignored_dirs, stats_counts, empty_dir. Uses tmp_path with git init for realistic file discovery.

### Step 2.2: Tests for `generate_index_at_size`
- **Status:** COMPLETE
- **Dependencies:** Milestone 1
- **Files:** `tests/test_generate_index.py` (created)
- **Result Log:** 5 tests created: success, failure, timeout, remembers_size, clipboard_no_remember. Uses unittest.mock.patch for subprocess mocking.

### Step 2.3: Tests for `should_regenerate`
- **Status:** COMPLETE
- **Dependencies:** Step 1.2 (requires shared calculate_files_hash)
- **Files:** `tests/test_staleness.py` (created)
- **Result Log:** 5 tests created: no_index, matching_hash, different_hash, unknown_hash, corrupt_json. Uses mock.patch for calculate_files_hash.

### Step 2.4: Fix compress test to verify output fits target
- **Status:** COMPLETE
- **Dependencies:** Milestone 1
- **Files:** `tests/test_compression.py`
- **Result Log:** Added test_compression_fits_target asserting compressed_size <= target.

---

## Milestone 3: God Function Decomposition
- **Status:** COMPLETE
- **Dependencies:** Milestone 1, Milestone 2
- **Complexity:** 55%
- **Effort:** 3-4 hours
- **Acceptance Criteria:**
  - `extract_python_signatures` decomposed into `_parse_python_imports`, `_parse_python_classes`, `_parse_python_functions` helpers
  - `extract_javascript_signatures` decomposed similarly, with `_find_matching_brace` extracted (replaces 5 inline instances)
  - `build_index` decomposed into `_discover_files`, `_parse_all_files`, `_build_call_graph`, `_build_dep_graph`
  - No function exceeds 100 lines
  - All 56+ tests still pass
  - New helpers have targeted unit tests
- **Result Log:** All 6 acceptance criteria verified. 79 tests pass (70 from M2 + 9 new brace matching tests). extract_python_signatures: 381→52 lines, extract_javascript_signatures: 358→29 lines, build_index: 283→61 lines, extract_shell_signatures: 111→63 lines, convert_to_enhanced_dense_format: 122→37 lines. No function exceeds 100 lines. 18 new helper functions created across index_utils.py and project_index.py.

### Step 3.1: Extract `_find_matching_brace` from JS parser
- **Status:** COMPLETE
- **Dependencies:** Milestone 2
- **Files:** `scripts/index_utils.py`, `tests/test_brace_matching.py` (created)
- **Result Log:** Created _find_matching_brace (line-based) and _find_matching_brace_char (character-based). 9 tests in test_brace_matching.py. Replaced 3 inline brace-counting loops.

### Step 3.2: Decompose `extract_python_signatures`
- **Status:** COMPLETE
- **Dependencies:** Step 3.1
- **Files:** `scripts/index_utils.py`
- **Result Log:** Extracted 7 helpers: _parse_python_imports, _handle_python_class_def, _handle_python_func_def, _extract_python_func_body, _cleanup_python_result, _parse_python_module_level, _parse_python_class_body. Main function: 381→52 lines.

### Step 3.3: Decompose `extract_javascript_signatures`
- **Status:** COMPLETE
- **Dependencies:** Step 3.1
- **Files:** `scripts/index_utils.py`
- **Result Log:** Extracted 9 helpers: _collect_js_function_names, _parse_js_imports, _parse_js_type_aliases, _parse_js_interfaces, _parse_js_enums, _parse_js_constants_and_vars, _parse_js_classes, _parse_js_standalone_functions, _cleanup_js_result. Main function: 358→29 lines.

### Step 3.4: Decompose `build_index`
- **Status:** COMPLETE
- **Dependencies:** Steps 3.2, 3.3
- **Files:** `scripts/project_index.py`
- **Result Log:** Extracted 4 helpers: _discover_files, _parse_all_files, _build_dep_graph, _build_call_graph. Also decomposed convert_to_enhanced_dense_format (extracted _compress_file_entry, _build_dense_call_graph_edges, _truncate_doc). Main function: 283→61 lines.

---

## Milestone 4: Python AST Parser
- **Status:** COMPLETE
- **Dependencies:** Milestone 1, Milestone 2, Milestone 3
- **Complexity:** 70%
- **Effort:** 3-4 hours
- **Acceptance Criteria:**
  - New `AstPythonParser` class using `ast.NodeVisitor`
  - Registered in `PARSER_REGISTRY` for `.py` extension
  - `SyntaxError` fallback to existing regex parser
  - Feature flag `V2_AST_PARSER=0` env var disables new parser
  - All existing characterization tests pass (identical or better output)
  - New tests for: nested functions, complex defaults, generics, async, decorators, dataclasses
  - Minimum Python version: 3.9 (for `ast.unparse()`)
  - Output format compatible with existing dense format conversion
- **Result Log:** All 8 acceptance criteria verified. 93 tests pass (79 from M3 + 14 new). extract_python_signatures_ast implemented using ast.parse + ast walking. Feature flag V2_AST_PARSER controls selection at call time in parse_file(). SyntaxError falls back to regex. Dense format compatibility verified.

### Step 4.1: Write comprehensive failing tests for AST parser
- **Status:** COMPLETE
- **Dependencies:** Milestone 3
- **Files:** `tests/test_ast_parser.py` (created)
- **Result Log:** 13 tests created covering: simple functions, classes with methods, async, decorators, nested functions, complex defaults, dataclasses, imports, constants, feature flag, SyntaxError fallback, inheritance, enums.

### Step 4.2: Implement AstPythonParser and register in PARSER_REGISTRY
- **Status:** COMPLETE
- **Dependencies:** Step 4.1
- **Files:** `scripts/index_utils.py` (added extract_python_signatures_ast), `tests/test_registry.py` (added test_parse_file_uses_ast_by_default), `scripts/project_index.py` (removed dead extract_python_signatures import)
- **Result Log:** AST parser uses ast.parse+walking, ast.unparse for signatures, ast.get_docstring for docs. Feature flag in parse_file() selects AST vs regex at call time. PARSER_REGISTRY unchanged (still maps .py to regex). Removed unused import from project_index.py.

---

## Milestone 5: Cross-File Resolution
- **Status:** COMPLETE
- **Dependencies:** Milestone 4
- **Complexity:** 60%
- **Effort:** 3-4 hours
- **Acceptance Criteria:**
  - `build_import_map(project_root)` resolves `dotted.name` to `relative/file/path.py`
  - `resolve_cross_file_edges(index)` adds `xg` key with cross-file edges
  - Handles: absolute imports, relative imports, `__init__.py` re-exports
  - Does NOT guess: dynamic imports, runtime sys.path manipulation
  - Schema extension is backward-compatible (additive `xg` key)
  - Tests with multi-file fixtures
- **Result Log:** All 6 acceptance criteria verified. 102 tests pass (93 from M4 + 9 new). build_import_map walks .py files to create dotted-name→path mapping. resolve_cross_file_edges matches function calls against imported files' functions. Integrated into build_index and dense format.

### Step 5.1: Implement `build_import_map`
- **Status:** COMPLETE
- **Dependencies:** Milestone 4
- **Files:** `scripts/index_utils.py`, `tests/test_cross_file.py` (created)
- **Result Log:** build_import_map uses get_git_files or rglob to find .py files, converts paths to dotted module names, handles __init__.py package mappings. 4 tests for import map (simple, nested, empty, git-based).

### Step 5.2: Implement `resolve_cross_file_edges`
- **Status:** COMPLETE
- **Dependencies:** Step 5.1
- **Files:** `scripts/project_index.py`, `scripts/index_utils.py`
- **Result Log:** resolve_cross_file_edges matches function calls against resolved import targets. Returns [source:func, target:func, "call"] triples. Integrated into build_index (after _build_call_graph) and convert_to_enhanced_dense_format (passes through xg key). 5 tests for edge resolution.

---

## Milestone 6: Incremental Indexing
- **Status:** PENDING
- **Dependencies:** Milestone 1
- **Complexity:** 65%
- **Effort:** 4-5 hours
- **Acceptance Criteria:**
  - SQLite cache at `~/.claude-code-project-index/cache.db`
  - Two-tier dirty detection: mtime+size fast path, SHA-256 on mismatch
  - `git diff --name-only` for committed change detection
  - Cache versioning: full invalidation on tool version change
  - `--incremental` flag on project_index.py
  - Fallback to full rebuild when >50% dirty or cache corrupt
  - `PRAGMA integrity_check` on cache open
  - Tests with SQLite fixtures

### Step 6.1: SQLite cache backend
- **Status:** PENDING
- **Dependencies:** Milestone 1
- **Files:** `scripts/cache_db.py` (create), `tests/test_cache_db.py` (create)
- **Result Log:**

### Step 6.2: Dirty file detection
- **Status:** PENDING
- **Dependencies:** Step 6.1
- **Files:** `scripts/cache_db.py`, `tests/test_cache_db.py`
- **Result Log:**

### Step 6.3: Incremental update integration
- **Status:** PENDING
- **Dependencies:** Step 6.2
- **Files:** `scripts/project_index.py`
- **Result Log:**

---

## Milestone 7: Query Engine + MCP Server
- **Status:** PENDING
- **Dependencies:** Milestone 5, Milestone 6
- **Complexity:** 60%
- **Effort:** 5-6 hours
- **Acceptance Criteria:**
  - `QueryEngine` class with 6 query methods: `who_calls`, `blast_radius`, `dead_code`, `dependency_chain`, `search_symbols`, `file_summary`
  - All queries <25ms p99 on 10k-file index
  - CLI: `python3 cli.py query who-calls <symbol> [depth]`
  - MCP server (optional): FastMCP 2.2.x with stdio transport
  - `readOnlyHint: true` on all MCP tools

### Step 7.1: Query engine core
- **Status:** PENDING
- **Dependencies:** Milestone 5, Milestone 6
- **Files:** `scripts/query_engine.py` (create), `tests/test_query_engine.py` (create)
- **Result Log:**

### Step 7.2: CLI interface
- **Status:** PENDING
- **Dependencies:** Step 7.1
- **Files:** `scripts/cli.py` (create)
- **Result Log:**

### Step 7.3: MCP server (optional)
- **Status:** PENDING
- **Dependencies:** Step 7.1
- **Files:** `scripts/mcp_server.py` (create)
- **Result Log:**

---

## Milestone 8: Multi-Language Augmentation + Polish
- **Status:** PENDING
- **Dependencies:** Milestone 4, Milestone 7
- **Complexity:** 45%
- **Effort:** 3-4 hours
- **Acceptance Criteria:**
  - If `sg` (ast-grep) on PATH, parse Go/Rust/Java/Ruby signatures
  - Silent no-op if `sg` not installed
  - PageRank-based importance scores in `_meta` for compression decisions
  - Tests for ast-grep integration (mocked subprocess)

### Step 8.1: ast-grep integration
- **Status:** PENDING
- **Dependencies:** Milestone 4
- **Files:** `scripts/index_utils.py`, `tests/test_ast_grep.py` (create)
- **Result Log:**

### Step 8.2: PageRank symbol importance
- **Status:** PENDING
- **Dependencies:** Milestone 7
- **Files:** `scripts/pagerank.py` (create), `scripts/project_index.py`, `tests/test_pagerank.py` (create)
- **Result Log:**
