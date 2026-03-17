# Code Quality Assessment

**Overall Grade: B**

## Metrics Summary

| Metric | Value |
|--------|-------|
| Total LOC | ~4,319 |
| Code Files | 19 |
| Test Files | 11 |
| Max Function Length | 381 lines (`extract_python_signatures`) |
| Max Cyclomatic Complexity | ~35-40 (`extract_python_signatures`) |
| DRY Violations | 3 (critical: `_validate_python_cmd`, moderate: brace-counting, hash calc) |
| Dead Code | 3 instances (MAX_ITERATIONS guard, ssh_file_large branch, __pycache__ duplicate) |

## High-Complexity Functions

| Function | File:Lines | Complexity | Lines |
|----------|-----------|-----------|-------|
| `extract_python_signatures` | index_utils.py:133-513 | ~35-40 | 381 |
| `extract_javascript_signatures` | index_utils.py:516-873 | ~25-30 | 358 |
| `build_index` | project_index.py:129-411 | ~15-20 | 283 |
| `compress_if_needed` | project_index.py:539-667 | ~10 | 129 |
| `convert_to_enhanced_dense_format` | project_index.py:415-536 | ~10 | 121 |
| `extract_shell_signatures` | index_utils.py:969-1079 | ~10 | 110 |
| `generate_index_at_size` | i_flag_hook.py:204-309 | ~8 | 106 |

## DRY Violations

### Critical: `_validate_python_cmd` (verbatim duplication)
- `i_flag_hook.py:31-51` and `stop_hook.py:13-33` — byte-for-byte identical
- Security function — drift risk if only one copy is updated
- Fix: Move to `index_utils.py`

### Moderate: Brace-counting pattern (5 instances in JS parser)
- `index_utils.py` lines 570, 609, 658, 742, 828
- Extract `_find_matching_brace(content, start, initial_count)` helper

### Moderate: Hash calculation duplicated
- `i_flag_hook.py:calculate_files_hash()` and `stop_hook.py:should_regenerate()` inline
- Same algorithm, different function names

## SOLID Principles

| Principle | Adherence | Notes |
|-----------|-----------|-------|
| Single Responsibility | Partial | `extract_python_signatures` has 8 responsibilities; `generate_index_at_size` mixes subprocess + metadata |
| Open/Closed | Good | PARSER_REGISTRY and CLIPBOARD_TRANSPORTS are properly extensible |
| Liskov Substitution | N/A | No class hierarchies |
| Interface Segregation | N/A | Procedural code |
| Dependency Inversion | Good | `index_utils.py` as shared library module |

## Test Coverage Assessment

**Grade: B+**

### Well Covered
- Parser characterization (Python, JS, Shell)
- Compression happy path + idempotency
- Clipboard transports (file fallback, permissions)
- Flag parsing (4 cases)
- Security regressions (hardcoded IPs, validation)
- Registry structure and dispatch

### Critical Gaps
1. `build_index` — zero end-to-end test coverage
2. `generate_index_at_size` — entirely untested
3. `should_regenerate_index` — no tests
4. `find_project_root` — no edge case tests
5. SSH clipboard branch — untested
6. `compress_if_needed` — doesn't verify output fits target size

## Dead Code

1. **`MAX_ITERATIONS = 10` guard** (project_index.py:551) — 5 steps, counter maxes at 5, guard at 10 never triggers
2. **`ssh_file_large` branch** (i_flag_hook.py:501-508) — no transport returns this type
3. **Duplicate `__pycache__`** in IGNORE_DIRS set (index_utils.py:16) — silently discarded

## Naming & Style

- Constants: `SCREAMING_SNAKE_CASE` — consistent
- Functions: `snake_case` — consistent
- Private: `_leading_underscore` — consistent
- Minor: `any` used instead of `Any` in type hints (index_utils.py:516, 898)

## Prioritized Recommendations

### P0 (Must Fix)
1. Move `_validate_python_cmd` to `index_utils.py`
2. Fix `any` → `Any` in type annotations
3. Add integration test for `build_index` with tmp_path
4. Fix compress test to verify output fits target

### P1 (Should Fix)
5. Remove `ssh_file_large` dead branch
6. Remove/restructure `MAX_ITERATIONS` dead guard
7. Remove duplicate `__pycache__` in IGNORE_DIRS
8. Extract brace-counting helper in JS parser
9. Add tests for `generate_index_at_size` and `should_regenerate_index`

### P2 (Nice to Have)
10. Extract `_classify_const_value()` helper
11. Consolidate `sys.path.insert` via pytest.ini
12. Add return-dict schema docstring to `parse_file()`
