# ast-grep (sg) Research: Multi-Language Code Intelligence and Indexing

**Date:** 2026-03-17
**Context:** Evaluation for augmenting claude-code-project-index's regex-based parser with ast-grep for languages without native support (Go, Rust, Java, Ruby, C/C++, etc.)

---

## 1. What Is ast-grep?

ast-grep (`sg`) is a CLI tool for **structural code search, lint, and rewriting** built in Rust on top of tree-sitter parsers. It matches code by Abstract Syntax Tree (AST) structure rather than text, making it immune to whitespace/formatting differences and capable of understanding syntactic intent.

**Key interfaces:**
- CLI binary (`sg` / `ast-grep`) — subprocess invocation from Python
- Python native bindings (`ast-grep-py` / `ast_grep_py` on PyPI) — PyO3-based, no subprocess overhead
- Node.js bindings (`@ast-grep/napi`)
- LSP server for IDE integration
- WebAssembly module (`@ast-grep/wasm`)

**Installation:**
```bash
# CLI binary (recommended for subprocess usage)
brew install ast-grep                  # macOS
cargo install ast-grep                 # from crates.io
npm install -g @ast-grep/cli           # via npm
pip install ast-grep-cli               # Python wrapper that bundles the binary

# Python native bindings (no subprocess)
pip install ast-grep-py
```

---

## 2. Language Support Matrix

ast-grep has **built-in support for 34 languages** (as of 2025). All target languages for this project are supported:

| Language | Aliases | File Extensions |
|----------|---------|----------------|
| **Go** | `go`, `golang` | `.go` |
| **Rust** | `rs`, `rust` | `.rs` |
| **Java** | `java` | `.java` |
| **Ruby** | `rb`, `ruby` | `.rb`, `.rbw`, `.gemspec` |
| **C** | `c` | `.c`, `.h` |
| **C++** | `cc`, `c++`, `cpp`, `cxx` | `.cc`, `.hpp`, `.cpp`, `.c++`, `.hh`, `.cxx`, `.cu`, `.ino` |
| **Python** | `py`, `python` | `.py`, `.py3`, `.pyi`, `.bzl` |
| **JavaScript** | `javascript`, `js`, `jsx` | `.cjs`, `.js`, `.mjs`, `.jsx` |
| **TypeScript** | `ts`, `typescript` | `.ts`, `.cts`, `.mts` |
| **TSX** | `tsx` | `.tsx` |
| **C#** | `cs`, `csharp` | `.cs` |
| **Kotlin** | `kotlin`, `kt` | `.kt`, `.kts` |
| **Swift** | `swift` | `.swift` |
| **Scala** | `scala` | `.scala`, `.sc`, `.sbt` |
| **PHP** | `php` | `.php` |
| **Elixir** | `ex`, `elixir` | `.ex`, `.exs` |
| **Haskell** | `hs`, `haskell` | `.hs` |
| **Lua** | `lua` | `.lua` |
| **Bash** | `bash` | `.sh`, `.bash`, `.zsh`, etc. |
| **HTML** | `html` | `.html`, `.htm`, `.xhtml` |
| **CSS** | `css` | `.css` |
| **JSON** | `json` | `.json` |
| **YAML** | `yml` | `.yml`, `.yaml` |
| **HCL** | `hcl` | `.hcl` |
| **Nix** | `nix` | `.nix` |
| **Solidity** | `solidity`, `sol` | `.sol` |

Language is detected from file extension by default. Override via `--lang` flag or `languageGlobs` config.

---

## 3. Pattern Matching Syntax

### 3.1 Core Principle

Patterns are written as **valid code fragments** that tree-sitter can parse. ast-grep converts them to AST and uses structural matching — not text matching. This means:

- Whitespace differences don't matter
- Comments inside matched code are ignored
- Operator precedence is respected

### 3.2 Metavariable Syntax

| Syntax | Matches | Example |
|--------|---------|---------|
| `$NAME` | Any single named AST node | `$FUNC`, `$ARG` |
| `$_` | Any single node (non-capturing) | Skip nodes you don't care about |
| `$$VAR` | Any single unnamed node (punctuation/operators) | `$$OP` |
| `$$$ARGS` | Zero or more consecutive nodes (multi-match) | `$$$PARAMS`, `$$$BODY` |

**Rules:**
- `$NAME` must use UPPERCASE letters, underscores, digits 1-9 only
- Invalid: `$invalid`, `$Svalue`, `$123`, `$KEBAB-CASE`
- Same-named variables enforce identical content: `$A == $A` matches `x == x` but not `x == y`
- Prefix with `_` to suppress capture tracking: `$_NAME` (performance optimization)
- `$$$ARGS` cannot have `constraints:` applied to it (only single metavariables support constraints)

### 3.3 Pattern Object Form (with context/selector)

When a plain pattern is ambiguous or fails to parse, use the object form:

```yaml
rule:
  pattern:
    context: 'class A { public void $METHOD($$$ARGS) { $$$BODY } }'
    selector: method_declaration
```

`context` provides the surrounding valid code; `selector` picks the node type to actually match. This is essential for Go (function calls vs type conversions), C (statements), Java (methods in classes), and JSON (partial objects).

---

## 4. CLI Usage: `sg run`

### 4.1 Core Flags

```bash
sg run -p 'PATTERN' -l LANG [PATH] [FLAGS]

-p, --pattern   AST pattern to match
-l, --lang      Language (go, rust, java, python, etc.)
--json[=STYLE]  Output JSON: pretty (default), stream, compact
-r, --rewrite   Replacement string
--stdin         Read code from stdin
--globs         gitignore-style file filters
-j, --threads   Thread count for parallel processing
-A/-B/-C        Lines after/before/around matches (like grep)
--debug-query   Print the parsed AST for debugging
```

### 4.2 JSON Output Format

```bash
sg run -p 'func $NAME($$$ARGS) $$$RET {$$$BODY}' -l go --json=stream ./
```

Each match (in stream mode) is a JSON object on its own line:

```json
{
  "text": "func NewServer(addr string) *Server { ... }",
  "range": {
    "byteOffset": { "start": 1024, "end": 1200 },
    "start": { "line": 42, "column": 0 },
    "end": { "line": 48, "column": 1 }
  },
  "file": "server/server.go",
  "lines": "func NewServer(addr string) *Server {",
  "language": "Go",
  "metaVariables": {
    "single": {
      "NAME": { "text": "NewServer", "range": { ... } },
      "RET": { "text": "*Server", "range": { ... } }
    },
    "multi": {
      "ARGS": [
        { "text": "addr string", "range": { ... } }
      ],
      "BODY": [ ... ]
    },
    "transformed": {}
  }
}
```

**Key fields:**
- `text`: full matched source text
- `range.start.line` / `range.start.column`: zero-based position
- `file`: relative path from cwd
- `metaVariables.single`: captured single-node variables
- `metaVariables.multi`: captured `$$$` multi-node variables

### 4.3 `sg scan` vs `sg run`

| | `sg run` | `sg scan` |
|-|---------|----------|
| Use case | Ad-hoc single pattern | Multiple YAML rules, CI lint |
| Input | `-p PATTERN` on CLI | `-c sgconfig.yml` config file |
| Output | Matches only | Matches + severity + ruleId + message |
| JSON extras | None | `ruleId`, `severity`, `note`, `message` |

For indexing, `sg run` per-pattern is simpler. `sg scan` with YAML rules is better for a pre-defined rule set.

---

## 5. YAML Rule Definitions

### 5.1 Rule Structure

```yaml
id: find-public-functions       # required, unique
language: go                    # required
severity: hint                  # hint | info | warning | error | off
message: "Found public function $NAME"
rule:                           # required: the matching logic
  pattern: func $NAME($$$ARGS) $$$RET { $$$BODY }
constraints:                    # optional: filter captured variables
  NAME:
    regex: '^[A-Z]'            # only match exported (capitalized) names
files:                          # optional: glob patterns to include
  - "**/*.go"
ignores:                        # optional: glob patterns to exclude
  - "*_test.go"
```

### 5.2 Rule Operators

**Atomic rules** (examine the node itself):
```yaml
pattern: func $NAME($$$ARGS) { $$$BODY }   # structural match
kind: function_declaration                  # node type match
regex: '^Test'                              # text regex match (whole node text)
nthChild: 1                                # position in parent (1-based)
```

**Relational rules** (examine node relationships):
```yaml
inside:                    # this node is contained within...
  kind: impl_block
has:                       # this node contains...
  kind: async_modifier
  stopBy: end              # search depth: "neighbor" (default) | "end" | Rule
follows:                   # comes after (sibling)
  kind: use_declaration
precedes:                  # comes before (sibling)
  kind: function_item
```

**Composite rules** (combine sub-rules):
```yaml
all:                       # must match ALL
  - pattern: fn $NAME($$$ARGS) -> $RET { $$$BODY }
  - has:
      kind: visibility_modifier
any:                       # must match at least ONE
  - kind: function_item
  - kind: method_definition
not:                       # must NOT match
  has:
    kind: unsafe_modifier
matches: my-utility-rule   # reference to a utils: entry by ID
```

### 5.3 Constraint Syntax

```yaml
constraints:
  NAME:
    regex: '^[A-Z][a-z]+'  # regex on the captured text
  ARG:
    kind: string_literal    # must be this node kind
```

**Limitation:** Constraints only apply to single metavariables (`$NAME`), not multi-node captures (`$$$ARGS`).

---

## 6. Language-Specific Patterns for Code Indexing

### 6.1 Go

Go patterns often need `context`/`selector` due to parsing ambiguity between function calls and type conversions.

```yaml
# Function declarations
- id: go-functions
  language: go
  rule:
    kind: function_declaration

# Exported functions only
- id: go-exported-functions
  language: go
  rule:
    kind: function_declaration
    has:
      field: name
      regex: '^[A-Z]'

# Method declarations (with receiver)
- id: go-methods
  language: go
  rule:
    kind: method_declaration

# Struct type definitions
- id: go-structs
  language: go
  rule:
    kind: type_declaration
    has:
      kind: type_spec
      has:
        kind: struct_type

# Interface type definitions
- id: go-interfaces
  language: go
  rule:
    kind: type_declaration
    has:
      kind: type_spec
      has:
        kind: interface_type

# Function calls (requires context due to Go ambiguity)
- id: go-fmt-println
  language: go
  rule:
    pattern:
      context: 'func t() { fmt.Println($A) }'
      selector: call_expression
```

**Important:** For Go, `fmt.Println($A)` as a bare pattern will fail. Always use `context`/`selector` for function call patterns in Go.

### 6.2 Rust

```yaml
# Function definitions
- id: rust-functions
  language: rust
  rule:
    kind: function_item

# Public functions only
- id: rust-pub-functions
  language: rust
  rule:
    kind: function_item
    has:
      kind: visibility_modifier
      regex: '^pub'

# Unsafe functions
- id: rust-unsafe-functions
  language: rust
  rule:
    kind: function_item
    has:
      kind: function_modifiers
      regex: "^unsafe"

# Struct definitions
- id: rust-structs
  language: rust
  rule:
    kind: struct_item

# Trait definitions
- id: rust-traits
  language: rust
  rule:
    kind: trait_item

# Impl blocks
- id: rust-impls
  language: rust
  rule:
    kind: impl_item

# Impl blocks for a specific type (pattern form)
- id: rust-impl-pattern
  language: rust
  rule:
    pattern: impl $TYPE { $$$BODY }

# Enum definitions
- id: rust-enums
  language: rust
  rule:
    kind: enum_item
```

**Rust kind names** (from tree-sitter-rust):
- `function_item` — `fn foo() {}`
- `impl_item` — `impl Foo {}`
- `trait_item` — `trait Bar {}`
- `struct_item` — `struct Baz {}`
- `enum_item` — `enum Qux {}`
- `type_item` — `type Alias = ...`
- `visibility_modifier` — `pub`, `pub(crate)`
- `function_modifiers` — `unsafe`, `async`, `const`, `extern`

### 6.3 Java

Java methods must be found inside class context:

```yaml
# Class declarations
- id: java-classes
  language: java
  rule:
    kind: class_declaration

# Method declarations (need class context)
- id: java-methods
  language: java
  rule:
    pattern:
      context: 'class A { $MOD $RET $NAME($$$ARGS) { $$$BODY } }'
      selector: method_declaration

# Or using kind directly
- id: java-methods-kind
  language: java
  rule:
    kind: method_declaration

# Interface declarations
- id: java-interfaces
  language: java
  rule:
    kind: interface_declaration

# Field declarations of specific type
- id: java-string-fields
  language: java
  rule:
    kind: field_declaration
    has:
      field: type
      regex: '^String$'

# Constructor declarations
- id: java-constructors
  language: java
  rule:
    kind: constructor_declaration

# Public methods only
- id: java-public-methods
  language: java
  rule:
    kind: method_declaration
    has:
      kind: modifiers
      has:
        kind: modifier
        regex: '^public$'
```

### 6.4 Ruby

```yaml
# Method definitions
- id: ruby-methods
  language: ruby
  rule:
    kind: method

# Or pattern form
- id: ruby-method-pattern
  language: ruby
  rule:
    pattern: def $NAME($$$ARGS) $$$BODY end

# Singleton methods (class methods: def self.foo)
- id: ruby-class-methods
  language: ruby
  rule:
    kind: singleton_method

# Class definitions
- id: ruby-classes
  language: ruby
  rule:
    kind: class

# Module definitions
- id: ruby-modules
  language: ruby
  rule:
    kind: module

# Block pattern (select with block)
- id: ruby-select-shorthand
  language: ruby
  rule:
    pattern: $LIST.$ITER { |$V| $V.$METHOD }
```

**Ruby kind names** (from tree-sitter-ruby):
- `method` — `def foo`
- `singleton_method` — `def self.foo`
- `class` — `class Foo`
- `module` — `module Bar`

### 6.5 C / C++

C patterns often need context/selector due to how tree-sitter-c parses fragments:

```yaml
# C function definitions (kind approach)
- id: c-functions
  language: c
  rule:
    kind: function_definition

# C function declarations (prototypes in headers)
- id: c-function-decls
  language: c
  rule:
    kind: declaration
    has:
      kind: function_declarator

# C++ class definitions
- id: cpp-classes
  language: cpp
  rule:
    kind: class_specifier

# C++ function definitions
- id: cpp-functions
  language: cpp
  rule:
    kind: function_definition

# C++ method definitions
- id: cpp-methods
  language: cpp
  rule:
    kind: function_definition
    inside:
      kind: class_specifier

# C call expression (needs context)
- id: c-calls
  language: c
  rule:
    pattern:
      context: 'void f() { $FUNC($$$ARGS); }'
      selector: call_expression

# Struct definitions
- id: c-structs
  language: c
  rule:
    kind: struct_specifier
```

**Note on C/C++:** `languageGlobs` can be used to parse `.h` files as C++ if needed:
```yaml
# sgconfig.yml
languageGlobs:
  cpp: ["*.h", "*.hpp"]
```

### 6.6 Python

```yaml
# Function definitions (all)
- id: python-functions
  language: python
  rule:
    kind: function_definition

# Async functions
- id: python-async-functions
  language: python
  rule:
    kind: function_definition
    has:
      kind: async
  # or pattern:
    pattern: async def $NAME($$$ARGS): $$$BODY

# Class definitions
- id: python-classes
  language: python
  rule:
    kind: class_definition

# Decorated functions (e.g. @pytest.fixture)
- id: python-decorated-functions
  language: python
  rule:
    kind: decorated_definition
    has:
      kind: function_definition

# Test functions (name starts with test_)
- id: python-test-functions
  language: python
  rule:
    kind: function_definition
    has:
      field: name
      regex: '^test_'

# Import statements
- id: python-imports
  language: python
  rule:
    any:
      - kind: import_statement
      - kind: import_from_statement
```

### 6.7 JavaScript / TypeScript

```yaml
# Function declarations
- id: js-functions
  language: javascript
  rule:
    any:
      - kind: function_declaration
      - kind: function_expression

# Arrow functions
- id: js-arrow-functions
  language: javascript
  rule:
    kind: arrow_function

# Class declarations
- id: js-classes
  language: javascript
  rule:
    kind: class_declaration

# Method definitions (inside classes)
- id: js-methods
  language: javascript
  rule:
    kind: method_definition

# TypeScript interface declarations
- id: ts-interfaces
  language: typescript
  rule:
    kind: interface_declaration

# TypeScript type aliases
- id: ts-types
  language: typescript
  rule:
    kind: type_alias_declaration

# Export named declarations
- id: js-exports
  language: javascript
  rule:
    kind: export_statement

# React component (arrow function assigned to const)
- id: react-component
  language: typescript
  rule:
    pattern: const $NAME = ($$$PROPS) => { $$$BODY }
    inside:
      kind: export_statement
```

---

## 7. Integration Patterns: Python

### 7.1 Option A: Subprocess (CLI binary)

Best for: projects that can't add Python deps, or need to support all 34 languages.

```python
"""ast-grep subprocess integration for claude-code-project-index."""
import subprocess
import json
import shutil
from pathlib import Path
from typing import Optional


def is_sg_available() -> bool:
    """Check if ast-grep binary is installed."""
    return shutil.which("sg") is not None or shutil.which("ast-grep") is not None


def _sg_binary() -> str:
    """Return the available sg binary name."""
    if shutil.which("sg"):
        return "sg"
    if shutil.which("ast-grep"):
        return "ast-grep"
    raise FileNotFoundError("ast-grep not found. Install: brew install ast-grep")


def run_pattern(
    pattern: str,
    lang: str,
    path: str = ".",
    globs: Optional[list[str]] = None,
    threads: int = 4,
) -> list[dict]:
    """
    Run a single ast-grep pattern against a path.

    Returns list of match dicts with keys:
        text, file, range, metaVariables, language
    """
    sg = _sg_binary()
    cmd = [sg, "run", "-p", pattern, "-l", lang, "--json=stream"]
    if globs:
        for g in globs:
            cmd += ["--globs", g]
    cmd += ["-j", str(threads), path]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if result.returncode not in (0, 1):  # 1 = no matches, still ok
        raise RuntimeError(f"ast-grep error: {result.stderr}")

    matches = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line:
            try:
                matches.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # malformed line, skip
    return matches


def extract_function_signatures(path: str, lang: str) -> list[dict]:
    """
    Extract function/method signatures for a given language.
    Returns list of {name, file, line, signature} dicts.
    """
    # Language-specific patterns
    patterns = {
        "go":         ("func $NAME($$$ARGS) $$$RET { $$$BODY }", "go"),
        "rust":       ("fn $NAME($$$ARGS) $$$RET { $$$BODY }", "rust"),
        "java":       (None, "java"),   # use kind-based approach below
        "ruby":       ("def $NAME($$$ARGS)\n$$$BODY\nend", "ruby"),
        "python":     ("def $NAME($$$ARGS): $$$BODY", "python"),
        "javascript": (None, "javascript"),  # multiple kinds needed
        "typescript": (None, "typescript"),
    }

    if lang == "go":
        matches = run_pattern("func $NAME($$$ARGS) $$$RET { $$$BODY }", "go", path)
    elif lang == "rust":
        matches = run_pattern("fn $NAME($$$ARGS) $$$RET { $$$BODY }", "rust", path)
    elif lang == "python":
        matches = run_pattern("def $NAME($$$ARGS): $$$BODY", "python", path)
    elif lang == "ruby":
        matches = run_pattern("def $NAME($$$ARGS) $$$BODY end", "ruby", path)
    else:
        matches = []

    results = []
    for m in matches:
        name_match = m.get("metaVariables", {}).get("single", {}).get("NAME")
        args_match = m.get("metaVariables", {}).get("multi", {}).get("ARGS", [])
        if name_match:
            args_text = ", ".join(a["text"] for a in args_match) if args_match else ""
            results.append({
                "name": name_match["text"],
                "file": m["file"],
                "line": m["range"]["start"]["line"] + 1,  # convert to 1-based
                "signature": f"{name_match['text']}({args_text})",
                "raw_text": m["text"],
            })
    return results


def scan_with_rules(rules_dir: str, path: str = ".") -> list[dict]:
    """
    Run ast-grep scan with a directory of YAML rule files.
    Returns matches with ruleId and severity.
    """
    sg = _sg_binary()
    cmd = [sg, "scan", "--json=stream", "--rule", rules_dir, path]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    matches = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line:
            try:
                matches.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return matches
```

### 7.2 Option B: Python Native Bindings (`ast-grep-py`)

Best for: tight integration, zero subprocess overhead, programmatic AST traversal.

```bash
pip install ast-grep-py
```

```python
from ast_grep_py import SgRoot
from pathlib import Path


def extract_python_functions(source: str) -> list[dict]:
    """Extract Python function signatures using ast_grep_py."""
    root = SgRoot(source, "python")
    node = root.root()

    results = []
    for match in node.find_all(pattern="def $NAME($$$ARGS): $$$BODY"):
        name_node = match.get_match("NAME")
        args_nodes = match.get_multiple_matches("ARGS")
        r = match.range()

        results.append({
            "name": name_node.text() if name_node else "",
            "args": [a.text() for a in args_nodes] if args_nodes else [],
            "line": r.start.line + 1,   # 1-based
            "column": r.start.column,
            "text": match.text(),
        })
    return results


def extract_rust_items(source: str) -> dict:
    """Extract Rust functions, structs, traits, and impls."""
    root = SgRoot(source, "rust")
    node = root.root()

    return {
        "functions": [
            {
                "name": m.get_match("NAME").text() if m.get_match("NAME") else m.text()[:40],
                "line": m.range().start.line + 1,
            }
            for m in node.find_all(kind="function_item")
        ],
        "structs": [
            {"name": m.field("name").text() if m.field("name") else "", "line": m.range().start.line + 1}
            for m in node.find_all(kind="struct_item")
        ],
        "traits": [
            {"name": m.field("name").text() if m.field("name") else "", "line": m.range().start.line + 1}
            for m in node.find_all(kind="trait_item")
        ],
        "impls": [
            {"text": m.text()[:60], "line": m.range().start.line + 1}
            for m in node.find_all(kind="impl_item")
        ],
    }


def process_file(filepath: Path, language: str) -> dict:
    """Process a single file with ast_grep_py."""
    source = filepath.read_text(encoding="utf-8", errors="replace")
    root = SgRoot(source, language)
    node = root.root()

    # Generic function extraction by kind
    FUNCTION_KINDS = {
        "go": "function_declaration",
        "rust": "function_item",
        "java": "method_declaration",
        "ruby": "method",
        "python": "function_definition",
        "javascript": "function_declaration",
        "typescript": "function_declaration",
        "c": "function_definition",
        "cpp": "function_definition",
    }

    kind = FUNCTION_KINDS.get(language)
    if not kind:
        return {"functions": [], "classes": []}

    functions = []
    for m in node.find_all(kind=kind):
        name_node = m.field("name")
        r = m.range()
        functions.append({
            "name": name_node.text() if name_node else m.text()[:40],
            "line": r.start.line + 1,
        })

    return {"functions": functions}
```

### 7.3 Batch File Processing Pattern

```python
"""Batch process an entire project for the PROJECT_INDEX.json."""
import json
import shutil
import subprocess
from pathlib import Path


# Language -> (ast-grep lang name, function kind, class kind)
LANG_CONFIG = {
    ".go":   ("go",         "function_declaration",  "type_declaration"),
    ".rs":   ("rust",       "function_item",          "struct_item"),
    ".java": ("java",       "method_declaration",     "class_declaration"),
    ".rb":   ("ruby",       "method",                 "class"),
    ".py":   ("python",     "function_definition",    "class_definition"),
    ".js":   ("javascript", "function_declaration",   "class_declaration"),
    ".ts":   ("typescript", "function_declaration",   "class_declaration"),
    ".c":    ("c",          "function_definition",    "struct_specifier"),
    ".cpp":  ("cpp",        "function_definition",    "class_specifier"),
    ".cc":   ("cpp",        "function_definition",    "class_specifier"),
    ".h":    ("c",          "function_definition",    "struct_specifier"),
    ".hpp":  ("cpp",        "function_definition",    "class_specifier"),
}


def index_project_with_sg(root: str) -> dict:
    """
    Generate a language-aware index of a project using ast-grep subprocess.
    Falls back gracefully when sg is not installed.
    """
    if not shutil.which("sg") and not shutil.which("ast-grep"):
        return {}  # graceful degradation

    sg = "sg" if shutil.which("sg") else "ast-grep"
    results = {}

    # Group files by language to minimize subprocess calls
    lang_files: dict[str, list[str]] = {}
    for f in Path(root).rglob("*"):
        if f.is_file() and f.suffix in LANG_CONFIG:
            lang = LANG_CONFIG[f.suffix][0]
            lang_files.setdefault(lang, [])
            lang_files[lang].append(str(f))

    for lang, files in lang_files.items():
        # Run one sg invocation per language across all its files
        # Use --json=stream for memory efficiency
        cmd = [sg, "run", "-l", lang, "--json=stream",
               "-p", f"$NAME($$$ARGS) {{$$$BODY}}",  # generic call-like pattern
               "--"] + files[:500]  # cap per invocation

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            for line in proc.stdout.splitlines():
                if not line.strip():
                    continue
                try:
                    m = json.loads(line)
                    fpath = m.get("file", "")
                    results.setdefault(fpath, {"functions": [], "classes": []})
                    name = (m.get("metaVariables", {})
                              .get("single", {})
                              .get("NAME", {})
                              .get("text", ""))
                    if name:
                        results[fpath]["functions"].append({
                            "name": name,
                            "line": m["range"]["start"]["line"] + 1,
                        })
                except (json.JSONDecodeError, KeyError):
                    pass
        except subprocess.TimeoutExpired:
            pass  # skip this language batch on timeout

    return results


def index_project_with_sg_py(root: str) -> dict:
    """
    Generate index using ast_grep_py native bindings (no subprocess overhead).
    Requires: pip install ast-grep-py
    """
    try:
        from ast_grep_py import SgRoot
    except ImportError:
        return {}  # graceful degradation

    results = {}

    FUNC_KINDS = {
        ".go":   ("go",         "function_declaration"),
        ".rs":   ("rust",       "function_item"),
        ".java": ("java",       "method_declaration"),
        ".rb":   ("ruby",       "method"),
        ".py":   ("python",     "function_definition"),
        ".js":   ("javascript", "function_declaration"),
        ".ts":   ("typescript", "function_declaration"),
        ".c":    ("c",          "function_definition"),
        ".cpp":  ("cpp",        "function_definition"),
    }

    for fpath in Path(root).rglob("*"):
        if not fpath.is_file() or fpath.suffix not in FUNC_KINDS:
            continue
        lang, func_kind = FUNC_KINDS[fpath.suffix]

        try:
            source = fpath.read_text(encoding="utf-8", errors="replace")
            root_node = SgRoot(source, lang).root()
            functions = []
            for m in root_node.find_all(kind=func_kind):
                name_node = m.field("name")
                functions.append({
                    "name": name_node.text() if name_node else "",
                    "line": m.range().start.line + 1,
                })
            results[str(fpath)] = {"functions": functions}
        except Exception:
            pass  # skip unparseable files

    return results
```

### 7.4 Error Handling: When sg Is Not Installed

```python
SG_AVAILABLE: bool | None = None  # cache the check

def check_sg() -> bool:
    global SG_AVAILABLE
    if SG_AVAILABLE is None:
        SG_AVAILABLE = shutil.which("sg") is not None or shutil.which("ast-grep") is not None
    return SG_AVAILABLE


def extract_signatures_with_fallback(content: str, extension: str, filepath: str) -> dict:
    """
    Try ast-grep first, fall back to existing regex parser.
    """
    if check_sg():
        try:
            return extract_via_sg(content, extension, filepath)
        except Exception:
            pass  # fall through to regex
    # Fall back to existing PARSER_REGISTRY regex approach
    return existing_regex_parser(content, extension)
```

---

## 8. Performance Characteristics

### 8.1 Benchmark Data (from ast-grep blog)

Single pattern against TypeScript source (large real-world codebase):
- Wall time: **~0.6 seconds** (parallel, multi-core)
- After 11X optimization: patterns that took 10.8s now take **0.97s**

Key optimizations ast-grep applies internally:
- `potential_kinds` filter: pre-screens files before full parse (40% speedup)
- Avoid regex cloning across threads (50% speedup)
- Eliminate duplicate tree traversal for multi-rule scans

### 8.2 No Offline Index

**Critical limitation for our use case:** ast-grep does NOT maintain an offline index. Every invocation re-parses all files from scratch. This means:

- For a 50k-file repo, every run parses all 50k files
- No cached AST storage between invocations
- Re-parse cost is paid on every `sg run` or `sg scan`

**Mitigation strategies:**
1. Run ast-grep once during index generation, store results in `PROJECT_INDEX.json`
2. Use the stop hook pattern (already in the project): only re-run when files change
3. Use `--json=stream` to pipeline output directly into index builder without buffering

### 8.3 Subprocess Overhead vs Native Bindings

| Approach | Overhead | Languages | Notes |
|----------|---------|-----------|-------|
| `sg` subprocess | One process per invocation, ~50-100ms startup | All 34 languages | Best for batch (pass many files at once) |
| `ast_grep_py` bindings | Near-zero FFI | All 34 languages | Better for per-file in tight loops |
| `py-tree-sitter` | Near-zero FFI | Requires per-language grammar install | More control over AST traversal |

For our use case (indexing during stop hook), **subprocess batching** (all files of one language in one `sg run` call) is the pragmatic choice — it avoids the pip dependency of `ast_grep_py` while keeping invocation count low.

### 8.4 Threading

`-j N` controls parallelism. Default uses all CPU cores. For a 50k-file project:
- Set `-j 4` to `-j 8` for good throughput without CPU starvation
- Stream mode (`--json=stream`) allows pipeline processing while sg still writes output

---

## 9. ast-grep vs py-tree-sitter

| Dimension | ast-grep subprocess | ast_grep_py | py-tree-sitter |
|-----------|-------------------|-------------|----------------|
| **Installation** | Single Rust binary | `pip install ast-grep-py` | `pip install tree-sitter` + per-language grammars |
| **Subprocess overhead** | Yes (~50-100ms per call) | No (PyO3 FFI) | No |
| **Languages** | 34 built-in | 34 built-in | Any with grammar, but must install separately |
| **Pattern syntax** | High-level (`$NAME`, `$$$ARGS`) | Same (via Python API) | None; manual node traversal |
| **AST traversal** | Limited (patterns + kinds) | Full tree traversal | Full tree traversal |
| **Multi-file batch** | Native (`sg run dir/`) | Must loop in Python | Must loop in Python |
| **Parallel processing** | Built-in (`-j N`) | Must use Python threads | Must use Python threads |
| **Type/scope analysis** | Not supported | Not supported | Not supported (need semantic layer) |
| **Debugging** | `--debug-query` flag | `.kind()`, `.children()` | Full node inspection |
| **Maturity** | Stable, production-ready | Stable | Very mature (used by Neovim, etc.) |
| **Best for** | Code search/extraction at scale | Programmatic extraction in Python | Fine-grained AST manipulation |

**Decision guide:**
- Need to support 10+ languages with minimal deps → **ast-grep subprocess** (one binary)
- Need programmatic Python integration, no binary dep → **ast_grep_py**
- Need custom grammar or deep semantic analysis → **py-tree-sitter**
- For `claude-code-project-index` specifically → **ast-grep subprocess** (matches existing pattern of external tool invocation, keeps Python stdlib-only constraint met via optional detection)

---

## 10. YAML Rule Files for Index Generation

Here is a complete `sgconfig.yml` + rule set suitable for the `claude-code-project-index` augmentation layer:

```yaml
# sgconfig.yml (project root)
ruleDirs:
  - .claude-code-project-index/rules
```

```yaml
# rules/extract-go-functions.yml
id: extract-go-functions
language: go
severity: hint
message: "go-function: $NAME"
rule:
  kind: function_declaration
files:
  - "**/*.go"
ignores:
  - "vendor/**"
  - "**/*_test.go"
```

```yaml
# rules/extract-go-structs.yml
id: extract-go-structs
language: go
severity: hint
message: "go-struct: $NAME"
rule:
  kind: type_declaration
  has:
    kind: type_spec
    has:
      kind: struct_type
```

```yaml
# rules/extract-rust-items.yml
id: extract-rust-functions
language: rust
severity: hint
message: "rust-function"
rule:
  kind: function_item
---
id: extract-rust-structs
language: rust
severity: hint
message: "rust-struct"
rule:
  kind: struct_item
---
id: extract-rust-traits
language: rust
severity: hint
message: "rust-trait"
rule:
  kind: trait_item
```

```yaml
# rules/extract-java-items.yml
id: extract-java-classes
language: java
severity: hint
message: "java-class"
rule:
  kind: class_declaration
---
id: extract-java-methods
language: java
severity: hint
message: "java-method"
rule:
  kind: method_declaration
---
id: extract-java-interfaces
language: java
severity: hint
message: "java-interface"
rule:
  kind: interface_declaration
```

---

## 11. Integration Architecture for claude-code-project-index

### Recommended Approach: Optional Augmentation Layer

```
project_index.py
  └── build_index()
        └── parse_file(content, extension)         ← existing PARSER_REGISTRY
              ├── if extension in PARSEABLE_LANGUAGES → regex parser (fast, no deps)
              └── else if sg_available() and extension in SG_LANGUAGES → ast-grep fallback
                    └── extract_via_sg(content, extension, filepath)

scripts/
  ├── project_index.py      (existing)
  ├── index_utils.py        (existing — add sg helpers here)
  └── sg_extractor.py       (NEW — optional ast-grep integration)
```

### `sg_extractor.py` Skeleton

```python
"""
Optional ast-grep augmentation for claude-code-project-index.
Used when sg binary is available and file extension is not natively parsed.
"""
import json
import shutil
import subprocess
from pathlib import Path

# Languages supported by sg but not by our regex parsers
SG_SUPPORTED = {
    ".go":   "go",
    ".rs":   "rust",
    ".java": "java",
    ".rb":   "ruby",
    ".c":    "c",
    ".h":    "c",
    ".cpp":  "cpp",
    ".cc":   "cpp",
    ".hpp":  "cpp",
    ".cs":   "csharp",
    ".kt":   "kotlin",
    ".swift": "swift",
    ".scala": "scala",
    ".lua":  "lua",
    ".ex":   "elixir",
    ".exs":  "elixir",
}

# Function node kind per language
FUNCTION_KIND = {
    "go":         "function_declaration",
    "rust":       "function_item",
    "java":       "method_declaration",
    "ruby":       "method",
    "c":          "function_definition",
    "cpp":        "function_definition",
    "csharp":     "method_declaration",
    "kotlin":     "function_declaration",
    "swift":      "function_declaration",
    "scala":      "function_definition",
    "lua":        "function_definition",
    "elixir":     "def",
}

CLASS_KIND = {
    "go":         "type_declaration",
    "rust":       "struct_item",
    "java":       "class_declaration",
    "ruby":       "class",
    "cpp":        "class_specifier",
    "csharp":     "class_declaration",
    "kotlin":     "class_declaration",
    "swift":      "class_declaration",
    "scala":      "class_definition",
}


def sg_available() -> bool:
    return shutil.which("sg") is not None or shutil.which("ast-grep") is not None


def _sg() -> str:
    return "sg" if shutil.which("sg") else "ast-grep"


def extract_sg_signatures(filepath: str, extension: str) -> dict:
    """
    Extract function and class signatures via ast-grep subprocess.
    Returns dict compatible with existing PARSER_REGISTRY output format.
    """
    lang = SG_SUPPORTED.get(extension)
    if not lang or not sg_available():
        return {"functions": [], "classes": {}}

    func_kind = FUNCTION_KIND.get(lang)
    class_kind = CLASS_KIND.get(lang)

    functions = []
    classes = {}

    # Extract functions by kind
    if func_kind:
        try:
            out = subprocess.run(
                [_sg(), "run", "-l", lang, "--kind", func_kind,
                 "--json=stream", filepath],
                capture_output=True, text=True, timeout=30
            )
            for line in out.stdout.splitlines():
                if not line.strip():
                    continue
                try:
                    m = json.loads(line)
                    name_node = m.get("metaVariables", {}).get("single", {}).get("NAME")
                    # Fallback: use text snippet as name
                    name = name_node["text"] if name_node else m["text"].split("(")[0].split()[-1]
                    functions.append(
                        f"{name}:{m['range']['start']['line'] + 1}"
                    )
                except (json.JSONDecodeError, KeyError, IndexError):
                    pass
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    return {
        "functions": functions,
        "classes": classes,
    }
```

**Note on `--kind` flag:** The `sg run` command accepts `--kind KIND` as a shorthand for `rule: {kind: KIND}`. Check if this flag is available in your sg version; if not, use `-p` with a minimal pattern or a temporary YAML rule file.

---

## 12. Known Limitations and Gotchas

1. **No offline index:** Every run re-parses from scratch. Store results immediately in PROJECT_INDEX.json.

2. **Go function call ambiguity:** `fmt.Println($A)` fails as a bare pattern. Always wrap in context: `func t() { fmt.Println($A) }` with `selector: call_expression`.

3. **$$$ARGS constraints:** You cannot add `constraints:` to multi-node metavariables. Apply constraints to `$SINGLE` vars only.

4. **Cross-language rules not supported:** Cannot write one rule for both TypeScript and JavaScript. Write separate rules per language.

5. **Constraints don't work inside `not:`:** Known limitation — constraints are filtered post-match and don't apply inside negation.

6. **Rule ordering matters:** In `all:` rules, the first rule determines what `$META_VAR` matches; later rules only filter against that captured content.

7. **Pattern must be valid code:** Fragments like `"key": $VAL` (partial JSON) fail. Use `context`/`selector` to wrap in valid syntax.

8. **`kind` and `pattern` are independent:** You cannot combine `kind: function_item` with `pattern: ...` to get "match this pattern but only on function_item nodes." Use the pattern object with `context`/`selector` instead.

9. **returncode 1 = no matches (not an error):** Handle this in subprocess calls; both 0 and 1 are success.

10. **Field names are language-specific:** `m.field("name")` works for Go (`function_declaration`'s `name` field) but may not exist for all languages. Always guard with `if name_node is not None`.

---

## 13. Sources

- [ast-grep official site](https://ast-grep.github.io/)
- [Pattern Syntax Guide](https://ast-grep.github.io/guide/pattern-syntax.html)
- [JSON Mode / Output Format](https://ast-grep.github.io/guide/tools/json.html)
- [YAML Configuration Reference](https://ast-grep.github.io/reference/yaml.html)
- [Rule Object Reference](https://ast-grep.github.io/reference/rule.html)
- [Rule Essentials Guide](https://ast-grep.github.io/guide/rule-config.html)
- [sg run CLI Reference](https://ast-grep.github.io/reference/cli/run.html)
- [Supported Languages](https://ast-grep.github.io/reference/languages.html)
- [Python API Guide](https://ast-grep.github.io/guide/api-usage/py-api.html)
- [Performance Tips (napi)](https://ast-grep.github.io/guide/api-usage/performance-tip.html)
- [Deep Dive: Pattern Syntax](https://ast-grep.github.io/advanced/pattern-parse.html)
- [Deep Dive: Core Concepts](https://ast-grep.github.io/advanced/core-concepts.html)
- [Optimize ast-grep to 10X Faster](https://ast-grep.github.io/blog/optimize-ast-grep.html)
- [Tool Comparison (vs semgrep, GritQL, Comby)](https://ast-grep.github.io/advanced/tool-comparison.html)
- [FAQ](https://ast-grep.github.io/advanced/faq.html)
- [Go Catalog](https://ast-grep.github.io/catalog/go/)
- [Rust Catalog](https://ast-grep.github.io/catalog/rust/)
- [Java Catalog](https://ast-grep.github.io/catalog/java/)
- [Ruby Catalog](https://ast-grep.github.io/catalog/ruby/)
- [C Catalog](https://ast-grep.github.io/catalog/c/)
- [Python Catalog](https://ast-grep.github.io/catalog/python/)
- [ast-grep-py on PyPI](https://pypi.org/project/ast-grep-py/)
- [GitHub: ast-grep/ast-grep](https://github.com/ast-grep/ast-grep)
- [DeepWiki: Python Integration](https://deepwiki.com/ast-grep/ast-grep/8-python-integration)
