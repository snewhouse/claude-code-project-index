# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**claude-code-project-index** is a Claude Code hooks-based tool that gives Claude architectural awareness of any codebase. It intercepts user prompts containing `-i` or `-ic` flags via Claude Code hooks, generates a compressed `PROJECT_INDEX.json` containing function signatures, call graphs, and project structure, then routes analysis through a subagent or clipboard export.

Installs to `~/.claude-code-project-index/`. No package manager, no dependencies beyond Python 3.8+ stdlib (pyperclip optional for clipboard).

## Running & Testing

```bash
# Generate index for current project
python3 scripts/project_index.py

# Check version
python3 scripts/project_index.py --version

# Test hook manually (pipe JSON to stdin)
echo '{"prompt": "fix bug -i"}' | python3 scripts/i_flag_hook.py

# Run full test suite
python3 -m pytest tests/ -v

# Run a single test file
python3 -m pytest tests/test_parsers.py -v

# Run a single test
python3 -m pytest tests/test_parsers.py::test_python_simple_function -v

# Run installer (from repo root)
bash install.sh
```

## Architecture

The system is a **hook-driven pipeline** with three phases:

### 1. Hook Detection (`scripts/i_flag_hook.py`)
- Registered as a `UserPromptSubmit` hook in `~/.claude/settings.json`
- Parses `-i[N]` (subagent mode, max 100k tokens) and `-ic[N]` (clipboard mode, max 800k tokens) flags from prompts
- Checks if index needs regeneration via file hash comparison (`_meta.files_hash`)
- Validates `.python_cmd` before execution (`_validate_python_cmd()`)
- Remembers last `-i` size per project in `PROJECT_INDEX.json` metadata
- Outputs `hookSpecificOutput` JSON to inject context into the Claude session
- Clipboard transport uses strategy pattern: `CLIPBOARD_TRANSPORTS` list with `_try_osc52`, `_try_xclip`, `_try_pyperclip`, `_try_file_fallback`

### 2. Index Generation (`scripts/project_index.py` + `scripts/index_utils.py`)
- `build_index()` → walks project files (prefers `git ls-files`) → dispatches to `PARSER_REGISTRY` → builds call graph + dependency graph
- `convert_to_enhanced_dense_format()` → compresses to minified JSON using `KEY_*` constants (`KEY_FILES`=`'f'`, `KEY_GRAPH`=`'g'`, `KEY_DOCS`=`'d'`, `KEY_DEPS`=`'deps'`)
- `compress_if_needed()` → progressive 5-step compression to fit target size
- `index_utils.py` contains all parsing logic + `PARSER_REGISTRY` for data-driven language dispatch
- Parser dispatch: `parse_file(content, extension)` looks up `PARSER_REGISTRY` dict instead of if/elif chains
- Writes use atomic `tempfile.mkstemp()` + `os.replace()` pattern
- Target size passed via `INDEX_TARGET_SIZE_K` environment variable

### 3. Consumption
- **Subagent mode** (`-i`): Hook injects context telling Claude to invoke the `index-analyzer` agent (`agents/index-analyzer.md`) which reads and analyzes `PROJECT_INDEX.json`
- **Clipboard mode** (`-ic`): Copies index + instructions to clipboard (tries OSC 52 → xclip → pyperclip → file fallback) for external AI tools
- **Stop hook** (`scripts/stop_hook.py`): Smart regeneration — checks staleness via `should_regenerate()` before rebuilding; skips when index is fresh

### Key Constants
- `MAX_FILES = 10000`, `MAX_INDEX_SIZE = 1MB`, `MAX_TREE_DEPTH = 5` (in `project_index.py`)
- `DEFAULT_SIZE_K = 50`, `CLAUDE_MAX_K = 100`, `EXTERNAL_MAX_K = 800` (in `i_flag_hook.py`)
- `KEY_FILES`, `KEY_GRAPH`, `KEY_DOCS`, `KEY_DEPS`, `LANG_LETTERS` (dense format constants in `project_index.py`)
- `IGNORE_DIRS`, `PARSEABLE_LANGUAGES`, `PARSER_REGISTRY` (in `index_utils.py`)

## Dense Index Format

The output `PROJECT_INDEX.json` uses compressed keys:
- `at`: timestamp, `root`: project root, `tree`: ASCII directory structure
- `f`: files dict keyed by abbreviated path (`scripts/` → `s/`, `src/` → `sr/`, `tests/` → `t/`)
  - Each file: `[lang_letter, [func_signatures...], {class_data...}]`
  - Function signature format: `name:line:signature:calls:docstring`
- `g`: call graph edges as `[[caller, callee], ...]`
- `d`: documentation map (markdown headers)
- `deps`: dependency graph (imports per file)
- `_meta`: generation metadata (target size, actual size, files hash, timestamps)

## Language Parsing

Regex-based signature extraction for Python, JavaScript/TypeScript, Shell. All other languages are listed (file tracked) but not parsed. Parsers are registered in `PARSER_REGISTRY` (`index_utils.py`). To add a language: write `extract_X_signatures(content)`, register in `PARSER_REGISTRY` dict.

## Extending

**Add a language parser:** Create a function `extract_X_signatures(content: str) -> Dict` in `index_utils.py`, add entries to `PARSER_REGISTRY` in `register_parsers()`, add extension to `PARSEABLE_LANGUAGES` and `CODE_EXTENSIONS`.

**Add a clipboard transport:** Write a `_try_X(content)` function returning `('transport_name', data)` or `None`, add to `CLIPBOARD_TRANSPORTS` or `SSH_TRANSPORTS` list in `i_flag_hook.py`.
