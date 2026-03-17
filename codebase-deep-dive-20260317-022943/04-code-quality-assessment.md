# Code Quality Assessment

**Overall Grade: C+**

The codebase achieves its functional goal competently and shows thoughtful architectural intent (shared utilities module, progressive compression, hook integration). However, it carries significant technical debt: massive functions, pervasive bare excepts, duplicated logic, complete absence of tests, and one deeply problematic god function. The grade would be B- with tests.

## Metrics Summary

| Metric | Value |
|--------|-------|
| Lines of Code | ~4,184 |
| Files | 12 source files (4 Python, 2 Shell, 1 agent MD) |
| Test Coverage | **0%** — no test suite exists |
| Documentation | Adequate — docstrings present, but schema undocumented |
| Bare `except:` clauses | **14** across 4 files |
| Functions > 50 lines | **7** (worst: 381 lines) |
| Dead code | 2 confirmed instances |
| Code duplication | 3 critical DRY violations |

## High-Complexity Functions

| Function | File:Line | Lines | Complexity | Assessment |
|----------|-----------|-------|------------|------------|
| `extract_python_signatures` | index_utils.py:161 | ~381 | Very High | Largest function; imperative parse-as-you-go with fragile index juggling |
| `extract_javascript_signatures` | index_utils.py:545 | ~358 | Very High | 3 near-identical brace-counting blocks |
| `copy_to_clipboard` | i_flag_hook.py:259 | ~305 | Very High (~25-30 cyclomatic) | God function: 5 transport strategies, hardcoded IPs, untestable |
| `build_index` | project_index.py:109 | ~289 | High | File discovery + parsing + dep graph + call graph in one |
| `extract_shell_signatures` | index_utils.py:928 | ~256 | High | 100 lines of verbatim duplication |
| `main` (i_flag_hook) | i_flag_hook.py:566 | ~211 | High | Huge if/elif chain on copy_result |
| `compress_if_needed` | project_index.py:529 | ~128 | Moderate | 5 steps wanting a loop pattern |

## SOLID Principles

- **Single Responsibility: FAILED** — `i_flag_hook.py` performs 5 distinct jobs (hook I/O, flag parsing, root discovery, generation orchestration, multi-platform clipboard). `copy_to_clipboard` alone spans 6 clipboard protocols.
- **Open/Closed: PARTIAL** — Adding a new language parser requires modifying an `if/elif` chain in `build_index` (project_index.py:224-229) rather than registering a handler. `PARSEABLE_LANGUAGES` dict is the right idea but dispatch is hardcoded.
- **Liskov Substitution: N/A** — No class hierarchies.
- **Interface Segregation: N/A** — No interfaces.
- **Dependency Inversion: VIOLATED** — `stop_hook.py` hardcodes Python version-pinned fallback strings. No dependency injection for clipboard mechanisms.

## Code Duplication (DRY Violations)

### Critical: Dead `build_call_graph` + inline duplicate
- `index_utils.build_call_graph` (lines 132-158) — **never called anywhere**
- `project_index.build_index` (lines 321-392) — re-implements the same logic with file-qualified names
- Risk: A developer fixing a bug in one won't know to fix the other

### Critical: Shell function body parsing
- `extract_shell_signatures` lines 983-1057 (style 1) and 1059-1133 (style 2) contain ~100 lines of verbatim identical code for parameter extraction and body extraction

### High: Python discovery logic
- `stop_hook.py:44-58` — reads `.python_cmd`, falls back to iterating version-pinned candidates
- `i_flag_hook.py:189-193` — reads `.python_cmd`, falls back to `sys.executable`
- Different fallback strategies for the same purpose

### High: Project root discovery
- `i_flag_hook.py:23-43` — checks `.git` + project markers
- `stop_hook.py:17-26` — checks only `PROJECT_INDEX.json`
- Neither uses a shared utility from `index_utils.py`

### Moderate: Value-type inference triplicated
- `extract_python_signatures` (lines ~262-270, ~365-373)
- `extract_javascript_signatures` (lines ~662-670, ~807-814)
- `extract_shell_signatures` (lines ~1142-1148)
- Should be a single `_classify_value_type(value: str) -> str` helper

## Dead Code

| Item | Location | Evidence |
|------|----------|----------|
| `build_call_graph()` | index_utils.py:132-158 | Never imported or called; grep confirms zero call sites |
| `call_graph` key in extractors | index_utils.py:171, 556, 935 | Initialized as `{}` but never populated; call graph built separately in project_index.py |
| Variables `in_function`, `current_function`, `function_start_line` | index_utils.py:972-974 | Assigned but never read |
| `MAX_ITERATIONS` guard in `compress_if_needed` | project_index.py:541 | Only 5 sequential steps; guard can never fire |

## Bare `except:` Clauses (14 total)

**Highest-risk:**

| Location | Impact |
|----------|--------|
| `i_flag_hook.py:60` | Swallows corrupt index JSON silently |
| `i_flag_hook.py:133` | Produces silently incomplete file hash |
| `i_flag_hook.py:291` | Network timeouts, import errors, attribute errors all treated as "not available" |
| `index_utils.py:1190` | Masks permission errors and encoding failures in markdown reading |
| `index_utils.py:1295` | Silently produces empty gitignore patterns — files that should be ignored may be indexed |
| `project_index.py:91` | Catches everything including KeyboardInterrupt on directory counting |

All should be replaced with `except Exception as e:` at minimum.

## Naming Conventions

**Good:** `should_index_file`, `infer_file_purpose`, `IGNORE_DIRS`, `PARSEABLE_LANGUAGES` — consistent verb-noun form, proper screaming snake for constants.

**Problems:**
- `dense['f']`, `dense['g']`, `dense['d']` — single-letter keys with no named constants in construction code
- Path abbreviation rules (`scripts/` -> `s/`) are magic strings at project_index.py:432
- Variable `j` reused in two scopes within `extract_python_signatures`

## Documentation Quality

**Good:**
- Module-level docstrings on all files
- Consistent one-line docstrings on all public functions in `index_utils.py`
- `compress_if_needed` step comments are accurate

**Problems:**
- `copy_to_clipboard` docstring: "Copy prompt, instructions, and index to clipboard for external AI" — completely understates 300 lines of multi-platform clipboard handling
- Dense format schema (`f`, `g`, `d` keys) undocumented anywhere in code
- `generate_index_at_size` has undocumented side effect of rewriting the index file with metadata

## Strengths

- Pipeline pattern in `project_index.py::main()` is clean and well-structured
- `index_utils.py` is a well-organized utility library with consistent function signatures
- Progressive compression in `compress_if_needed` is a thoughtful degradation strategy
- Hook integration is properly thin — hooks delegate, don't re-implement

## Prioritized Improvement Areas

1. **Replace 14 bare `except:` clauses** — Highest reliability impact
2. **Delete dead `build_call_graph`** or consolidate with live inline version — Prevent correctness traps
3. **Add a test suite** — Even 20 focused parser tests would catch invisible bugs
4. **Extract shell duplication** — `_parse_shell_function_body` helper saves 100 lines
5. **Decompose `copy_to_clipboard`** — Split into `_try_vm_bridge`, `_try_osc52`, `_try_xclip`, `_try_pyperclip`, `_save_file_fallback`
6. **Document dense format schema** — TypedDict or at minimum a docstring on `convert_to_enhanced_dense_format`
