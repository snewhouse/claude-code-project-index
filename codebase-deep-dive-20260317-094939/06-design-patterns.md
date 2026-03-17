# Design Patterns & Maintainability

**Maintainability Score:** 7/10
**Extensibility Score:** 8/10

## Design Patterns Detected

### 1. Registry Pattern — `PARSER_REGISTRY` (index_utils.py:1175-1200)

Well-implemented data-driven dispatch. Module-level dict maps extensions to parser functions, populated by `register_parsers()` at load time. Dispatch via `parse_file()` is 3 lines.

**Adding a language:** Write parser function + add to `PARSER_REGISTRY` + add to `PARSEABLE_LANGUAGES`. Zero changes to `project_index.py` or hooks.

### 2. Strategy Pattern — Clipboard Transports (i_flag_hook.py:455-477)

```python
CLIPBOARD_TRANSPORTS = [_try_xclip, _try_pyperclip]
SSH_TRANSPORTS = [_try_osc52, _try_tmux_buffer]
```

Each transport: `(content: str) → Optional[Tuple[str, data]]`. Dispatcher iterates until one succeeds, falls back to `_try_file_fallback`.

**Adding a transport:** Write one function, insert into list. Dispatcher unchanged.

### 3. Pipeline Pattern — Build → Convert → Compress → Write (project_index.py:718-796)

Linear data pipeline where each stage transforms a dict:
- `build_index()` → raw dict (full, verbose)
- `convert_to_enhanced_dense_format()` → compressed keys
- `compress_if_needed()` → size-constrained
- Atomic write → `PROJECT_INDEX.json`

Each stage independently testable. Clean input/output contracts.

### 4. Template Method — Uniform Parser Signatures (index_utils.py)

All parsers follow identical structure: init result dict → first pass (collect names) → main parse → post-process → return. Template is implicit (convention, not ABC).

### 5. Content-Addressed Caching (i_flag_hook.py:172-202)

`_meta.files_hash` = sha256(git_files + mtimes)[:16]. Compared before regeneration. 2k-token tolerance for size changes.

## Anti-Patterns Detected

### 1. Code Duplication (3 instances)

| Duplicated Code | Location 1 | Location 2 | Risk |
|----------------|-----------|-----------|------|
| `_validate_python_cmd()` | i_flag_hook.py:31-51 | stop_hook.py:13-33 | Medium (security function) |
| Atomic write block | project_index.py:752-768 | i_flag_hook.py:274-293 | Low |
| Hash calculation | i_flag_hook.py:135 | stop_hook.py:44-59 | Low |

Fix: Move all three to `index_utils.py`.

### 2. God Functions

| Function | File | Lines | Concerns Mixed |
|----------|------|-------|----------------|
| `extract_python_signatures` | index_utils.py:133-513 | **381** | imports, classes, functions, decorators, docstrings, calls |
| `extract_javascript_signatures` | index_utils.py:516-873 | **358** | imports, interfaces, enums, classes, functions, types |
| `build_index` | project_index.py:129-411 | **283** | tree gen, file discovery, parsing, call graph, dep graph |

### 3. Dead Code

- `MAX_ITERATIONS = 10` guard (project_index.py:551) — only 5 steps exist, counter never exceeds 5
- `ssh_file_large` transport type branch in `_build_hook_output` — no transport returns this type

### 4. Dual-Writer on PROJECT_INDEX.json

`project_index.py` writes minified JSON, then `i_flag_hook.py` rewrites as pretty-printed with enriched `_meta`. Brief window of incomplete metadata.

## Extensibility Assessment

| Extension Point | Effort | Changes Required |
|----------------|--------|-----------------|
| New language parser | Low (30-60 min) | 1 function + 2 dict entries in index_utils.py |
| New clipboard transport | Very Low (15-30 min) | 1 function + 1 list insertion in i_flag_hook.py |
| New index data section | Medium (1-3 hrs) | build_index + dense_format + compress_if_needed in project_index.py |
| New compression step | Low (30 min) | Add step in compress_if_needed |

## Maintainability Scores

| Factor | Score | Notes |
|--------|-------|-------|
| Readability | 7/10 | Good naming and constants; parsers too long to read end-to-end |
| Testability | 7/10 | Parsers pure-functional; hooks require integration tests |
| Modifiability | 7/10 | Registry/strategy patterns clean; 3 duplication points raise risk |

## Refactoring Opportunities

1. **Extract shared utilities** — move `_validate_python_cmd`, `calculate_files_hash`, `atomic_write` to `index_utils.py`
2. **Decompose god functions** — extract `_parse_imports`, `_parse_classes`, `_parse_functions` from 380-line parsers
3. **Convert compression steps to a list** — make steps enumerable, eliminate dead MAX_ITERATIONS guard
4. **Add type alias** for clipboard transport contract — `ClipboardResult = Optional[Tuple[str, Any]]`
5. **Document parser output contract** — add expected-keys docstring to `parse_file()`
