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

# Run installer (from repo root)
bash install.sh

# No test suite exists — verify by running the indexer on this repo and inspecting PROJECT_INDEX.json
```

## Architecture

The system is a **hook-driven pipeline** with three phases:

### 1. Hook Detection (`scripts/i_flag_hook.py`)
- Registered as a `UserPromptSubmit` hook in `~/.claude/settings.json`
- Parses `-i[N]` (subagent mode, max 100k tokens) and `-ic[N]` (clipboard mode, max 800k tokens) flags from prompts
- Checks if index needs regeneration via file hash comparison (`_meta.files_hash`)
- Remembers last `-i` size per project in `PROJECT_INDEX.json` metadata
- Outputs `hookSpecificOutput` JSON to inject context into the Claude session

### 2. Index Generation (`scripts/project_index.py` + `scripts/index_utils.py`)
- `build_index()` → walks project files (prefers `git ls-files`) → parses signatures → builds call graph + dependency graph
- `convert_to_enhanced_dense_format()` → compresses to minified JSON with short keys (`f`=files, `g`=graph, `d`=docs, `deps`=dependencies)
- `compress_if_needed()` → progressive 5-step compression (truncate tree → truncate docs → remove docs → remove doc map → emergency file truncation) to fit target size
- `index_utils.py` contains all parsing logic: regex-based extractors for Python, JavaScript/TypeScript, and Shell signatures
- Target size passed via `INDEX_TARGET_SIZE_K` environment variable

### 3. Consumption
- **Subagent mode** (`-i`): Hook injects context telling Claude to invoke the `index-analyzer` agent (`agents/index-analyzer.md`) which reads and analyzes `PROJECT_INDEX.json`
- **Clipboard mode** (`-ic`): Copies index + instructions to clipboard (tries VM Bridge → OSC 52 → xclip → pyperclip → file fallback) for external AI tools
- **Stop hook** (`scripts/stop_hook.py`): Regenerates index at session end if `PROJECT_INDEX.json` exists

### Key Constants
- `MAX_FILES = 10000`, `MAX_INDEX_SIZE = 1MB`, `MAX_TREE_DEPTH = 5` (in `project_index.py`)
- `DEFAULT_SIZE_K = 50`, `CLAUDE_MAX_K = 100`, `EXTERNAL_MAX_K = 800` (in `i_flag_hook.py`)
- `IGNORE_DIRS` and `PARSEABLE_LANGUAGES` defined in `index_utils.py`

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

Full signature extraction (regex-based, no AST): Python, JavaScript/TypeScript, Shell. All other languages are listed (file tracked) but not parsed. Parsers are in `index_utils.py` — `extract_python_signatures()`, `extract_javascript_signatures()`, `extract_shell_signatures()`.
