# Design Patterns & Maintainability

**Maintainability Score: 4/10**
**Extensibility Score: 4/10**

## Design Patterns Detected

### Appropriate Use

#### Pipeline Pattern — `project_index.py::main()`
Clean 4-stage linear pipeline: `build_index()` → `convert_to_enhanced_dense_format()` → `compress_if_needed()` → `write`. Stages are decoupled and individually testable. Best pattern application in the codebase.

#### Observer/Hook Pattern — Claude Code Integration
`i_flag_hook.py` (UserPromptSubmit) and `stop_hook.py` (Stop) correctly implement event-driven hooks. Clean JSON stdin/stdout contracts keep hooks thin for orchestration.

#### Cache-Aside Pattern — `should_regenerate_index()`
`_meta.files_hash` (SHA-256 of paths + mtimes, first 16 chars) enables smart cache invalidation. Only regenerates on actual file changes or size delta > 2k tokens.

#### Two-Pass Parsing — All Language Parsers
All three parsers correctly use Pass 1 (collect function names) + Pass 2 (extract with call detection). Standard forward-reference resolution approach.

#### Composite Compression — `compress_if_needed()`
5-step progressive degradation: tree → docstrings → docs → files. Each step checks size and returns early. Correct Chain of Responsibility application.

### Questionable Use

#### Strategy Pattern (Degraded) — `copy_to_clipboard()`
The pattern intent is present (5+ transport strategies in priority order), but collapsed into a 305-line monolith with nested try/except instead of proper callables with a common interface. Not independently testable.

#### Template Method (Informal) — Language Parsers
Three parsers follow the same two-pass convention by copy, not by contract. No base class or ABC enforces the pattern. A future parser author could miss Pass 1 (name collection), breaking call detection.

## Anti-Patterns Detected

### God Function: `copy_to_clipboard` (305 lines)
`i_flag_hook.py:259-564`. Handles: VM Bridge (network/tunnel), OSC 52, tmux buffer, xclip, pyperclip, file fallback — all with environment detection, content formatting, error handling, and user messaging. Returns untyped string enum (`'vm_bridge'`, `'clipboard'`, `'file'`, etc.) dispatched by 7 `elif` branches in `main()`.

**Impact:** Untestable, unmaintainable, adding a transport requires changes in 2 locations.

### Hardcoded Configuration
`i_flag_hook.py:270-271,283,478,492,681` — Author-specific IPs (`10.211.55.x`), paths (`/home/ericbuess/`), and username baked into shared code. Silent failure for all other users.

### Dead Code: `build_call_graph`
`index_utils.py:132-158` — Complete function, never imported or called. Logic reimplemented inline in `project_index.py:321-392`.

### Duplicated Logic (~130 lines)
Shell parser handles two syntax styles via nearly-identical ~65-line blocks at `index_utils.py:984-1133`.

### Bare `except:` (12 instances)
Catches `KeyboardInterrupt` and `SystemExit` — should be `except Exception:`.

### Magic String Keys
Dense format uses `'f'`, `'g'`, `'d'`, `'at'`, `'deps'` as bare string literals with no constant definitions. Function entry format `name:line:sig:calls:doc` is an implicit 5-field protocol with no schema.

### Non-Reentrant State: `os.chdir`
`stop_hook.py:63` mutates process CWD instead of using `subprocess.run(cwd=...)`.

### Vestigial Data Structures
`call_graph: {}` initialized in all three parser return dicts but never populated.

## Extensibility Analysis

### Adding a Language Parser (Medium Effort)
Requires editing 3 locations:
1. `index_utils.py` — add extension to `PARSEABLE_LANGUAGES` + `CODE_EXTENSIONS`, write `extract_X_signatures()`
2. `project_index.py:build_index()` — add `elif file_path.suffix` branch
3. `project_index.py:convert_to_enhanced_dense_format()` — add language letter to `lang_map`

**Friction:** Hardcoded if/elif dispatch instead of registry.

### Adding a Clipboard Transport (Difficult)
Requires modification in 2 tightly coupled locations:
1. Insert try/except block inside 305-line `copy_to_clipboard()`
2. Add `elif copy_result[0] == 'new_method':` in `main()` with near-duplicate output dict

**Friction:** God Function + string enum + duplicated output dicts = 3-point coupling.

### Changing Index Format (Risky)
Implicit schema with no TypedDict or compile-time safety. The colon-delimited function format is assumed by both `convert_to_enhanced_dense_format()` and `compress_if_needed()` (which indexes `parts[4]`).

## Maintainability Factors

| Factor | Score | Evidence |
|--------|-------|---------|
| Readability | 5/10 | Core readable, but clipboard requires tracking 5 nested blocks across 300 lines |
| Testability | 2/10 | Zero tests; functions depend on filesystem/subprocess with no injection |
| Modifiability | 5/10 | Sound module boundaries, but cross-cutting changes need multi-file edits |
| Dead code | 4/10 | Unused function, vestigial keys, unreachable guards |
| Configuration | 3/10 | Developer-specific hardcodes, no config file |
| Error handling | 4/10 | 12 bare excepts, errors silently swallowed |

## Refactoring Opportunities (Prioritized)

1. **Decompose `copy_to_clipboard`** into independently testable strategy callables with common `(content: str) -> (method, payload)` interface
2. **Replace if/elif parser dispatch** with `PARSER_REGISTRY` dict for one-line language additions
3. **Define dense format as TypedDict** for type-safe schema
4. **Extract duplicated shell parser** into `_parse_shell_function_body()` helper
5. **Remove all dead code** — unused function, vestigial keys, unreachable guards
