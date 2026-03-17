# Architecture Overview

**Codebase:** claude-code-project-index
**Analysis Date:** 2026-03-17

## Architectural Pattern

**Hook-Driven Pipeline (Trigger-Transform-Inject)**

The system is a pipeline with two trigger points that intercept Claude Code lifecycle events:

```
[Trigger: UserPromptSubmit]   [Trigger: Stop]
        |                            |
  i_flag_hook.py              stop_hook.py
        |                            |
  [Transform]                  [Transform]
  project_index.py         project_index.py
  (via subprocess)          (via subprocess)
        |                            |
  [Inject/Route]             [Refresh file]
  hookSpecificOutput         PROJECT_INDEX.json
  to Claude session
```

Two routing branches at injection:
- **Subagent mode** (`-i`): Injects `additionalContext` instructing Claude to invoke the `index-analyzer` agent
- **Clipboard mode** (`-ic`): Copies index to clipboard via strategy-pattern transport chain

Decision documented in ADR-001: daemon/server architectures explicitly rejected.

## Core Components

| Component | Responsibility | LOC |
|-----------|---------------|-----|
| `i_flag_hook.py` | Hook orchestrator: flag parsing, staleness detection, subprocess dispatch, clipboard transport, metadata injection | ~539 |
| `project_index.py` | Index builder: file discovery, parsing dispatch, call graph, dense format, progressive compression, atomic write | ~760 |
| `index_utils.py` | Parsing engine: regex parsers for Python/JS/TS/Shell, PARSER_REGISTRY, shared constants, helpers | ~1283 |
| `stop_hook.py` | Session-end refresher: staleness check, conditional re-index | ~132 |
| `index-analyzer.md` | Subagent definition: reads PROJECT_INDEX.json, provides code intelligence | Agent def |
| `install.sh` | System integrator: copies scripts, registers hooks, detects Python | ~315 |

## Separation of Concerns

| Concern | Location | Assessment |
|---------|----------|------------|
| Hook protocol I/O | `main()` in both hooks | Clean |
| Index staleness | `should_regenerate_index()` / `should_regenerate()` | Duplicated |
| Index generation | `project_index.py:build_index()` | Clean |
| Language parsing | `index_utils.py:extract_*_signatures()` | Clean, extensible |
| Parser dispatch | `index_utils.py:PARSER_REGISTRY` | Clean (ADR-003) |
| Clipboard transport | `i_flag_hook.py:CLIPBOARD_TRANSPORTS` | Clean (ADR-005) |
| Metadata injection | `i_flag_hook.py:generate_index_at_size()` | **Violation** — dual-writer |

## Inter-Component Communication

1. **Process boundary via subprocess** — hooks spawn indexer with `INDEX_TARGET_SIZE_K` env var
2. **File-based IPC via `PROJECT_INDEX.json`** — sole communication artifact
3. **Hook protocol I/O** — stdin JSON in, stdout JSON out
4. **Clipboard strategy pattern** — ordered transport list with fallback
5. **Parser registry** — data-driven dispatch via dict lookup

## Modularity Assessment

- `index_utils.py`: **High cohesion** — focused parsing logic and config
- `project_index.py`: **Medium cohesion** — combines discovery, transformation, serialization
- `i_flag_hook.py`: **Medium-low cohesion** — orchestration, clipboard, metadata, flags, size memory

## Strengths

1. Zero external Python dependencies (ADR-002)
2. Atomic writes with `tempfile.mkstemp()` + `os.replace()` (ADR-006)
3. Progressive 5-step compression for variable project sizes (ADR-004)
4. Git-first file discovery with manual fallback
5. Parser registry eliminates if/elif chains (ADR-003)
6. Non-blocking failure policy — hooks never block user workflow
7. Clipboard transport graceful degradation (ADR-005)

## Concerns

1. **Dual-writer on PROJECT_INDEX.json** — metadata injection should be in project_index.py
2. **_validate_python_cmd() duplication** — identical in both hooks, belongs in index_utils.py
3. **Regex parser fragility** — ~70% Python accuracy, edge cases in ADR-003
4. **Token estimation approximate** — `len(str) // 4` heuristic underestimates for code
5. **Stop hook reimplements hash logic** — DRY violation with i_flag_hook.py
6. **MAX_ITERATIONS guard is dead code** — only 5 steps, counter never exceeds 5
