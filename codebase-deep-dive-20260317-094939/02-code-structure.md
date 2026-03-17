# Code Structure

## Directory Hierarchy

```
claude-code-project-index/
├── scripts/                    # Core Python scripts (4 .py, 2 .sh)
│   ├── project_index.py             # Index generation pipeline (760 LOC)
│   ├── index_utils.py               # Shared parsers & config (1283 LOC)
│   ├── i_flag_hook.py               # UserPromptSubmit hook (539 LOC)
│   ├── stop_hook.py                 # Smart stop hook (132 LOC)
│   ├── run_python.sh                # Python executor wrapper (~23 LOC)
│   └── find_python.sh              # Python version finder (~167 LOC)
├── tests/                      # Test suite (11 test modules)
│   ├── conftest.py                  # 3 fixtures: sample_python/js/shell_source
│   ├── test_parsers.py              # Characterization tests for parser behavior
│   ├── test_flag_parsing.py         # -i/-ic flag detection & parsing
│   ├── test_compression.py          # Progressive compression logic
│   ├── test_clipboard.py            # Clipboard transport strategies
│   ├── test_security.py             # IP validation, executable validation
│   ├── test_quality.py              # Code quality checks (no bare excepts)
│   ├── test_registry.py             # Parser registry dispatch
│   ├── test_atomic_writes.py        # Concurrent write safety
│   ├── test_utils.py                # Utility function tests
│   └── __init__.py
├── docs/
│   ├── adr/                         # 8 Architectural Decision Records
│   │   ├── ADR-001-hook-driven-architecture.md
│   │   ├── ADR-002-zero-external-dependencies.md
│   │   ├── ADR-003-regex-based-parsers.md
│   │   ├── ADR-004-progressive-compression.md
│   │   ├── ADR-005-clipboard-transport-strategy.md
│   │   ├── ADR-006-atomic-writes-and-concurrency.md
│   │   ├── ADR-007-smart-stop-hook.md
│   │   ├── ADR-008-python-cmd-validation.md
│   │   └── INDEX.md
│   └── pdr/                         # 1 Project Design Record
│       ├── PDR-001-project-design.md
│       └── INDEX.md
├── agents/
│   └── index-analyzer.md            # Subagent for deep index analysis
├── install.sh                       # Installation orchestrator (~315 LOC)
├── uninstall.sh                     # Cleanup script
├── CLAUDE.md                        # Project guidelines for Claude Code
├── README.md                        # Documentation
└── PROJECT_INDEX.json               # Generated output (per-project)
```

## Module Organization

**No traditional package structure** — standalone scripts approach:

- Scripts are executables, not Python modules
- All shared code lives in `index_utils.py`, imported by other scripts
- **Import hierarchy**: `project_index.py`, `i_flag_hook.py` import from `index_utils.py`; `stop_hook.py` is fully standalone
- **No classes** in production code — functional programming style throughout
- Data-driven dispatch via `PARSER_REGISTRY` dict

## Entry Points

| Script | Hook Type | Invocation | Purpose |
|--------|-----------|-----------|---------|
| `i_flag_hook.py` | UserPromptSubmit | Auto (settings.json) | Detects `-i[N]`/`-ic[N]` flags |
| `stop_hook.py` | Stop | Auto (settings.json) | Refreshes index if stale |
| `project_index.py` | Manual/subprocess | `/index` command or via hook | Generates PROJECT_INDEX.json |
| `install.sh` | Manual | `bash install.sh` | One-time setup |

## Configuration

| File | Location | Purpose |
|------|----------|---------|
| `~/.claude/settings.json` | User home | Hook registration (auto-updated by installer) |
| `~/.claude-code-project-index/.python_cmd` | Install dir | Saved Python command path |
| `~/.claude/commands/index.md` | User home | `/index` slash command definition |
| `~/.claude/agents/index-analyzer.md` | User home | Subagent for index analysis |
| `PROJECT_INDEX.json` | Per-project | Generated compressed index |

## Test Structure

11 test modules covering:
- **Characterization tests** — capture actual parser behavior, not aspirational
- **Fixture-based** with language samples (Python, JS, Shell) in `conftest.py`
- **Strategy pattern tests** for clipboard transports
- **Security tests** for validation functions
- **Quality tests** for code hygiene (no bare excepts, etc.)

Test runner: `pytest` (only external dev dependency)
