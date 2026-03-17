# ADR-001: Hook-Driven Architecture

**Status:** Accepted
**Date:** 2026-03-17
**Context:** How the tool integrates with Claude Code

## Decision

Use Claude Code's hook system (`UserPromptSubmit` and `Stop` events) as the sole integration mechanism. No daemon, no server, no background process.

## Rationale

- Hooks execute automatically — no user action needed after initial `-i` usage
- Process isolation: hooks spawn subprocess for index generation, keeping hook scripts thin
- Non-blocking: hooks exit 0 on failure, never blocking the user's prompt
- No persistent state beyond `PROJECT_INDEX.json` and `.python_cmd`

## Implementation

- `i_flag_hook.py` registered as `UserPromptSubmit` hook (timeout: 20s in settings.json, 30s internal subprocess)
- `stop_hook.py` registered as `Stop` hook (timeout: 10s)
- Both hooks read stdin JSON, emit stdout JSON per Claude Code hook protocol
- Registration performed by `install.sh` via `jq` patching of `~/.claude/settings.json`

## Consequences

- Tool cannot provide real-time index updates (only updates on prompt or session end)
- Each hook invocation pays stdin JSON parsing + Python startup cost (~50ms)
- No inter-session communication (each hook invocation is stateless)

## Verified Against

- `install.sh:249-277` — hook registration via jq
- `i_flag_hook.py:main()` — json.load(stdin), json.dumps to stdout
- `stop_hook.py:main()` — same pattern
