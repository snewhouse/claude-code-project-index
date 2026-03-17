# Recommendations & Action Plan

## Priority Matrix

| Priority | Category | Issue | Effort | Impact |
|----------|----------|-------|--------|--------|
| P0 | Accuracy | Replace Python regex parser with `ast` module | 3-4 hrs | Python accuracy 70% → 99% |
| P0 | Security | Consolidate `_validate_python_cmd` to index_utils.py | 30 min | Eliminate security drift risk |
| P0 | Security | Tighten basename regex validation | 15 min | Block `python3-malicious` names |
| P1 | Accuracy | Cross-file call graph via import resolution | 2-3 hrs | Enable cross-file relationships |
| P1 | Performance | Incremental indexing with per-file hash cache | 3-4 hrs | 15-30s → <2s for 1-file change |
| P1 | Quality | Extract shared utilities (hash calc, atomic write) | 1-2 hrs | Eliminate 3 DRY violations |
| P1 | Feature | MCP server for structured queries | 4-6 hrs | who_calls, blast_radius, dead_code |
| P2 | Accuracy | ast-grep augmentation for unlisted languages | 1-2 hrs | Go/Rust/Java/Ruby coverage |
| P2 | Quality | Decompose god functions (380-line parsers) | 2-3 hrs | Readability + testability |
| P2 | Testing | Add integration tests for build_index, generate_index_at_size | 2-3 hrs | Cover critical untested paths |
| P3 | Feature | PageRank-based symbol importance ranking | 2-3 hrs | Better compression decisions |
| P3 | Feature | CLI query interface | 2-3 hrs | Human-accessible code queries |

---

## Phase 1: Foundation & Security (Week 1-2)

### 1.1 Consolidate Shared Utilities
- Move `_validate_python_cmd` to `index_utils.py`
- Extract `calculate_files_hash()` as shared function
- Extract `atomic_write_json()` as shared function
- Tighten basename regex: `re.fullmatch(r'python\d*(\.\d+)?', basename)`
- Replace `which xclip` with `shutil.which('xclip')`

### 1.2 Clean Up Dead Code
- Remove `MAX_ITERATIONS` dead guard or restructure as list-of-steps
- Remove `ssh_file_large` dead branch in `_build_hook_output`
- Remove duplicate `__pycache__` in IGNORE_DIRS
- Fix `any` → `Any` in type annotations

### 1.3 Add Critical Tests
- Integration test for `build_index` with tmp_path
- Tests for `generate_index_at_size` (mock subprocess)
- Tests for `should_regenerate_index`
- Fix compress test to verify output fits target

**Acceptance:** All 39+ tests pass, zero DRY violations in security code, dead code removed.

---

## Phase 2: Python AST Parser (Week 3-4)

### 2.1 Replace `extract_python_signatures` with `ast` module

**Why:** Current regex parser is ~70% accurate. Python's `ast` module is stdlib, zero dependencies, ~99% accurate for all Python syntax.

**Key technique:** `ast.NodeVisitor` subclass that visits `FunctionDef`, `AsyncFunctionDef`, `ClassDef`, `Import`, `ImportFrom` nodes. Use `ast.unparse()` (3.9+) to reconstruct signatures. Extract call graph via `ast.Call` nodes within function bodies.

**Implementation:**
- Write `AstPythonParser(ast.NodeVisitor)` in new `parsers/python_ast_parser.py` or inline in `index_utils.py`
- Register as `.py` handler in `PARSER_REGISTRY`
- SyntaxError fallback to existing regex parser (for partial/invalid files)
- Feature flag: `V2_AST_PARSER=1` env var for A/B testing
- Bump minimum Python to 3.9+ (3.8 is EOL)

**What it fixes:**
- Multi-line signatures with `:` in defaults
- Nested generics (`Dict[str, List[Tuple[int, ...]]]`)
- Multi-line continuation imports
- Nested functions and closures
- Dataclass fields
- All docstring variations

**Research:** See `research-python-ast.md` for full implementation patterns and code examples.

**Acceptance:** A/B test showing identical or better output for all existing test fixtures.

---

## Phase 3: Cross-File Resolution + Incremental Indexing (Week 5-8)

### 3.1 Cross-File Call Graph

**Why:** Current call graph is intra-file only. "Function A in file X calls function B in file Y" is invisible.

**Technique:** Import resolution via module map:
1. Build `{dotted.name → relative/file/path.py}` from git file list
2. For each `import foo.bar` → resolve to `foo/bar.py`
3. For relative imports: `from .utils import X` → resolve to sibling
4. Connect intra-file calls through resolved imports
5. Add `xg` key to PROJECT_INDEX.json for cross-file edges

**Research:** See `research-cross-file-resolution.md` for PyCG, Pyan3, and Griffe approaches.

### 3.2 Incremental Indexing

**Why:** Full re-index takes 15-30s on large projects. With per-file caching, 1-file change → <2s.

**Technique:**
1. Store per-file content hash in `_file_hashes` dict in `_meta`
2. On update: compare hashes, only re-parse dirty files
3. Load cached results for unchanged files
4. Rebuild graph from merged results
5. Use `git diff --name-only $LAST_SHA HEAD` for fast dirty detection
6. Fall back to full rebuild on cache corruption

**Cache storage:** SQLite via stdlib `sqlite3` (WAL mode) for 50k+ file projects.

**Research:** See `research-incremental-indexing.md` for strategy details and benchmarks.

---

## Phase 4: Query Engine + MCP Server (Week 9-12)

### 4.1 Query Engine

In-memory graph traversal over `PROJECT_INDEX.json`:

| Query | Method | Use Case |
|-------|--------|----------|
| `who_calls(symbol, depth)` | Reverse BFS | "What depends on this function?" |
| `blast_radius(symbol)` | Forward+reverse BFS | "What breaks if I change this?" |
| `dead_code()` | Full graph scan | "What's never called from entry points?" |
| `dependency_chain(file)` | Import graph traversal | "What does this file need?" |
| `search_symbols(pattern)` | Fuzzy match | "Find functions matching X" |
| `file_summary(path)` | Direct lookup | "What's in this file?" |

### 4.2 MCP Server (Optional, FastMCP 2.2.x)

- Expose 6 query tools via MCP protocol
- `lifespan` context manager loads index at startup
- Pre-compute reverse call graph from `g` edges
- All queries <25ms p99
- stdio transport, project-scoped `.mcp.json`
- `readOnlyHint: true` annotation skips confirmation prompts

### 4.3 CLI Interface

```bash
python3 ~/.claude-code-project-index/cli.py query who-calls build_index 3
python3 ~/.claude-code-project-index/cli.py query blast-radius extract_python_signatures
python3 ~/.claude-code-project-index/cli.py query dead-code
```

**Research:** See `research-mcp-code-intelligence.md` for full design.

---

## Phase 5: Multi-Language Augmentation (Week 13+)

### 5.1 ast-grep for Unlisted Languages

- If `sg` (ast-grep) is on PATH, augment index with Go/Rust/Java/Ruby signatures
- Subprocess: `sg run -l LANG --json=stream`
- 34 languages supported, Rust-based parallelism
- Silent no-op if `sg` not installed
- Alternative: `ast_grep_py` PyPI package for native bindings

### 5.2 tree-sitter for Deep Multi-Language Parsing (Optional)

- Only if zero-dependency constraint is relaxed
- `pip install tree-sitter tree-sitter-python tree-sitter-javascript`
- Error recovery (partial trees on invalid syntax)
- Language-agnostic API for all languages

**Research:** See `research-ast-grep.md` and `research-tree-sitter.md`.

---

## Competitive Differentiation

Based on research (`research-ai-code-intelligence-landscape.md`):

### What We Have That Others Don't
1. **Hook-level UserPromptSubmit interception** — no other tool does this
2. **Portable single-file structural index** with call graph + dep graph
3. **Dual transport** (subagent + clipboard with fallback chain)
4. **Zero infrastructure, zero cloud, stdlib only**
5. **Token-budget flags** (`-i[N]`, `-ic[N]`) at point of use

### Highest-ROI Improvements (from competitive analysis)
1. Python `ast` parser (accuracy gap vs all competitors)
2. PageRank-based symbol importance (Aider's approach)
3. MCP server mode (adopted by OpenAI March 2025)
4. Incremental indexing (standard in all serious tools)
5. Optional local embeddings for semantic search (no cloud)

---

## Suggested Roadmap

| Phase | Timeline | Effort | Impact |
|-------|----------|--------|--------|
| 1. Foundation & Security | Week 1-2 | Low | High (security, quality) |
| 2. Python AST Parser | Week 3-4 | Medium | Very High (accuracy 70%→99%) |
| 3. Cross-File + Incremental | Week 5-8 | Medium-High | High (relationships, performance) |
| 4. Query Engine + MCP | Week 9-12 | Medium | High (structured queries) |
| 5. Multi-Language | Week 13+ | Low | Medium (broader language coverage) |
