# PDR-001: claude-code-project-index Project Design Record

**Status:** Active
**Date:** 2026-03-17
**Version:** 0.2.0-beta (from `scripts/project_index.py:17`)

---

## 1. Purpose

Give Claude Code architectural awareness of any codebase by generating a compressed `PROJECT_INDEX.json` containing function signatures, call graphs, dependency graphs, and directory structure. The tool intercepts user prompts via Claude Code hooks, generates or reuses a cached index, and injects it into the session as subagent context or clipboard content.

## 2. System Boundary

The tool operates entirely within the Claude Code hook lifecycle:

- **Inputs:** Claude Code hook events (UserPromptSubmit, Stop)
- **Outputs:** `PROJECT_INDEX.json` (file), `hookSpecificOutput` (stdout JSON), clipboard content
- **Install location:** `~/.claude-code-project-index/`
- **Hook registration:** `~/.claude/settings.json` (patched by `install.sh` via `jq`)

## 3. File Inventory

| File | Lines | Role |
|------|-------|------|
| `scripts/i_flag_hook.py` | ~700 | UserPromptSubmit hook: flag parsing, cache validation, subprocess orchestration, clipboard transport dispatch, hookSpecificOutput emission |
| `scripts/project_index.py` | ~770 | Index pipeline: file discovery, parser dispatch via `parse_file()`, call graph, dense format conversion, 5-step compression, atomic JSON write |
| `scripts/index_utils.py` | ~1350 | Shared library: constants, `PARSER_REGISTRY`, regex parsers (Python/JS/TS/Shell), gitignore handling, `parse_file()` dispatch |
| `scripts/stop_hook.py` | 153 | Stop hook: `should_regenerate()` SHA-256 hash comparison, conditional regeneration |
| `scripts/find_python.sh` | 166 | Python 3.8+ interpreter discovery |
| `scripts/run_python.sh` | 22 | Exec wrapper reading `.python_cmd` |
| `install.sh` | 313 | Bootstrap: copies files, patches hooks, persists Python path with `chmod 600` |
| `uninstall.sh` | 131 | Reverse of install |
| `agents/index-analyzer.md` | ~130 | Subagent prompt (Read/Grep/Glob tools only) |
| `tests/` | 8 files, 46 tests | pytest suite: parsers, flag parsing, compression, security, quality, clipboard, atomic writes, registry |

## 4. Runtime Architecture

### UserPromptSubmit Flow

1. `main()` reads `json.load(stdin)`, extracts `prompt`
2. `parse_index_flag(prompt)` regex-matches `-i[N]` or `-ic[N]`. No flag -> `sys.exit(0)` (fast path)
3. `find_project_root()` walks up from cwd looking for `.git` or project markers
4. `should_regenerate_index()` computes SHA-256 of `git ls-files` paths+mtimes, compares to `_meta.files_hash`
5. If stale: `generate_index_at_size()` validates `.python_cmd` via `_validate_python_cmd()`, spawns `project_index.py` subprocess with `INDEX_TARGET_SIZE_K` env var, then read-modify-writes `_meta` with `fcntl.flock` + atomic `os.replace`
6. If `-i`: emits `hookSpecificOutput` instructing Claude to invoke `index-analyzer` subagent
7. If `-ic`: calls `copy_to_clipboard()` which dispatches over transport lists

### Stop Hook Flow

1. Walk up directory tree for `PROJECT_INDEX.json`
2. `should_regenerate()` checks SHA-256 hash match. If fresh, prints "up to date" to stderr, returns
3. If stale: validates `.python_cmd`, spawns `project_index.py` with `cwd=str(project_root)`, timeout=10

### Index Generation Pipeline

1. `build_index('.')` discovers files via `git ls-files` (fallback: `Path.rglob`)
2. For each file: `parse_file(content, suffix)` dispatches via `PARSER_REGISTRY`
3. Builds bidirectional call graph (intra-file only)
4. `convert_to_enhanced_dense_format()` produces compressed JSON using `KEY_*` constants and `LANG_LETTERS`
5. `compress_if_needed()` applies 5-step progressive compression
6. Atomic write: `tempfile.mkstemp()` + `os.replace()`

### Parser Dispatch

`PARSER_REGISTRY` dict (populated at module load by `register_parsers()`, line 1346 of `index_utils.py`):

| Extension | Parser Function |
|-----------|----------------|
| `.py` | `extract_python_signatures` |
| `.js`, `.jsx` | `extract_javascript_signatures` |
| `.ts`, `.tsx` | `extract_javascript_signatures` |
| `.sh`, `.bash` | `extract_shell_signatures` |

`parse_file(content, extension)` returns `None` for unregistered extensions.

### Clipboard Transport Chain

Two dispatch lists in `i_flag_hook.py:455-456`:

- `SSH_TRANSPORTS = [_try_osc52, _try_tmux_buffer]` (when `SSH_CONNECTION` or `SSH_CLIENT` set)
- `CLIPBOARD_TRANSPORTS = [_try_xclip, _try_pyperclip]` (local sessions)
- `_try_file_fallback` always available as last resort (tempfile with 0o600)

### Dense Format Schema

Constants defined in `project_index.py:40-60`:

| Constant | Key | Content |
|----------|-----|---------|
| `KEY_TIMESTAMP` | `at` | ISO timestamp |
| `KEY_ROOT` | `root` | Absolute project path |
| `KEY_TREE` | `tree` | ASCII directory tree |
| `KEY_FILES` | `f` | Parsed files dict |
| `KEY_GRAPH` | `g` | Call graph edge pairs |
| `KEY_DOCS` | `d` | Markdown headers per doc file |
| `KEY_DEPS` | `deps` | Import graph per file |
| `KEY_DIR_PURPOSES` | `dir_purposes` | Inferred directory roles |
| `KEY_STALENESS` | `staleness` | Epoch timestamp |
| `KEY_META` | `_meta` | Generation metadata |

Language letters (`LANG_LETTERS`, line 54): python=`p`, javascript=`j`, typescript=`t`, shell=`s`, json=`n`.

Function signature format: `name:line:signature:calls:docstring` (colon-delimited).

### Compression Pipeline

5 steps in `compress_if_needed()`, each checks size and returns early:

| Step | Action |
|------|--------|
| 1 | Truncate `tree` to 10 items |
| 2 | Truncate docstrings to 40 chars |
| 3 | Strip docstrings entirely |
| 4 | Delete documentation map (`d` key) |
| 5 | Emergency: keep top-N files by function count + class bonus |

## 5. Security Model

- `.python_cmd` validated: absolute path, exists, executable, `python*` basename
- `.python_cmd` file permissions: `chmod 600`
- Zero hardcoded IPs or author-specific paths
- Zero bare `except:` blocks (all typed)
- Clipboard writes: `tempfile.mkstemp()` + `os.fchmod(fd, 0o600)`
- Index writes: atomic `tempfile.mkstemp()` + `os.replace()`
- Concurrent sessions: `fcntl.flock(LOCK_EX)` (guarded by `HAS_FCNTL`)
- No `shell=True`, no `eval()`, no `exec()`
- All subprocess calls have explicit timeouts

## 6. Dependencies

**External Python:** Zero. Pure stdlib (Python 3.8+).

**Optional:** `pyperclip` (clipboard transport position 4 of 5).

**System tools:** `git` (preferred, fallback to rglob), `jq` (install-time), `xclip` (optional), `tmux` (optional SSH)

## 7. Known Limitations

1. Call graph is intra-file only (cross-file calls not resolved)
2. Parsers are regex-based (known edge cases with multi-line signatures, nested generics)
3. Token estimation approximate (`len(str) // 4`)
4. Stop hook timeout 10s (may be tight for >1000 files, mitigated by smart staleness check)
5. No incremental indexing (full re-parse on every regeneration)
