# Design Patterns & Maintainability

**Maintainability Score: 4/10**
**Extensibility Score: 5/10**

## Design Patterns Detected

### Appropriate Use

**Pipeline Pattern — `project_index.py::main()`**
Best-applied pattern in the codebase. Four clearly delineated stages: `build_index` -> `convert_to_enhanced_dense_format` -> `compress_if_needed` -> `write_text`. Each stage takes previous output as sole input and returns a transformed dict. No hidden coupling. Textbook linear transformation pipeline.

**Observer/Hook Pattern — Claude Code integration**
The two hooks (`i_flag_hook.py`, `stop_hook.py`) integrate with Claude Code's event system via JSON stdin/stdout. Contracts are clean. Hooks are correctly kept thin — they orchestrate but don't re-implement business logic.

**Cache-Aside Pattern — `_meta` block**
The `_meta` block in `PROJECT_INDEX.json` stores `files_hash`, `target_size_k`, and timestamps. `should_regenerate_index()` checks this metadata to decide whether to invoke an expensive regeneration subprocess. Valid cache-aside for an expensive operation.

**Two-Pass Parsing Pattern — `extract_*_signatures()` functions**
All three parsers do a first pass to collect function/method names into a set, then use that set during the second pass to resolve call targets. Standard forward-reference resolution, applied correctly.

**Composite Compression Pattern — `compress_if_needed()`**
Sequential lossy compression ladder with early exit on budget satisfaction. Reasonable for budget-constrained serialization.

### Questionable Use

**Strategy Pattern (degraded) — `copy_to_clipboard()`**
The intent is correct: isolate clipboard transport concerns and degrade gracefully across 5 mechanisms. But the implementation collapses all strategies into a single 300-line function with nested try/except. A proper Strategy pattern would have each transport as a callable with a common interface, dispatched by priority from a list.

**Template Method Pattern (informal) — `extract_*_signatures()`**
The three parsers share a structural template (first pass names, second pass imports, third pass bodies) but purely by convention — not enforced by a base class or documented protocol. A future parser author will not naturally discover the pattern and may skip the first-pass step, breaking call detection.

## Anti-Patterns Detected

| Anti-Pattern | Location | Impact |
|-------------|----------|--------|
| **God Function** | `i_flag_hook.py:259-564` (`copy_to_clipboard`, ~305 lines) | Untestable, unreadable, unmaintainable. 6 clipboard protocols in one function. |
| **Hardcoded Configuration** | `i_flag_hook.py:270-271, 283, 478, 492` | IPs, paths specific to original author's VM environment |
| **Dead Code** | `index_utils.py:132-158` (`build_call_graph`) | Never called; live duplicate in `project_index.py` |
| **Duplicated Logic** | `index_utils.py:983-1133` (shell), `project_index.py:321-392` (call graph) | ~170 lines of duplication across two locations |
| **Bare `except: pass`** | 14 occurrences across 4 files | Suppresses `KeyboardInterrupt`, `SystemExit`, `MemoryError` |
| **Magic Strings** | `project_index.py:432` (path abbreviations), `project_index.py:406-414` (dense keys) | Single-letter keys with no constants or schema |
| **Vestigial Data** | `index_utils.py:171, 556, 935` (`call_graph` key) | Initialized as `{}` but never populated in any extractor |
| **Module-Level Mutable State** | `index_utils.py:1278` (`_gitignore_cache`) | Non-reentrant; no cache invalidation mechanism |

## Code Organization

The module boundary between `index_utils.py` (pure parsing/utilities) and `project_index.py` (orchestration) is sound and the primary architectural strength. The hooks are correctly independent — they call the generator via subprocess rather than importing it.

The weakness is that `i_flag_hook.py` acts as both a hook orchestrator AND a multi-platform clipboard compatibility layer. These should be separate modules.

## Extensibility Analysis

### Adding a New Language Parser — **Achievable** (Medium effort)
Steps:
1. Add extension to `PARSEABLE_LANGUAGES` in `index_utils.py`
2. Add extension to `CODE_EXTENSIONS` in `index_utils.py`
3. Write `extract_X_signatures()` following the two-pass template
4. Add `elif` branch in `build_index()` at `project_index.py:224-231`

Friction: Steps 1-3 are in `index_utils.py` but step 4 requires editing `project_index.py`. The `elif` dispatch is not data-driven — a registry pattern (dict mapping extension to parser callable) would make this a single-file change.

### Adding a New Clipboard Transport — **Difficult** (High effort)
Requires inserting 30-80 lines into the 300-line `copy_to_clipboard()` god function. Must read and understand all existing transports to find the correct insertion point. Without decomposition into strategy objects, every addition increases cognitive load on the entire function.

### Changing the Index Format — **Risky** (High effort)
The dense format schema is implicit — assembled in `convert_to_enhanced_dense_format()`, consumed by `compress_if_needed()`, written by `main()`, read by `should_regenerate_index()` and `generate_index_at_size()`. No schema class, no dataclass, no TypedDict. A key rename requires grep-and-replace across files with no compile-time safety. The `agents/index-analyzer.md` prompt also references format fields implicitly.

## Maintainability Factors

- **Readability:** `project_index.py` and `index_utils.py` are readable at the function level. `i_flag_hook.py`'s clipboard function requires tracking 5 nested try/except blocks across 300 lines with environment-specific dead branches. Score: 5/10
- **Testability:** Zero tests exist. `copy_to_clipboard` is structurally untestable (no DI for clipboard mechanisms). `build_index` does direct filesystem I/O. `should_regenerate_index` calls git via subprocess. Score: 2/10
- **Modifiability:** Module boundary between utils and generator is sound. Cross-cutting format changes require multi-file edits with no type safety. Score: 5/10

## Refactoring Opportunities

1. **Decompose `copy_to_clipboard`** into a list of strategy callables with a common `(content: str) -> Tuple[str, Any]` interface. Each transport becomes independently testable.

2. **Data-driven parser dispatch** — Replace the `if/elif` chain in `build_index()` with a registry: `PARSER_REGISTRY = {'.py': extract_python_signatures, '.js': extract_javascript_signatures, ...}`. New languages become a one-line registration.

3. **Define dense format as TypedDict** — Structural changes produce type errors rather than silent runtime failures.

4. **Extract shared utilities** — `_get_python_command()`, `_find_project_root()`, `_classify_value_type()` into `index_utils.py`.

5. **Remove dead code** — Delete `build_call_graph`, vestigial `call_graph` key, unused variables in shell parser, non-functional `MAX_ITERATIONS` guard.
