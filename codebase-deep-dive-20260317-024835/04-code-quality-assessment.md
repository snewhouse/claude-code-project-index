# Code Quality Assessment

**Overall Grade: C+**

The codebase is functional and solves a real problem, but carries significant technical debt in exception handling, code duplication, coupling, and test coverage.

## Metrics Summary

| Metric | Value |
|--------|-------|
| Cyclomatic Complexity (avg) | ~15 (max: ~35-40 in `extract_python_signatures`) |
| Code Duplication | ~200 lines duplicated across 4 areas |
| Test Coverage | **0%** |
| Documentation | Adequate (module docstrings present, inline comments inconsistent) |
| Bare `except:` blocks | **12** |
| Functions > 50 lines | **8** |
| Dead code instances | **4** |

## High-Complexity Functions

| Function | File | Lines | Est. Complexity |
|----------|------|-------|-----------------|
| `extract_python_signatures` | `index_utils.py:161` | 381 | 35-40 |
| `copy_to_clipboard` | `i_flag_hook.py:259` | 305 | 25-30 |
| `build_index` | `project_index.py:109` | 289 | 20-25 |
| `extract_javascript_signatures` | `index_utils.py:545` | ~355 | 20-25 |
| `extract_shell_signatures` | `index_utils.py:928` | ~255 | 15-20 |
| `compress_if_needed` | `project_index.py:529` | 128 | 15 |
| `main` | `i_flag_hook.py:566` | 213 | 12-15 |
| `convert_to_enhanced_dense_format` | `project_index.py:404` | 122 | 10 |

## Code Duplication (DRY Violations)

1. **Shell function body extraction** — `index_utils.py:993-1057` and `1062-1133` (~130 lines duplicated). Two shell parsing branches are near-identical clones differing only in detection regex.

2. **Call graph construction** — `project_index.py:321-393` (~65 lines) reimplements `build_call_graph()` already defined at `index_utils.py:132-158`. The `index_utils` version is never called.

3. **hookSpecificOutput blocks** — `i_flag_hook.py:600-737` — Five nearly identical output dictionaries with ~60 lines of repeated boilerplate.

4. **`find_project_root` logic** — `i_flag_hook.py:23-43` and `stop_hook.py:21-25` implement different variants with no shared code.

## SOLID Principles

| Principle | Status | Evidence |
|-----------|--------|----------|
| **Single Responsibility** | VIOLATED | `copy_to_clipboard` does 7 jobs; `build_index` does 5 |
| **Open/Closed** | PARTIAL | Adding language/transport requires editing hardcoded if/elif chains |
| **Liskov Substitution** | N/A | No class hierarchy |
| **Interface Segregation** | N/A | No interfaces/ABCs |
| **Dependency Inversion** | VIOLATED | Direct imports, no injection; subprocess untestable without mocking |

## Exception Handling

**Bare `except:` count: 12** (catches `KeyboardInterrupt`, `SystemExit`)

| File | Count |
|------|-------|
| `i_flag_hook.py` | 9 |
| `index_utils.py` | 2 |
| `project_index.py` | 1 |

All should be replaced with `except Exception:` at minimum.

## Dead Code

1. `build_call_graph()` in `index_utils.py:132-158` — defined, exported, never called
2. `call_graph: {}` key initialized in all 3 parser return dicts — never populated
3. `MAX_ITERATIONS` guard in `compress_if_needed` — unreachable with 5 sequential steps
4. `in_function`, `current_function`, `function_start_line` in shell parser — initialized, never read

## Test Coverage: 0%

No test files exist anywhere. Critical untested areas:
- Multi-line Python signatures with colons in default values
- Compression docstring parsing by `:` split (corrupts signatures with colons)
- File hash edge cases (new file same mtime, moved file)

## Naming Conventions

**Good:** Constants `SCREAMING_SNAKE_CASE`, functions `snake_case`, booleans `is_`/`should_` prefixed.

**Problematic:**
- Dense format single-letter keys (`f`, `g`, `d`) — no constant mapping in code
- `json`/`javascript` language letter collision (both map to `j`)
- Stale comments: `"These functions are now imported from index_utils"` — orphaned refactoring artifacts

## Prioritized Improvements

1. **Add test suite** — parsers, compression, flag parsing (highest risk)
2. **Replace 12 bare `except:`** with typed exceptions
3. **Split `copy_to_clipboard`** into strategy functions
4. **Deduplicate shell parser** — extract shared helper
5. **Remove dead code** — `build_call_graph`, vestigial keys, unreachable guards
6. **Define dense format constants** — replace bare string literals
7. **Remove hardcoded environment** — author's IPs, paths, username
