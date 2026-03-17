# Cross-File Call Graph Resolution Research

**Date:** 2026-03-17
**Context:** Improving claude-code-project-index with cross-file relationship tracking

---

## Current State

The current indexer tracks intra-file call graphs only. "Function A in file X calls function B in file Y" is invisible. Cross-file resolution would enable blast_radius, who_calls, and dead_code queries.

---

## Tool Comparison

### PyCG (Archived Nov 2023)

- **ICSE 2021 paper:** 99.2% precision, 69.9% recall
- Fixed-point iteration over ASTs
- Output: JSON adjacency list with fully-qualified dotted names
- Import resolution requires --package flag
- **Status:** Archived, do not use for new projects
- **Key technique:** Module map + AST-based call site extraction

### Pyan3 (Active, v2.2.0, Mar 2026)

- Single-pass AST visitor with "defines" and "uses" edges
- Scope-aware name binding table
- Supports Python 3.10-3.14
- Outputs DOT/SVG/plain-text
- No formal precision/recall evaluation
- **Actively maintained**

### Griffe (v2.0.0, Feb 2026)

- API extractor with Alias class for cross-module indirection
- Handles __all__, re-exports, alias chains
- Not a call graph tool, but alias resolution model is applicable
- Production-grade (powers mkdocstrings)

### Jedi (v0.19.2, Nov 2024)

- Per-call-site resolver: script.goto(line, col, follow_imports=True)
- Returns file and line of definition
- Best as resolution backend on top of your own AST extraction
- Heavy overhead for batch use

---

## Import Resolution Algorithm (Pure stdlib, Zero Dependencies)

### 5-Step Pipeline

**Step 1: Build Module Map from File Tree**
```
{dotted.name -> relative/file/path.py}

Example:
  "scripts.project_index" -> "scripts/project_index.py"
  "scripts.index_utils"   -> "scripts/index_utils.py"
  "tests.conftest"         -> "tests/conftest.py"
```

**Step 2: Resolve Absolute Imports**
```
import foo.bar -> module_map.get("foo.bar") -> "foo/bar.py"
from foo.bar import X -> module_map.get("foo.bar") -> "foo/bar.py", symbol="X"
```

**Step 3: Resolve Relative Imports**
```
from .utils import X
  -> current_package = "scripts"
  -> level = 1
  -> resolved = "scripts.utils" -> "scripts/utils.py"

from ..core import Y
  -> current_package = "scripts.parsers"
  -> level = 2
  -> resolved = "core" -> "core.py" or "core/__init__.py"
```

**Step 4: Follow __init__.py Re-export Chains (2-pass)**
```
Pass 1: Collect all __init__.py imports
Pass 2: Resolve chains: foo/__init__.py imports from foo.bar
         -> re-export chain: foo.X -> foo.bar.X
```

**Step 5: Handle __all__ for Star Imports**
```
from foo import *
  -> check foo/__init__.py for __all__
  -> if defined: only import listed names
  -> if not defined: import all non-underscore names (conservative)
```

### Unresolvable Patterns (Flag, Don't Guess)
- Dynamic imports: importlib.import_module(variable)
- Runtime sys.path manipulation
- Conditional imports inside if/try blocks
- Monkey patching

---

## Symbol Table Design

### Structure
```python
SymbolTable = Dict[str, SymbolEntry]

SymbolEntry = {
    "file": str,         # relative file path
    "line": int,         # definition line
    "kind": str,         # "function" | "class" | "constant" | "module"
    "canonical": str,    # fully qualified name
}
```

### 3-Phase Build
1. **Discover modules** from git file list
2. **Extract symbols per file** using ast.NodeVisitor
3. **Resolve aliases** following re-export chains (MAX_DEPTH=10 guard against cycles)

---

## Graph Data Structures

### Storage Format (in PROJECT_INDEX.json)

New `xg` key for cross-file edges:
```json
"xg": [
  {
    "source_file": "s/project_index.py",
    "source_symbol": "build_index",
    "target_file": "s/index_utils.py",
    "target_symbol": "extract_python_signatures",
    "edge_type": "call"
  }
]
```

Edge types: call, import, inherit, implement, reference

### Query Patterns

| Query | Algorithm | Use Case |
|-------|-----------|----------|
| who_calls(symbol) | Reverse BFS on xg edges | "What depends on this?" |
| blast_radius(symbol) | Forward+reverse transitive closure | "What breaks if I change this?" |
| dead_code() | Reachability from entry points | "What's never called?" |
| dependency_chain(file) | Import graph traversal via deps | "What does this file need?" |

---

## Recommendations for claude-code-project-index

### Phase 1: build_import_map() in index_utils.py
- Pure stdlib, zero dependencies
- Build {dotted.name -> file_path} from git file list
- ~50-80 lines of code

### Phase 2: resolve_cross_file_edges()
- Use import map + per-file AST call sites
- Connect intra-file calls through resolved imports
- Add xg key to PROJECT_INDEX.json
- ~100-150 lines of code

### Phase 3: Optional Jedi Integration
- For higher recall on complex resolution cases
- Optional dependency with graceful fallback

### Design Philosophy (from PyCG)
- **Prefer precision over recall**
- Emit no edge when resolution is ambiguous
- False negatives are acceptable; false positives are dangerous
- Mark unresolvable patterns explicitly

### Schema Extensions (Backward Compatible)
| Key | Type | Content |
|-----|------|---------|
| xg | list | Cross-file graph edges |
| sym | dict | Symbol table (dotted.name -> file:line:kind) |
| resolved_deps | dict | Import -> file path mapping |

All new keys are additive. V1 consumers ignore them.
