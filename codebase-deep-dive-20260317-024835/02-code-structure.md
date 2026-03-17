# Code Structure

## Directory Hierarchy

```
claude-code-project-index/
├── scripts/                        # Core Python modules + shell utilities
│   ├── project_index.py           # Main indexer (775 lines, v0.2.0-beta)
│   ├── index_utils.py             # Shared parsing & utilities (~1400 lines)
│   ├── i_flag_hook.py             # UserPromptSubmit hook (~780 lines)
│   ├── stop_hook.py               # Stop hook (~90 lines)
│   ├── run_python.sh              # Python dispatch wrapper (23 lines)
│   └── find_python.sh             # Python version discovery (167 lines)
├── agents/                         # Claude Code agent definitions
│   └── index-analyzer.md          # Subagent for deep index analysis
├── install.sh                     # Installation script (314 lines)
├── uninstall.sh                   # Cleanup script (132 lines)
├── CLAUDE.md                      # Project documentation for Claude Code
├── README.md                      # User-facing documentation
├── LICENSE                        # Project license
└── PROJECT_INDEX.json             # Generated artifact (auto-created)
```

## Module Organization

Functional, module-based architecture with **no classes**:

| Module | Lines | Functions | Role |
|--------|-------|-----------|------|
| `index_utils.py` | ~1400 | 17 | Pure utility functions: parsers, filters, constants |
| `project_index.py` | ~775 | 6 | Pipeline: build → transform → compress → write |
| `i_flag_hook.py` | ~780 | 8 | Hook: parse → cache-check → generate → dispatch |
| `stop_hook.py` | ~90 | 1 | Teardown: unconditional regeneration |

**Import structure:**
```
project_index.py ──imports──→ index_utils.py (11+ functions/constants)
i_flag_hook.py ──subprocess──→ project_index.py (process isolation)
stop_hook.py ──subprocess──→ project_index.py (process isolation)
index_utils.py → (stdlib only, no internal deps)
```

## Entry Points

| Entry Point | Type | Trigger |
|-------------|------|---------|
| `i_flag_hook.py` | UserPromptSubmit hook | Every user prompt |
| `stop_hook.py` | Stop hook | Session termination |
| `project_index.py` | CLI | Direct invocation or subprocess |
| `install.sh` | Script | One-time setup |
| `/index` command | Claude Code command | User types `/index` |
| `index-analyzer` | Subagent | Invoked by `-i` flag |

## Configuration

| File | Location | Purpose |
|------|----------|---------|
| `PROJECT_INDEX.json` | Project root | Generated index with embedded `_meta` state |
| `.python_cmd` | `~/.claude-code-project-index/` | Persisted Python interpreter path |
| `settings.json` | `~/.claude/` | Hook registration (patched by install.sh) |
| `index.md` | `~/.claude/commands/` | `/index` command definition |
| `index-analyzer.md` | `~/.claude/agents/` | Installed subagent definition |

## Key Constants

| Constant | Value | Location |
|----------|-------|----------|
| `MAX_FILES` | 10,000 | `project_index.py:36` |
| `MAX_INDEX_SIZE` | 1 MB | `project_index.py:37` |
| `MAX_TREE_DEPTH` | 5 levels | `project_index.py:38` |
| `DEFAULT_SIZE_K` | 50k tokens | `i_flag_hook.py` |
| `CLAUDE_MAX_K` | 100k tokens | `i_flag_hook.py` |
| `EXTERNAL_MAX_K` | 800k tokens | `i_flag_hook.py` |
| `__version__` | "0.2.0-beta" | `project_index.py:33` |
| `IGNORE_DIRS` | 18 dirs | `index_utils.py:13` |

## Test Structure

**No test suite exists.** Zero directories, zero files, zero coverage. Verification is manual only.

## Type System

- Modern Python 3.8+ type hints (`Dict`, `List`, `Optional`, `Tuple`, `Set`)
- No Pydantic models, dataclasses, or TypedDicts
- No `py.typed` marker
