# Code Structure

## Directory Hierarchy

```
claude-code-project-index/
├── agents/
│   └── index-analyzer.md           # Subagent definition for deep analysis
├── scripts/                        # Core Python and Shell implementation
│   ├── project_index.py            # Main indexer (765 lines)
│   ├── index_utils.py              # Shared parsing utilities (1400+ lines)
│   ├── i_flag_hook.py              # UserPromptSubmit hook (778 lines)
│   ├── stop_hook.py                # Session stop hook (87 lines)
│   ├── find_python.sh              # Python 3.8+ discovery
│   └── run_python.sh               # Python execution shim
├── install.sh                      # System-wide installer
├── uninstall.sh                    # Cleanup script
├── CLAUDE.md                       # Project guidance for Claude Code
├── README.md                       # User-facing documentation
├── PROJECT_INDEX.json              # Generated output (self-referential)
└── LICENSE                         # MIT
```

## Module Organization

**No packages** — all Python files are standalone scripts in `scripts/`. The only internal import is `project_index.py` importing from `index_utils.py` (requires same directory or sys.path).

| Module | Lines | Role |
|--------|-------|------|
| `index_utils.py` | ~1400 | Utility library (largest file) |
| `i_flag_hook.py` | ~778 | Hook orchestrator |
| `project_index.py` | ~765 | Index generator |
| `stop_hook.py` | ~87 | Maintenance hook |

## Entry Points

| Entry Point | Type | Trigger |
|-------------|------|---------|
| `i_flag_hook.py::main()` | Claude Code UserPromptSubmit hook | User prompt containing `-i` or `-ic` flag |
| `stop_hook.py::main()` | Claude Code Stop hook | Session end |
| `project_index.py::main()` | CLI script | Manual: `python3 project_index.py` or subprocess from hooks |
| `/index` command | Claude Code slash command | User types `/index` |
| `index-analyzer` agent | Claude Code subagent | Invoked when `-i` flag triggers subagent mode |

All Python entry points use `if __name__ == '__main__': main()` pattern.

## Configuration

| File/Variable | Location | Purpose |
|---------------|----------|---------|
| `~/.claude/settings.json` | System | Hook registration (modified by installer) |
| `~/.claude-code-project-index/.python_cmd` | System | Cached Python binary path |
| `INDEX_TARGET_SIZE_K` env var | Runtime | Target token size for compression |
| `PROJECT_INDEX.json._meta` | Per-project | Generation metadata, cached file hash, remembered size |

## Test Structure

**No automated test suite exists.** The PROJECT_INDEX.json in the repository references a `tests/` directory with 4 files, but this directory does not exist on disk — likely from a previous state or the index is stale.

Testing is manual:
- Run `python3 scripts/project_index.py` and inspect output
- Pipe test JSON to hook: `echo '{"prompt": "test -i"}' | python3 scripts/i_flag_hook.py`
- Run `install.sh` and verify hooks in `~/.claude/settings.json`

## Key Constants

**index_utils.py:**
- `IGNORE_DIRS`: `.git`, `node_modules`, `__pycache__`, `.venv`, `venv`, `env`, `build`, `dist`, `.next`, `target`, `.pytest_cache`, `coverage`, `.idea`, `.vscode`, `.DS_Store`, `eggs`, `.eggs`, `.claude`
- `PARSEABLE_LANGUAGES`: `.py` (python), `.js/.jsx` (javascript), `.ts/.tsx` (typescript), `.sh/.bash` (shell)
- `CODE_EXTENSIONS`: 30+ extensions tracked (listing only for non-parsed languages)

**i_flag_hook.py:**
- `DEFAULT_SIZE_K = 50`, `MIN_SIZE_K = 1`, `CLAUDE_MAX_K = 100`, `EXTERNAL_MAX_K = 800`

**project_index.py:**
- `MAX_FILES = 10000`, `MAX_INDEX_SIZE = 1MB`, `MAX_TREE_DEPTH = 5`
