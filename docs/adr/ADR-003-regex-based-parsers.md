# ADR-003: Regex-Based Language Parsers

**Status:** Accepted (with documented limitations)
**Date:** 2026-03-17
**Context:** How to extract function signatures, classes, and call graphs from source code

## Decision

Use regex-based parsers for Python, JavaScript/TypeScript, and Shell. All other languages are file-tracked but not parsed. Parser dispatch uses `PARSER_REGISTRY` dict.

## Rationale

- Zero external dependencies (ADR-002)
- Covers the three most common languages in Claude Code users' projects
- `PARSER_REGISTRY` (dict mapping extension to parser function) enables adding languages without modifying dispatch logic

## Implementation

Three parsers in `scripts/index_utils.py`:

| Parser | Function | Two-Pass | Call Detection |
|--------|----------|----------|---------------|
| Python | `extract_python_signatures()` | Yes (collect names → extract with calls) | `extract_function_calls_python()` via `\b(\w+)\s*\(` regex |
| JS/TS | `extract_javascript_signatures()` | Yes | `extract_function_calls_javascript()` same pattern |
| Shell | `extract_shell_signatures()` | Yes | `extract_function_calls_shell()` same pattern |

Shell parser uses `_parse_shell_function()` shared helper (line 898) for both `name() {}` and `function name {}` styles.

Registry dispatch (`parse_file()`, line 1192):
```python
parser = PARSER_REGISTRY.get(extension)
if parser is None:
    return None
return parser(content)
```

## Known Limitations

1. **Python multi-line signatures**: The `\).*:` terminator fails when default values contain `:` (e.g., `def f(x: dict = {'a': 1}):`)
2. **JS template literals**: Brace counting corrupted by `${...}` expressions containing object literals
3. **JS nested generics**: `[^>]+` pattern can't match inner `>` in `Map<K, V>`
4. **Call graph is intra-file only**: `all_functions` set is built per-file, so cross-file calls are invisible
5. **Shell brace detection**: When `{` is on the same line as function definition, the body scanner may miss parameters

## Future Direction

Python `ast` module (stdlib) would provide 100% accuracy for Python files. Documented in `codebase-deep-dive-20260317-024835/09-code-intelligence-research.md`.

## Verified Against

- `scripts/index_utils.py:1174-1191` — PARSER_REGISTRY definition
- `scripts/index_utils.py:1192-1201` — parse_file() dispatch
- `scripts/index_utils.py:1346` — register_parsers() called at module load
- `scripts/index_utils.py:898` — _parse_shell_function() shared helper
