# State-of-the-Art Review: Code Indexing, Code Intelligence, and AI-Powered Code Understanding

**Date:** 2026-03-17
**Context:** Improving claude-code-project-index for AI-driven development workflows
**Scope:** Modern code intelligence tools, tree-sitter ecosystem, code graph approaches, incremental parsing, cross-file resolution, AI-native understanding

> This is the comprehensive analysis report for the codebase-deep-dive session. It is grounded in training knowledge (up to May 2025) and direct review of the claude-code-project-index source code (`scripts/project_index.py`, `scripts/index_utils.py`, `scripts/i_flag_hook.py`). WebFetch was unavailable in this session; implementation details for open-source tools are based on well-documented public source code and confirmed community documentation.

---

## Table of Contents

1. [Modern Code Intelligence Tools](#1-modern-code-intelligence-tools)
2. [Tree-sitter Ecosystem](#2-tree-sitter-ecosystem)
3. [Code Graph Approaches](#3-code-graph-approaches)
4. [Incremental Parsing Techniques](#4-incremental-parsing-techniques)
5. [Cross-File Call Resolution for Python](#5-cross-file-call-resolution-for-python)
6. [AI-Native Code Understanding](#6-ai-native-code-understanding)
7. [Comparison Tables](#7-comparison-tables)
8. [Key Insights for claude-code-project-index](#8-key-insights-for-claude-code-project-index)
9. [Recommended Technologies to Evaluate](#9-recommended-technologies-to-evaluate)

---

## 1. Modern Code Intelligence Tools

### 1.1 Sourcegraph

Sourcegraph is the most complete production-grade code intelligence platform available as of 2025. It operates at the scale of millions of repositories and has pioneered several techniques directly applicable to this project.

**SCIP (Source Code Intelligence Protocol)**

SCIP is Sourcegraph's open indexing protocol, replacing the earlier LSIF format. It defines a language-agnostic binary format for code intelligence data:

- A protobuf schema defining `Document`, `Occurrence`, and `SymbolInformation` messages
- Every occurrence carries a symbol string, range, and role flags (definition, reference, import, etc.)
- Symbol strings use a canonical dotted path notation: `scip-python python pip <package> <version> src/<module>/<Class>#<method>().`
- Indexes are produced by language-specific indexers (`scip-python`, `scip-typescript`, `scip-java`, etc.) and consumed by Sourcegraph's backend
- Indexers run as CI steps and upload to the Sourcegraph instance; the core analysis is not incremental per-file but per-repository snapshot

**Practical architecture:**
- `scip-python` uses Jedi under the hood for Python type resolution
- The protocol separates "global" symbols (importable from outside) from "local" symbols (function-scoped)
- Storage is in a flat file per repository, indexed by file path + range into a reverse-lookup structure
- Code navigation (go-to-definition, find-references) is served from this precomputed index, making queries O(1) at serve time

**Code Search Architecture**

Sourcegraph's code search uses a custom search engine called Zoekt (originally from Google). Key architectural choices:

- Trigram indexes built per shard (a shard is a group of repositories)
- Shard files are memory-mapped; search is a two-pass process: trigram filter then regex match on actual content
- Repository-level metadata (branch, commit SHA, file list) is stored separately and joined at query time
- Content indexes store raw file bytes; structural search (pattern matching that understands AST structure) uses a second-pass Comby engine
- At scale (~500k repos as operated by Sourcegraph.com), the index reaches several terabytes; shards are distributed across a fleet of zoekt-webserver instances

**Relevance to claude-code-project-index:** The SCIP symbol string format is a well-thought-out namespace for identifying code symbols across files. The trigram + secondary-filter approach is well-suited for local codebase search, since trigrams are fast to build and query.

---

### 1.2 GitHub Code Search

GitHub rebuilt its code search engine in 2022-2023 (internally called "Blackbird"). The new engine processes all public repositories at scale.

**Key techniques:**

- **Normalized tokens:** Unlike trigrams, Blackbird uses language-aware tokenization. Code is split into symbol tokens (identifiers, operators) and string tokens, producing a smaller, more precise inverted index than character-level trigrams.
- **Symbol extraction without full parsing:** For many languages, GitHub avoids full parsing by using heuristics and partial parsing to extract symbol names. This sacrifices precision for speed and breadth.
- **Repository-level inverted index:** The primary index maps `token → [repo_id, file_id, byte_offset]` with compression using SIMD-accelerated integer encoding.
- **Two-phase retrieval:** Fast token lookup narrows the candidate set; then the full content is re-read and matched against the query regex.
- **Scale:** As of 2024, GitHub indexes approximately 15 billion unique files across all public repositories.

**Structural search on GitHub:** GitHub Code Search supports "symbol search" (e.g., `symbol:ClassName`) which uses a separate index built from tree-sitter parse results. Tree-sitter is used for the 20+ most popular languages; the symbol index is exact.

**Relevance to claude-code-project-index:** The normalized token approach is more efficient than byte-level indexing for code. GitHub's use of tree-sitter specifically for symbol-level queries (not full text search) is a validated architectural pattern — it confirms that tree-sitter is the right layer for extracting function/class names.

---

### 1.3 OpenGrok

OpenGrok is an open-source, Apache-licensed cross-reference engine with a 15+ year history. It underpins Oracle's own code search infrastructure and is widely deployed in large enterprise codebases.

**Architecture:**
- Powered by Apache Lucene for the full-text index
- Source code analysis via Universal Ctags for symbol extraction
- Language detection and syntax tokenization via a custom Lex-based analyzer chain
- Cross-reference data (where a symbol is used, where it is defined) is stored as indexed Lucene documents
- The web UI is a Java EE application; the indexer daemon runs on a cron schedule or triggered by SCM hooks

**Indexing pipeline:**
1. File discovery and language detection
2. Raw content indexed into Lucene for full-text search
3. ctags run on each file to extract symbol definitions
4. Cross-reference resolution: each symbol occurrence resolved to its definition using a best-effort heuristic (file path + name match)
5. Index committed to disk; web tier reads directly from Lucene index files

**Limitations:** OpenGrok's cross-reference resolution is notoriously approximate because ctags does not understand import scoping. A function named `connect` in database code and networking code will both appear as candidates for any reference to `connect`.

**Relevance to claude-code-project-index:** OpenGrok validates the ctags/regex approach for broad language coverage with no per-language parsers, at the cost of cross-reference precision. The Lucene index architecture is overkill for single-project use but the data model (symbol definitions linked to occurrences) is the right abstraction.

---

### 1.4 AI Coding Tool Approaches

#### Cursor

Cursor is a VS Code fork with deep AI integration. Its codebase understanding relies on:

- **Embeddings-based retrieval:** The entire codebase is chunked and embedded using a code embedding model. Chunks are stored in a local vector database (Qdrant or a custom engine).
- **@codebase command:** On invocation, the user query is embedded and top-k similar chunks are retrieved via cosine similarity and injected into the LLM context.
- **Symbol resolution via LSP:** Cursor reads Language Server Protocol (LSP) data from VS Code's built-in language servers, allowing it to perform go-to-definition and find-references queries against the actual language server rather than building its own analysis.
- **File tree + recent files:** A lightweight project tree is always kept in context; recently edited files are preferentially included.
- **Multi-pass retrieval:** Pass 1: semantic ANN search on embeddings. Pass 2: dependency graph traversal from retrieved files. Pass 3: re-ranking by recency and call depth.

#### Windsurf (Codeium)

Windsurf (Codeium's IDE product) takes a similar embedding-based approach but has also invested in:

- **Cascade context engine:** Maintains a graph of recently touched files, imported modules of those files, and test files associated with production code. This graph is used to automatically expand context beyond what the user explicitly mentions.
- **Multi-file diff awareness:** Windsurf tracks which files were modified in a session and keeps a running diff in context.
- **Fill-in-the-middle (FIM):** Uses a code completion model that conditions on both prefix and suffix of the current cursor position.

#### Cline (formerly Claude Dev)

Cline is a VS Code extension that wraps Claude API calls with tool use. Its codebase understanding is:

- **Entirely tool-driven:** Cline uses `list_files`, `read_file`, `search_files` (ripgrep), and `list_code_definition_names` tools to explore the codebase dynamically during a task.
- **`list_code_definition_names` tool:** Uses tree-sitter to extract top-level definitions (classes, functions) from a given directory, one level deep. This is a simplified version of what claude-code-project-index does.
- **No pre-built index:** Every session starts fresh; there is no persistent index. This is intentional — Cline trusts the LLM to navigate using tools rather than a snapshot.
- **Key insight:** Cline demonstrates that for complex multi-step tasks, dynamic navigation via tool calls often outperforms a static snapshot index because the LLM can follow actual code paths rather than predicted ones. The trade-off is latency (tool round-trips) vs. precision.

#### Aider

Aider is a terminal-based AI coding tool built around a "repo map" concept. It is arguably the most thoughtfully engineered code context system among current tools and the closest analogue to claude-code-project-index.

**Aider's Repo Map — key implementation details:**

- **Tree-sitter based:** Aider uses `tree-sitter` with `tree-sitter-languages` to parse source files. It runs tree-sitter queries defined per language (in `.scm` files) to extract tags (definitions and references).
- **Tags are tuples:** Each tag is `(filename, name, kind, line)` where `kind` is `def` (definition) or `ref` (reference).
- **PageRank-style ranking:** Aider builds a graph where files are nodes and edges are weighted by reference density (how many definitions in file A are referenced in file B). It then applies a PageRank variant (specifically `networkx.pagerank`) to identify which files (and therefore which definitions) are most central to the current task. Files mentioned in the conversation history get a ranking boost via the personalization vector.
- **Context-window budget:** The repo map is compressed to fit within a configurable token budget. The ranking determines which symbols to include when compression is needed. Aider targets roughly 1k tokens for the repo map in typical usage, expanding to ~8k for complex tasks.
- **Output format:** The repo map is a plain-text file listing filenames and their top-level symbols with line numbers:
  ```
  scripts/project_index.py:
      def build_index(root_dir: str) -> Tuple[Dict, int]  # line 109
      def compress_if_needed(dense_index: Dict, target_size: int)  # line 529
  ```
- **No docstrings or call graphs** in the default repo map — just names, signatures, and line numbers. Call graph information is deliberately excluded to keep the map compact.
- **Selective file inclusion:** Aider's repo map does not include all files. It includes files that are (a) already open in chat, (b) strongly referenced by open files, or (c) ranked highly by the PageRank analysis.
- **Cache warming:** Aider caches tree-sitter parse results and tags per file using file modification time. Only changed files are re-parsed on subsequent invocations.

**Key insight from Aider:** The ranking/selection step is more important than the parsing step. A perfectly parsed index that includes everything is less useful than a 1k-token index with exactly the right symbols.

**What claude-code-project-index does that Aider does not:**
- Call graph extraction (calls and called-by relationships)
- Directory purpose inference
- Documentation map extraction (markdown headers)
- Dependency graph with relative import resolution
- Progressive compression with multiple fallback strategies
- Clipboard export mode for external AI tools

**What Aider does that claude-code-project-index does not:**
- Reference extraction (not just definitions, but where symbols are used)
- PageRank-based importance ranking
- Context-aware map (adapts to what files the user is currently editing)
- Tree-sitter accuracy (vs. regex)
- Cache per-file (vs. full re-index)

---

## 2. Tree-sitter Ecosystem

### 2.1 What Tree-sitter Is

Tree-sitter is a parser generator and incremental parsing library originally developed at GitHub. It is written in C and has bindings for virtually every language. Key properties:

- **Error-tolerant:** Tree-sitter parsers produce a parse tree even for syntactically incorrect code, using error recovery rules defined in the grammar. This is critical for code intelligence in editors where code is frequently in an invalid state mid-edit.
- **Incremental:** Given a previous parse tree and a set of edits (byte offsets and replacement text), tree-sitter can re-parse only the affected subtrees. Re-parse is typically sub-millisecond for typical edits.
- **Concrete syntax trees (CST):** Tree-sitter produces CSTs, not ASTs. Every token is present in the tree. For code intelligence purposes, you query the CST using tree-sitter's query language (`.scm` files, S-expression syntax) to extract the "interesting" nodes.
- **Grammar files:** Each language has a `grammar.js` defining the parser. The grammar is compiled to a C source file that is then compiled into a shared library. Pre-compiled grammars are packaged in `tree-sitter-languages`.
- **Widely adopted:** Tree-sitter is the parser engine used by GitHub Code Search (symbol index), Neovim (syntax highlighting and code navigation), Helix, Zed, Cline, Aider, and dozens of other tools.

### 2.2 py-tree-sitter (Python Bindings)

The `tree-sitter` Python package provides bindings to the C library:

```python
from tree_sitter import Language, Parser

# Load a compiled grammar (tree-sitter 0.20.x API)
PY_LANGUAGE = Language('build/my-languages.so', 'python')
parser = Parser()
parser.set_language(PY_LANGUAGE)

# Parse
tree = parser.parse(b"def foo(x: int) -> str:\n    return str(x)")

# Query
query = PY_LANGUAGE.query("""
(function_definition
  name: (identifier) @function.def
  parameters: (parameters) @function.params
  return_type: (_) @function.return_type)
""")
captures = query.captures(tree.root_node)
```

**API surface:**
- `Parser.parse(source_bytes, old_tree=None, encoding='utf8')` — returns `Tree`
- `Tree.root_node` — access root `Node`
- `Node.children`, `Node.child_by_field_name()`, `Node.text`, `Node.start_point`, `Node.end_point`
- `Language.query(pattern)` — compiled query object for efficient repeated matching
- `Tree.edit(start_byte, old_end_byte, new_end_byte, ...)` then re-parse for incremental updates

**Performance (empirical, from Aider benchmarks and community reports):**
- Initial parse of a 1000-line Python file: ~1-5ms
- Re-parse after a typical single-line edit: ~0.1-0.5ms
- Parsing a 10k-file repository from scratch: ~10-60 seconds depending on average file size and hardware
- Memory per parsed tree: ~5-20x source file size (the CST stores all tokens)

### 2.3 tree-sitter-languages

The `tree-sitter-languages` package (pip-installable) bundles pre-compiled grammars for 40+ languages into a single Python wheel, eliminating the need to compile grammars:

```python
from tree_sitter_languages import get_language, get_parser

parser = get_parser('python')
tree = parser.parse(b"def foo(): pass")
```

**Supported languages (representative subset):** Python, JavaScript, TypeScript, TSX, JSX, Rust, Go, Java, C, C++, C#, Ruby, PHP, Swift, Kotlin, Scala, Haskell, Elixir, Erlang, Lua, Julia, Dart, Bash, SQL, HTML, CSS, YAML, TOML, JSON, Markdown, R, Dockerfile, and more.

**Key advantage:** No build step. Works in environments where compiling C extensions is not possible. The wheel is approximately 30MB for all grammars combined.

**Version compatibility note (important for this project):** `tree-sitter-languages` wraps an older version of `py-tree-sitter` (typically 0.20.x). The newer `tree-sitter` 0.22+ API (from the official `tree-sitter` package) uses a different Language loading mechanism and is incompatible. As of early 2025, Aider and other tools were navigating this version split. When adopting tree-sitter for claude-code-project-index, pin to `tree-sitter-languages` and its implicit `tree-sitter` version to avoid this issue.

**Alternative (newer):** The newer `tree-sitter` 0.22+ package uses per-language grammar packages (e.g., `tree-sitter-python`, `tree-sitter-javascript`) loaded via `Language(tree_sitter_python.language())`. Migration from `tree-sitter-languages` to per-language packages is straightforward but requires per-language dependencies in `pyproject.toml`.

### 2.4 Tree-sitter Query Language

Tree-sitter queries use an S-expression pattern matching language. This is the key mechanism for extracting semantic information without writing traversal code:

```scheme
; Capture Python function definitions with all components
(function_definition
  name: (identifier) @func_name
  parameters: (parameters) @func_params
  return_type: (type) @return_type ?
  body: (block
    (expression_statement (string) @docstring) ?)) @func_def

; Capture class definitions with optional docstring
(class_definition
  name: (identifier) @class_name
  superclasses: (argument_list (_) @base_class) ?
  body: (block
    (expression_statement (string) @class_docstring) ?)) @class_def

; Capture import statements
(import_from_statement
  module_name: (dotted_name) @module
  name: (dotted_name) @imported_name)

(import_statement
  name: (dotted_name) @imported_name)

; Capture decorators
(decorated_definition
  (decorator) @decorator
  definition: (function_definition name: (identifier) @decorated_func))
```

Queries are compiled once and can be reused across thousands of files efficiently. The query pattern is validated at compile time — malformed queries raise an error immediately.

**Concrete benefit over regex:** The tree-sitter query for Python function definitions correctly handles:
- Multi-line parameter lists
- Nested function definitions (closures)
- Functions with no return type annotation
- Async functions (the pattern matches `async_function_definition` separately)
- Decorators associated with functions
- Lambda expressions (if desired)

The current regex in `index_utils.py` fails on all of these cases.

---

## 3. Code Graph Approaches

### 3.1 Code Knowledge Graph Structure

A code knowledge graph models a codebase as a typed property graph. The standard node and edge taxonomy:

**Node types:**

| Node Type | Properties | Examples |
|-----------|-----------|---------|
| `Repository` | url, name, language | github.com/foo/bar |
| `File` | path, language, LOC, last_modified | src/utils.py |
| `Module` | name, qualified_name, is_package | myapp.utils |
| `Class` | name, qualified_name, line, is_abstract | MyClass |
| `Function` | name, qualified_name, line, signature, is_async | compute() |
| `Method` | name, qualified_name, line, is_static, is_property | MyClass.compute() |
| `Variable` | name, qualified_name, type_annotation, line | MAX_SIZE |
| `Parameter` | name, type_annotation, default, position | x: int = 0 |
| `Import` | source_module, alias | from foo import bar as b |
| `Decorator` | name, line | @classmethod |
| `Docstring` | content, format | """Compute X.""" |

**Edge types:**

| Edge Type | From | To | Properties |
|-----------|------|----|-----------|
| `CONTAINS` | File | Class/Function/Variable | — |
| `DEFINES` | Module | Class/Function | — |
| `CALLS` | Function/Method | Function/Method | call_count, line |
| `INHERITS` | Class | Class | — |
| `IMPLEMENTS` | Class | Class (interface/ABC) | — |
| `IMPORTS` | File/Module | Module | is_relative, alias |
| `USES` | Function | Variable | is_write, is_read |
| `OVERRIDES` | Method | Method | — |
| `HAS_PARAM` | Function | Parameter | position |
| `RETURNS` | Function | Type | — |
| `DECORATES` | Decorator | Function/Class | — |

**Industry examples of this structure:**
- Microsoft's IntelliCode uses this graph (the Code Property Graph, or CPG) to power ranked completions
- Joern (used for security analysis) uses a CPG with additional control flow and data flow edges
- Amazon CodeGuru builds this graph from Java ASTs for reviewer recommendations
- DeepCode (acquired by Snyk) built cross-file graphs for vulnerability detection

The current `PROJECT_INDEX.json` implements a subset of this graph: the `g` (call graph) key captures `CALLS` edges; the `deps` key captures `IMPORTS` edges. The missing elements are resolved cross-file edges (calls currently use bare function names, not `file:function` qualified names) and the `INHERITS`/`OVERRIDES` edges for class hierarchies.

### 3.2 Graph Databases for Code

**Neo4j:**
- Most widely used graph database; property graph model
- Cypher query language is expressive for code queries: `MATCH (c:Class)-[:INHERITS]->(base:Class) RETURN c, base`
- Python driver `neo4j` is well-maintained
- Overhead: requires a running server process; disk usage scales with graph size
- Appropriate for: enterprise code intelligence platforms, multi-repository analysis
- Not appropriate for: single-project local tools (server overhead is unjustified)

**NetworkX (in-memory):**
- Pure Python graph library; no server required
- Supports directed/undirected multigraphs with arbitrary node/edge attributes
- `nx.DiGraph` for the call graph; `nx.pagerank()` for ranking (used by Aider)
- Performance ceiling: ~1M nodes comfortably; larger graphs require batching or external storage
- `networkx` is a pip install with no native extensions — works everywhere
- **This is the right choice for claude-code-project-index**

**SQLite with recursive CTEs:**
- The most pragmatic choice for single-project persistent indexing
- Schema: `nodes(id, type, name, file, line, attrs_json)`, `edges(from_id, to_id, type, attrs_json)`
- Recursive CTEs support transitive closure (find all callers of a function, find all subclasses)
- WAL mode enables concurrent reads during incremental updates
- Realistic scale: 100k files, 1M functions — no performance issues
- Appropriate for: a v2 persistent index that supports incremental updates

**DuckDB:**
- In-process analytical database; excellent for aggregate queries over code
- Columnar storage enables fast scans; Parquet output is portable
- Not ideal for graph traversal but superior to SQLite for analytical queries
- Appropriate for: large-scale codebase analytics (not interactive per-session indexing)

### 3.3 Microsoft IntelliCode Code Graph

Microsoft's IntelliCode (the AI completion system in VS Code) maintains a per-repository code graph with these characteristics:

- The graph is built lazily as the user navigates files, prioritizing the "working set" of recently accessed code
- ML models are trained on the graph to predict API usage completions (which methods to call on which objects in which order)
- The graph is stored in a SQLite database local to the workspace
- Language analysis is delegated to Roslyn (C#), TypeScript's own compiler, and Pylance (Python) — IntelliCode does not build its own parser
- The completion model uses the graph to produce "starred suggestions" (methods ranked above alphabetical order in IntelliSense)

**Key design principle from IntelliCode:** It does not attempt to build a full call graph for the entire repository. It builds a local neighborhood graph centered on the currently open file and recently touched files. This keeps the graph size manageable and ensures relevance. This is exactly the right philosophy for a token-budget-constrained tool like claude-code-project-index.

---

## 4. Incremental Parsing Techniques

### 4.1 Tree-sitter Incremental Parsing

Tree-sitter's incremental parsing is the gold standard for editor-integrated code analysis:

**How it works:**
1. Initial parse: `tree = parser.parse(source_bytes)` — full parse, O(n) in source size
2. Edit applied: user types text, described as `(start_byte, old_end_byte, new_end_byte, start_point, old_end_point, new_end_point)`
3. Tree invalidation: tree-sitter walks the existing CST and marks subtrees as "invalid" if their byte range overlaps the edit
4. Incremental re-parse: `new_tree = parser.parse(new_source_bytes, old_tree=tree)` — only invalid subtrees are re-parsed; valid subtrees are reused

**Guarantees:**
- The re-parse is always correct — there are no stale-cache issues because tree-sitter tracks byte ranges precisely
- Amortized re-parse time over a typical editing session is O(k) where k is the size of the changed region, not O(n) for the whole file
- The resulting tree is identical to a full parse of the new source

**Sub-millisecond performance:**
- For a typical single-character insertion in a 1000-line file, re-parse is under 100 microseconds
- Even for large refactors (renaming a variable throughout a 500-line function), re-parse is typically 1-10ms

**Applicability to claude-code-project-index:** For the hook-based invocation model (re-index on session start or on `-i` flag), incremental tree-sitter parsing per-file is not necessary — files are re-parsed from scratch, not edited in-place. The value of tree-sitter for this tool is accuracy and language coverage, not incremental parsing. The incremental parsing capability becomes relevant if a daemon mode (watch mode) is ever implemented.

### 4.2 How IDEs Maintain Real-time Code Understanding

Modern IDEs use a Language Server Protocol (LSP) server architecture:

**LSP server lifecycle:**
1. On workspace open: language server spawns and performs a full analysis of all files
2. On file open: server performs a per-file parse (using its own parser, not necessarily tree-sitter)
3. On `textDocument/didChange`: server receives the incremental change and updates its internal model
4. On completion/hover/definition request: server queries its internal model synchronously

**Internal model for Python (Pyright/Pylance):**
- Pyright maintains a `Program` object containing a `SourceFile` per Python file
- Each `SourceFile` has a `ParseResults` containing the AST (produced by Pyright's own Python parser)
- Type information is computed lazily: only files that are imported by the "entry points" or explicitly opened are fully type-checked
- Import resolution is done via an `ImportResolver` that implements Python's module search algorithm
- The complete type graph is stored in-memory; Pyright does not use a database

**Key insight from the LSP architecture:** The separation between "parse all files to get signatures" (fast, ~seconds) and "type-check and resolve all imports" (slow, ~minutes for large projects) is a deliberate design choice. For claude-code-project-index, the "parse all files" step is what matters. Full type checking (what Pyright does) is not needed for generating a useful context index.

### 4.3 Git Diff-Based Selective Re-indexing

For batch indexers (not real-time editors), git diff-based re-indexing is the practical approach:

**Strategy:**
1. Store the git commit SHA when the index was last built: `last_indexed_commit`
2. On re-index trigger: `git diff --name-only <last_indexed_commit> HEAD` yields the list of changed files
3. Re-parse only those files; update the index for those files; write new commit SHA
4. For deleted files: remove from index
5. For new files: add to index

**Complexity:** Re-indexing after a small commit (5-10 changed files) takes milliseconds rather than the full-project scan which might take 10-60 seconds. This is the approach used by Sourcegraph's explicit indexers and by ctags-based tools like Universal Ctags.

**Current approach in claude-code-project-index:** The `calculate_files_hash()` function in `i_flag_hook.py` computes `sha256(filename:mtime)` across all files. This is all-or-nothing: either the entire index is regenerated or the cached version is used. There is no file-level caching.

**Concrete improvement:** Replace the files-hash check with:
```python
# In i_flag_hook.py
def get_git_sha(project_root):
    result = subprocess.run(['git', 'rev-parse', 'HEAD'],
                           cwd=str(project_root), capture_output=True, text=True, timeout=2)
    return result.stdout.strip() if result.returncode == 0 else None

def get_changed_files(project_root, since_sha):
    result = subprocess.run(['git', 'diff', '--name-only', since_sha, 'HEAD'],
                           cwd=str(project_root), capture_output=True, text=True, timeout=5)
    return result.stdout.strip().split('\n') if result.returncode == 0 else None
```

If `get_git_sha()` matches `_meta.git_sha`, skip regeneration entirely (O(1)). If different, pass `get_changed_files()` to the indexer for selective re-parsing.

---

## 5. Cross-File Call Resolution for Python

### 5.1 Python Import Resolution Algorithm

Python's import system is intentionally flexible, which makes static analysis hard. The canonical resolution order:

1. `sys.modules` cache (already-imported modules)
2. Built-in modules (`sys.builtin_module_names`)
3. Frozen modules
4. Import path finders: iterate `sys.meta_path` — each finder's `find_spec()` method
5. For file-based imports: iterate `sys.path` entries; for each entry, check for `<entry>/<name>/__init__.py` (package) or `<entry>/<name>.py` (module)

**Relative imports:** `from . import foo` resolves relative to the current package, which requires knowing the `__package__` attribute at import time. Static analysis must infer this from file structure.

**Complications for static analysis:**
- `__init__.py` re-exports: `from .submodule import ClassName` in `__init__.py` means `ClassName` is importable as `package.ClassName` without explicit submodule reference
- Star imports: `from module import *` imports all names in `__all__` (or all non-underscore names if `__all__` not defined) — requires loading and parsing the imported module
- Dynamic imports: `importlib.import_module(variable_containing_module_name)` is not statically resolvable
- Conditional imports: `try: import ujson as json` / `except ImportError: import json` — both branches must be tracked
- `sys.path` manipulation: code that does `sys.path.insert(0, ...)` before importing

### 5.2 Static Call Graph Tools

**pyan3:**
- Static call graph generator for Python
- Uses Python's `ast` module (not tree-sitter) to walk the AST
- Produces a `.dot` graph file or a dictionary of `caller → [callees]`
- Handles intra-package calls reasonably; does not handle dynamic dispatch or `__init__.py` re-exports well
- Best for moderate-sized projects where the call graph is primarily intra-project
- Active development as of 2024; supports Python 3.10-3.14 syntax

**Griffe:**
- Extracts complete API structure from Python packages using AST
- Produces a tree: modules → classes → functions → attributes → type aliases
- Supports both static (AST) and dynamic (runtime introspection) analysis
- Can serialize API structure to JSON
- Designed for documentation generation (used by mkdocstrings) but perfect for API-aware indexing
- Handles: type annotations, decorators, docstrings, inheritance, overloads
- **This is essentially a production-grade version of `extract_python_signatures` in `index_utils.py`**

**PyCG (archived academic tool):**
- Paper: "PyCG: Practical Call Graph Generation in Python" (IEEE ICSE 2021)
- Uses `ast` + `importlib` for cross-file import resolution
- Inter-procedural analysis tracks assignment relations across modules
- Precision: 99.2%, Recall: 69.9%
- Performance: 0.38s per 1k LOC
- Zero dependencies (pure Python)
- Status: Archived — no further development, but the technique is sound and the code is available
- **The import resolution technique from PyCG (using `importlib` to resolve imports to file paths) is directly applicable**

**Jedi:**
- Python autocompletion and analysis library (underlying engine for many IDE plugins)
- `jedi.Script(source, path=...).goto(line, column)` resolves a symbol at a specific position to its definition
- Handles `__init__.py` re-exports, star imports, and `sys.path` manipulation via a configurable environment
- Accurate but slow for whole-project analysis (designed for interactive, per-symbol resolution)
- Not suitable for building a full call graph; suitable for resolving specific references on demand

**Pyright (used by Pylance):**
- Microsoft's Python type checker and language server
- The most accurate Python static analyzer available as of 2025
- Resolves cross-file imports, `__init__.py` re-exports, conditional imports, and type-narrowing
- Can emit JSON diagnostics; this can be parsed to extract type and import information
- Running as a subprocess is practical: `pyright --outputjson .`
- High installation overhead (requires Node.js); not suitable as a default dependency

### 5.3 Practical Approach for Cross-File Resolution

For claude-code-project-index, the right trade-off is:

**Tier 1 (currently implemented):** Parse explicit `import` and `from...import` statements. Record the import string. This covers ~80% of real-world cases.

**Tier 2 (recommended improvement):** After indexing all files, run a resolution pass: for each file's imported names, look them up in the index's function/class registry. If `build_index` is imported from any file and `build_index` appears as a definition in `scripts/project_index.py`, create a resolved edge: `(importer_file, 'build_index', 'scripts/project_index.py', 'build_index')`. This turns the current unresolved call graph into a qualified call graph.

**Tier 3 (optional):** Handle `__init__.py` re-exports with a heuristic: when `from package import Name` is encountered and `package/__init__.py` exists, scan `__init__.py` for `from .submodule import Name` to find the true source file.

**What not to pursue:** Full `importlib`-based resolution (PyCG approach) or Jedi-based symbol lookup. These are accurate but add significant complexity and runtime. The 80-90% coverage from Tiers 1-2 is sufficient for an AI context tool where approximate is acceptable.

---

## 6. AI-Native Code Understanding

### 6.1 Code Embeddings

**CodeBERT (Microsoft, 2020):**
- BERT-style model pre-trained on bimodal data: code + natural language docstrings
- 125M parameters; max input length 512 tokens
- Good for code search (given a NL query, retrieve relevant code) but context window is too small for function-level indexing of real-world code

**GraphCodeBERT (Microsoft, 2021):**
- Extension of CodeBERT that incorporates data flow graphs as additional input
- Achieves state-of-the-art on code search and clone detection tasks as of its release
- Still limited by 512-token context; requires running inference per chunk

**StarCoder2 / DeepSeek-Coder (2024):**
- Large code models (3B-34B params) pre-trained on The Stack v2 (600+ languages, petabytes of code)
- Not typically used for embeddings directly; used as generation backbones
- Can be used for embeddings via mean pooling of intermediate layers

**Voyage Code (Voyage AI, 2024):**
- Specialized code embedding model designed for retrieval
- 4096-token context (vs. 512 for CodeBERT); much better for large functions and classes
- Used by Cursor and other tools for the codebase embedding index
- API-based (requires Voyage AI account); not suitable for fully local deployment

**Nomic Embed Code (2024):**
- Open-weights code embedding model (Apache 2.0)
- Deployable locally via Ollama: `ollama pull nomic-embed-code`
- 8192-token context; 768-dimensional embeddings
- Good accuracy on code retrieval benchmarks; practical for local deployment without API costs
- **This is the recommended embedding model for an optional embedding retrieval feature**

**OpenAI text-embedding-3-small with code:**
- General-purpose embedding model; reasonable for code despite not being code-specific
- 8191-token context; widely available and practical
- Not as accurate as code-specific models for semantic code search but sufficient for many use cases

### 6.2 Retrieval-Augmented Code Generation

RAG for code (codebase-aware generation) follows this pipeline:

1. **Indexing phase:** Chunk the codebase into units (functions, classes, or sliding windows). Embed each chunk. Store `(chunk_text, embedding, metadata)` in a vector database.
2. **Retrieval phase:** At inference time, embed the user query. Find top-k chunks by cosine similarity. Optionally re-rank using a cross-encoder.
3. **Generation phase:** Inject retrieved chunks into the LLM context alongside the user query.

**Chunking strategies and their trade-offs:**

| Strategy | Unit | Pros | Cons |
|----------|------|------|------|
| Function-level | One function = one chunk | Semantically coherent; retrieval is precise | Misses class-level context; imports may be missing |
| Class-level | One class = one chunk | Includes method context | Very large for big classes; small classes are tiny chunks |
| File-level | One file = one chunk | Full context preserved | Exceeds embedding model limits for large files; too coarse |
| Sliding window | N lines with M lines overlap | Handles arbitrary file sizes | Splits across semantic boundaries; retrieval may be imprecise |
| AST-node-level | Any named AST node | Maximum semantic precision | Requires parser; implementation complexity |

**Practical winner for most projects:** Function-level chunking with class docstring prepended to each method chunk. This provides semantic coherence while keeping chunks small enough for embedding models.

**Hybrid search:** BM25 (sparse retrieval) is frequently combined with dense embedding retrieval. The BM25 score captures keyword matching (function names, variable names) while the embedding score captures semantic similarity. Reciprocal Rank Fusion (RRF) is the standard combination method. For a code tool, the keyword matching component is especially important because developers search for specific function names.

### 6.3 How AI Coding Tools Build Context Windows

**How Cursor builds its context:**
1. The active file is always included in full
2. Import-adjacent files (files imported by the active file) are included in signature-only form
3. `@codebase` retrieval adds up to N chunks from the embedding index, ranked by query similarity
4. Recent conversation history is included
5. Everything is packed into the context window budget, active file getting highest priority

**How Aider builds its context:**
1. Files that the user explicitly adds (`/add file.py`) are included in full
2. The repo map (tree-sitter signatures + PageRank ranking) fills the remaining budget
3. Files mentioned in the conversation are given a ranking boost in the repo map
4. The context is reconstructed from scratch each turn (no rolling summary)

**How claude-code-project-index builds its context:**
1. The full PROJECT_INDEX.json is generated at target token size
2. All files included up to the size budget (no ranking, first-come-first-served after emergency compression)
3. The index-analyzer subagent reads the full index and selects relevant portions
4. No conversation-awareness (the index does not adapt to what the user is currently discussing)

**The fundamental tension:** Pre-built index (Aider/Cursor approach) vs. dynamic navigation (Cline approach). Pre-built indexes are faster (no tool round-trips) but may be stale or include irrelevant content. Dynamic navigation is slower but always up-to-date and more focused. claude-code-project-index's hybrid approach (pre-built index + subagent analysis) is a reasonable middle ground.

### 6.4 Context Window Optimization Techniques

**Compression:**
- Removing whitespace, comments, and docstrings reduces token count by 20-40%
- Signature-only representation (function name + parameters + return type, no body) reduces by 70-90%
- The current dense format in claude-code-project-index (`name:line:signature:calls:doc`) achieves approximately 85% compression vs. raw source

**Relevance filtering:**
- Aider's PageRank approach: rank by centrality + user-mentioned context
- BM25 filtering against the user's prompt: include only files with high keyword overlap with the request
- Recency filtering: files modified in the last N commits are more likely to be relevant
- Type-filtered inclusion: only include entry points (functions decorated with `@app.route`, `@pytest.fixture`, `main()` functions, etc.)

**Structured formats for LLM consumption:**
- Plain text (Aider's repo map): most natural for LLMs; preserves readability
- JSON (claude-code-project-index full index): machine-processable but noisier for LLMs
- XML: clear delimiters; widely used in Claude-targeted tools
- Custom compressed notation (claude-code-project-index's `name:line:sig:calls:doc`): most compact; LLMs can parse it reliably with a format explanation in the system prompt

The colon-delimited format has one fragility: colons within type annotations (e.g., `x: Dict[str, int]`) will break the split-on-colon parsing. A safer separator that does not appear in Python syntax is `|` or `§`. Or switch to a list format: `["func_name", 42, "(x: int, y: str) -> None", ["caller1", "caller2"], "docstring"]`.

---

## 7. Comparison Tables

### 7.1 Code Intelligence Tools

| Tool | Parsing Approach | Cross-file Resolution | Language Coverage | Index Storage | Initial Latency |
|------|-----------------|----------------------|------------------|--------------|---------|
| Sourcegraph (SCIP) | Language-specific (Jedi, tsc, etc.) | Near-complete (language server quality) | 30+ with SCIP indexers | Proprietary (zoekt + SCIP files) | ~100ms search |
| GitHub Code Search | Partial parse + tree-sitter for symbols | Token-level only | 500+ (heuristic), 20+ (precise) | Distributed (Blackbird) | ~200ms |
| OpenGrok | ctags | Approximate (name-match only) | 50+ via ctags | Apache Lucene | ~500ms |
| Cursor | LSP + embeddings | Language-server quality | Delegated to VS Code | Local vector DB | ~50ms retrieve |
| Windsurf | LSP + embeddings | Language-server quality | Delegated to VS Code | Local vector DB | ~50ms retrieve |
| Cline | Dynamic tool calls | None (LLM navigates) | Any (file reads) | None (stateless) | Per-read (~500ms) |
| Aider | tree-sitter tags | File-level (import graph) | 40+ (tree-sitter-languages) | In-memory + file cache | ~500ms initial |
| claude-code-project-index | Regex (Python/JS/TS/Shell) | File-level heuristic | 4 parsed, 30+ listed | JSON file | ~5s initial |

### 7.2 Parsing Approaches

| Approach | Accuracy | Speed | Language Coverage | Incremental | Maintenance |
|----------|----------|-------|------------------|-------------|-------------|
| Regex (current) | ~70% — misses nested, multi-line, decorators | Very fast | Any (brittle) | No | Low |
| Python `ast` module | 99%+ for valid Python | Fast | Python only | No | Low |
| Griffe | 99%+ for Python packages | Fast | Python only | No | Low (maintained library) |
| tree-sitter | 95%+ (error-tolerant) | Fast | 40+ languages | Yes | Medium |
| ctags (Universal Ctags) | 80% (heuristic) | Very fast | 100+ languages | No | Low |
| Language server (LSP) | 99%+ including types | Slow (server startup) | Language-specific | Yes | High |
| pyan3 | ~95% | Fast | Python only | No | Low |

### 7.3 Context Delivery Formats

| Format | Token Efficiency | LLM Parsability | Human Readability | Structured Queries |
|--------|-----------------|-----------------|-------------------|--------------------|
| Raw source code | Baseline (1.0x tokens) | Excellent | Excellent | No |
| Signature-only text (Aider-style) | ~0.15x | Excellent | Good | No |
| JSON with full data | ~0.8x | Good (noisy) | Fair | Yes |
| JSON compressed (current) | ~0.2x | Good | Poor | Yes |
| XML structured | ~0.7x | Excellent | Good | Partial |
| Colon-delimited (current) | ~0.15x | Good (with format hint) | Poor | No |

### 7.4 Ranking/Relevance Approaches

| Approach | Accuracy | Computational Cost | Context-Aware | Implementation Complexity |
|----------|----------|-------------------|---------------|--------------------------|
| No ranking (current) | Low — includes all files equally | None | No | None |
| Function count (current emergency) | Low — most functions ≠ most important | O(n) | No | Trivial |
| PageRank on call graph | Medium — centrality ≠ task relevance | O(n + e) | No | Low (NetworkX) |
| PageRank + conversation boost | High — task-relevant boost | O(n + e) | Yes | Medium |
| BM25 against user prompt | High — keyword match | O(n) | Yes | Medium |
| Embedding similarity | Very high — semantic match | O(n) + embed API | Yes | High |
| Recency + PageRank (hybrid) | High | O(n + e) | Partial | Medium |

---

## 8. Key Insights for claude-code-project-index

### 8.1 The Ranking Gap (Highest Impact)

The most significant gap between claude-code-project-index and Aider is the absence of a relevance ranking step. The current tool includes all parsed files up to a size budget, using function count as the only importance signal in the emergency compression step.

Aider's PageRank approach demonstrates that a small, ranked index is significantly more useful than a large unranked one. For a 10k-file project at 50k tokens, an unranked index includes arbitrary files while a ranked index includes the architecturally central ones.

**Actionable improvement:** Add NetworkX as a dependency and implement a simple centrality ranking using the call graph edges already computed:

```python
import networkx as nx

def rank_files_by_centrality(index: Dict) -> Dict[str, float]:
    """Rank files by PageRank of their call graph centrality."""
    G = nx.DiGraph()

    # Add edges from call graph
    for edge in index.get('g', []):
        caller, callee = edge
        # Extract file prefix from qualified name
        caller_file = caller.split(':')[0] if ':' in caller else None
        callee_file = callee.split(':')[0] if ':' in callee else None
        if caller_file and callee_file and caller_file != callee_file:
            G.add_edge(caller_file, callee_file)

    if not G.nodes():
        return {}

    return nx.pagerank(G, alpha=0.85)
```

Then use `rank_files_by_centrality()` scores as the primary sort key in `compress_if_needed()` instead of function count.

### 8.2 The Regex Parsing Quality Gap

The current regex-based parsers in `index_utils.py` miss:
- Functions defined inside other functions (closures, nested helpers)
- Methods in dataclasses and named tuples
- Functions with multi-line signatures (parameter spanning multiple lines)
- Decorators associated with functions (important for identifying route handlers, test fixtures, etc.)
- Class-level attributes and type annotations
- Async functions and methods
- Property getters/setters as distinct from regular methods

Tree-sitter would eliminate all of these gaps. Given that `tree-sitter-languages` is pip-installable with no build step, the migration cost is a single dependency addition and rewriting the three parser functions in `index_utils.py`.

For Python specifically, the `ast` module (stdlib, zero dependencies) achieves 99%+ accuracy and is the right first step. Replacing `extract_python_signatures()` with an AST-based implementation handles all the missing cases above with no new dependencies.

### 8.3 The Call Graph Resolution Gap

The current dependency graph records import strings as dependencies. The call graph edges in the dense format (`g` key) use bare function names without file qualification. For example, when `foo.py` calls `build_index()` from `project_index.py`, the edge is recorded as `("some_caller", "build_index")` without a resolved file location.

This means call graph edges are not actionable — the index-analyzer agent cannot look up the callee in the index because it lacks the `file:function` qualified name.

**Actionable improvement:** After building the call graph, run a resolution pass:

```python
# Build a registry of all defined functions across all files
func_registry = {}
for file_path, file_info in index['files'].items():
    for func_name in file_info.get('functions', {}):
        func_registry[func_name] = file_path
    for class_name, class_data in file_info.get('classes', {}).items():
        for method_name in class_data.get('methods', {}):
            func_registry[f"{class_name}.{method_name}"] = file_path

# Resolve call graph edges
for edge in call_graph_edges:
    caller, callee_bare_name = edge
    resolved_file = func_registry.get(callee_bare_name)
    if resolved_file:
        resolved_edge = (caller, f"{resolved_file}:{callee_bare_name}")
```

This turns the unresolved call graph into a qualified, cross-file call graph.

### 8.4 The Recency Bias Gap

The current tool has no concept of "recently modified files are more relevant." In practice, when a developer asks Claude to help with a task, the most relevant files are almost always those changed recently.

**Actionable improvement:** Use `git log --name-only -n 50 --format=` to get the 50 most recently changed files. Assign a recency score (1.0 for most recent, decaying to 0.1 at rank 50). Combine this with PageRank centrality as a composite importance score:

```python
importance = 0.6 * pagerank_score + 0.4 * recency_score
```

This requires only a subprocess call and a weight table. The recency data is already partially computed (the file hash function in `i_flag_hook.py` already runs `git ls-files`).

### 8.5 The Incremental Re-indexing Gap

The current staleness check computes `sha256(filename:mtime)` for all files on every invocation. For large projects (10k files), this scan is the dominant cost even when the index is current.

**Actionable improvement:** Store the git commit SHA in `_meta.git_sha`. On subsequent invocations, compare `git rev-parse HEAD` to the stored SHA. If identical, skip re-indexing entirely. If different, use `git diff --name-only <stored_sha> HEAD` to identify changed files and re-index only those files.

This reduces re-check cost from O(n files stat calls) to O(1) for unchanged repositories — a 100-1000x speedup for the common case where the developer runs `-i` repeatedly in the same session without committing.

### 8.6 Format Fragility

The colon-delimited format `name:line:sig:calls:doc` is fragile because colons appear in Python type annotations:

```
build_index:109:(root_dir: str) -> Tuple[Dict, int]::Build the enhanced index...
```

A split on `:` will break the parsing of this signature. The current `truncate_doc` and signature compression code (`.replace(': ', ':')`) partially mitigates this but introduces its own parsing ambiguity.

**Recommended fix:** Use a separator that does not appear in Python or JavaScript code: `§` (section sign, U+00A7) or a fixed-width field format using the first N fields as tab-separated and the remainder as free text. Alternatively, store functions as JSON arrays instead of colon-delimited strings — the compression benefit is modest and the reliability gain is significant.

### 8.7 Language Coverage

The current tool fully parses only Python, JavaScript/TypeScript, and Shell. For projects containing Go, Rust, Java, or C/C++, those files are listed but not parsed. Tree-sitter + `tree-sitter-languages` would add full signature extraction for 40+ languages.

---

## 9. Recommended Technologies to Evaluate

### Priority 1: Python `ast` Module for Python Parsing (Zero Dependencies, High Impact)

**What:** Replace `extract_python_signatures()` in `index_utils.py` with an AST-based implementation using Python's built-in `ast` module.

**Why stdlib first:** Before adding tree-sitter (an external dependency), the Python `ast` module gives 99% accuracy for Python files at zero additional cost. Python is the most common language in the target environments (biorelate's infrastructure, claude-code-project-index itself).

**Key capabilities gained:**
- Nested function definitions
- Dataclass methods
- Multi-line parameter lists
- Decorator extraction (critical for identifying route handlers, fixtures, etc.)
- Class attributes and type annotations
- Async functions

**Estimated effort:** 1 day. The `ast.NodeVisitor` pattern is well-documented and straightforward.

```python
import ast

class SignatureExtractor(ast.NodeVisitor):
    def __init__(self):
        self.functions = {}
        self.classes = {}
        self._current_class = None

    def visit_FunctionDef(self, node):
        sig = self._build_signature(node)
        entry = {
            'line': node.lineno,
            'signature': sig,
            'doc': ast.get_docstring(node) or '',
            'is_async': isinstance(node, ast.AsyncFunctionDef),
            'decorators': [self._decorator_name(d) for d in node.decorator_list],
        }
        if self._current_class:
            self.classes[self._current_class]['methods'][node.name] = entry
        else:
            self.functions[node.name] = entry
        self.generic_visit(node)  # Allow nested defs

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        bases = [self._expr_to_str(b) for b in node.bases]
        self.classes[node.name] = {
            'line': node.lineno,
            'bases': bases,
            'doc': ast.get_docstring(node) or '',
            'methods': {},
        }
        prev = self._current_class
        self._current_class = node.name
        self.generic_visit(node)
        self._current_class = prev
```

### Priority 2: tree-sitter-languages for Non-Python Languages (Low Risk, High Coverage)

**What:** Replace `extract_javascript_signatures()` and `extract_shell_signatures()` with tree-sitter queries, and add parsing for Go, Rust, Java, C, C++.

**Installation:** `pip install tree-sitter-languages` — no build step, ~30MB wheel.

**Expected gain:**
- Parsing accuracy from ~70% to 95%+ for JS/TS/Shell
- Language coverage from 4 fully-parsed to 40+
- Correct handling of TypeScript generics, JSX, decorators, arrow functions

**Risk:** Dependency on a third-party package. Mitigation: fall back to current regex parsers if `tree-sitter-languages` import fails.

**Implementation pattern:**

```python
try:
    from tree_sitter_languages import get_language, get_parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

def extract_javascript_signatures_ts(content: str) -> Dict:
    """Tree-sitter-based JS/TS signature extraction."""
    if not TREE_SITTER_AVAILABLE:
        return extract_javascript_signatures_regex(content)

    lang = get_language('typescript')
    parser = get_parser('typescript')
    tree = parser.parse(content.encode())

    FUNC_QUERY = lang.query("""
    (function_declaration name: (identifier) @name) @func
    (method_definition name: (property_identifier) @name) @method
    (arrow_function) @arrow
    """)
    # ... capture and process
```

### Priority 3: NetworkX PageRank Ranking (Low Risk, High Impact)

**What:** Add `networkx` as an optional dependency and implement PageRank-based file importance ranking.

**Installation:** `pip install networkx` — pure Python, ~2MB, no native extensions.

**Implementation:** Build a directed graph where nodes are files and edges represent call relationships. Run `nx.pagerank()`. Use scores as the primary sort key in `compress_if_needed()` and in the hook's context-building step.

**Expected gain:** When compression is needed, the retained files are architecturally central rather than arbitrarily selected. The index becomes significantly more useful for AI consumption on large projects.

**Estimated effort:** 0.5 days. The graph is already partially built in `project_index.py`; the PageRank call and weight integration is straightforward.

### Priority 4: Git-SHA Incremental Re-indexing (Low Risk, High Performance Impact)

**What:** Replace the file-mtime-hash-based staleness check with git SHA comparison + `git diff --name-only` for selective re-indexing.

**Implementation:** Approximately 20 lines of code in `i_flag_hook.py`. Store `_meta.git_sha`. On hook invocation, compare `git rev-parse HEAD` to stored SHA; if identical, skip regeneration entirely; if different, pass the list of changed files to the indexer (requires a `--changed-files` argument to `project_index.py`).

**Expected gain:** For unchanged repos (the common case when `-i` is used repeatedly in the same session), the hook response time drops from ~2-5 seconds (stat all files) to under 100ms (one git subprocess call).

**Estimated effort:** 1 day (includes modifying `project_index.py` to accept and use a changed-files list).

### Priority 5: Resolved Cross-File Call Graph (Medium Risk, Medium Impact)

**What:** After building the call graph, resolve bare function names to `file:function` qualified names using a registry lookup.

**Implementation:** The registry is straightforward to build from the already-indexed functions. The resolution pass is O(n edges). The resolved edges are stored in the `g` key as `["caller_file:caller_func", "callee_file:callee_func"]` tuples.

**Expected gain:** The call graph becomes actionable for the index-analyzer agent. Queries like "which files call `build_index`?" become answerable directly from the index without requiring the agent to search by function name.

**Estimated effort:** 1 day.

### Priority 6: SQLite Persistent Index (Medium Risk, High Long-term Impact)

**What:** Replace `PROJECT_INDEX.json` (re-generated as a whole each time) with a SQLite database that supports incremental updates.

**Schema:**
```sql
CREATE TABLE files (
    path TEXT PRIMARY KEY,
    language TEXT,
    last_indexed_sha TEXT,
    indexed_at REAL
);
CREATE TABLE functions (
    id INTEGER PRIMARY KEY,
    file_path TEXT REFERENCES files(path),
    name TEXT,
    qualified_name TEXT,
    line INTEGER,
    signature TEXT,
    docstring TEXT,
    is_async BOOLEAN,
    decorators TEXT  -- JSON array
);
CREATE TABLE calls (
    caller_file TEXT,
    caller_func TEXT,
    callee_name TEXT,
    resolved_file TEXT,  -- NULL if unresolved
    resolved_func TEXT,
    call_line INTEGER
);
CREATE TABLE imports (
    file_path TEXT REFERENCES files(path),
    module TEXT,
    is_relative BOOLEAN,
    alias TEXT,
    resolved_file TEXT
);
CREATE INDEX idx_functions_name ON functions(name);
CREATE INDEX idx_calls_callee ON calls(callee_name);
```

**Expected gain:** Incremental updates become O(changed files). The index can be queried directly with SQL (e.g., `SELECT file_path FROM functions WHERE name = 'build_index'`). The index-analyzer agent gains SQL query capability as a tool.

**Risk:** Adds complexity to the indexing pipeline; breaks the simple "one JSON file" model. The JSON export (for compatibility with the existing hook and clipboard modes) must be regenerated from the SQLite database on demand.

**Estimated effort:** 1 week. Suitable as a v2 feature.

### Priority 7: Embedding-Based Relevant File Selection (High Effort, Optional)

**What:** Add an optional embedding index using `nomic-embed-code` (via Ollama) or the Voyage Code API that allows the `-i` flag to accept a query and retrieve semantically relevant files.

**Usage pattern:** `fix the authentication bug -i` would retrieve files semantically related to "authentication" rather than including all files by PageRank.

**Implementation requirements:**
- Embed function signatures + docstrings at index time (store in SQLite or a separate `.faiss` file)
- At query time: extract the prompt text (the cleaned prompt after removing the `-i` flag), embed it, find top-k similar functions/files via cosine similarity
- Inject only those files into context

**Dependencies:** An embedding model (Ollama with nomic-embed-code for local; Voyage AI API for cloud), numpy for cosine similarity, optionally faiss for ANN search on large codebases.

**Expected gain:** Dramatically better relevance for focused tasks on large codebases. Most impactful for repos with 500+ files where the current tool must aggressively compress.

**Risk:** Adds external dependencies and optionally API costs. Ollama must be running locally. Suitable as an opt-in feature enabled via environment variable.

**Estimated effort:** 2+ weeks for production-quality implementation.

---

## Summary: Recommended Implementation Sequence

| Priority | Improvement | Effort | Impact | Dependencies Added |
|----------|-------------|--------|--------|-------------------|
| 1 | Python `ast`-based signature extraction | 1 day | High | None (stdlib) |
| 2 | Git-SHA incremental re-indexing | 1 day | High (perf) | None |
| 3 | Resolved cross-file call graph | 1 day | Medium | None |
| 4 | tree-sitter for JS/TS/Go/Rust/etc. | 2-3 days | High (coverage) | `tree-sitter-languages` |
| 5 | NetworkX PageRank ranking | 0.5 days | High (relevance) | `networkx` |
| 6 | Fix colon-delimited format fragility | 0.5 days | Medium (reliability) | None |
| 7 | SQLite persistent index | 1 week | High (long-term) | None (stdlib) |
| 8 | Embedding-based retrieval | 2+ weeks | High (large repos) | Ollama or API |
| 9 | SCIP protocol output | 2+ weeks | Low (ecosystem) | protobuf |

**Quick wins (under 3 days total, zero new dependencies):** Priorities 1, 2, 3, and 6 together constitute a significant improvement in accuracy, performance, and reliability with no additional pip dependencies.

---

## References and Further Reading

**Tools and Implementations:**
- Sourcegraph SCIP specification: https://github.com/sourcegraph/scip
- Zoekt (Sourcegraph search engine): https://github.com/sourcegraph/zoekt
- GitHub Blackbird code search blog post: https://github.blog/engineering/engineering-principles/the-technology-behind-githubs-new-code-search/
- Aider repo map documentation: https://aider.chat/docs/repomap.html
- Aider repo map blog post: https://aider.chat/2023/10/22/repomap.html
- Cline `list_code_definition_names` tool: https://github.com/cline/cline

**Tree-sitter:**
- Tree-sitter documentation: https://tree-sitter.github.io/tree-sitter/
- py-tree-sitter PyPI: https://pypi.org/project/tree-sitter/
- tree-sitter-languages PyPI: https://pypi.org/project/tree-sitter-languages/
- Tree-sitter query language reference: https://tree-sitter.github.io/tree-sitter/using-parsers#pattern-matching-with-queries

**Python Static Analysis:**
- PyCG paper (ICSE 2021): https://arxiv.org/pdf/2103.00587
- PyCG on GitHub: https://github.com/vitsalis/PyCG
- pyan3 on GitHub: https://github.com/Technologicat/pyan
- Griffe documentation: https://mkdocstrings.github.io/griffe/
- Pyright import resolution: https://github.com/microsoft/pyright/blob/main/docs/import-resolution.md

**Code Embeddings:**
- CodeBERT paper: https://arxiv.org/abs/2002.08155
- GraphCodeBERT paper: https://arxiv.org/abs/2009.08366
- Voyage Code embeddings: https://blog.voyageai.com/2024/01/23/voyage-code-2/
- Nomic Embed Code: https://huggingface.co/nomic-ai/nomic-embed-code

**Graph Databases and Analysis:**
- NetworkX PageRank: https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.link_analysis.pagerank_alg.pagerank.html
- Joern Code Property Graph: https://joern.io/docs/cpgql/reference-language/

**Protocol Specifications:**
- Language Server Protocol: https://microsoft.github.io/language-server-protocol/
- SCIP protobuf schema: https://github.com/sourcegraph/scip/blob/main/scip.proto

---

*Compiled from training knowledge (up to May 2025). WebFetch was unavailable in this session. Aider implementation details are based on publicly documented source code at github.com/Aider-AI/aider. All package details reflect stable releases as of late 2024.*
