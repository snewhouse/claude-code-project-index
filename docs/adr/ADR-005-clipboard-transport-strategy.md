# ADR-005: Clipboard Transport Strategy Pattern

**Status:** Accepted
**Date:** 2026-03-17
**Context:** How to copy index content to clipboard across diverse environments (local, SSH, tmux)

## Decision

Decompose clipboard handling into independent transport functions, dispatched via ordered lists. SSH and local sessions use different transport lists. File fallback always available.

## Rationale

- Different environments require different clipboard mechanisms
- Strategy pattern makes each transport independently testable
- Adding a new transport requires only: write `_try_X(content)`, append to transport list
- Previous monolithic implementation (305 lines) was untestable and unmaintainable

## Implementation

Transport functions in `scripts/i_flag_hook.py`:

| Function | Line | Mechanism | When Used |
|----------|------|-----------|-----------|
| `_try_osc52(content)` | 363 | OSC 52 terminal escape sequence | SSH, content <= 11KB |
| `_try_tmux_buffer(content)` | 398 | `tmux load-buffer -` via subprocess | SSH, large content |
| `_try_xclip(content)` | 411 | `xclip -selection clipboard` via subprocess | Local Linux with DISPLAY |
| `_try_pyperclip(content)` | 432 | `pyperclip.copy()` library call | Library fallback |
| `_try_file_fallback(content, cwd)` | 441 | `tempfile.mkstemp()` with `0o600` | Always works |

Dispatch lists (line 455-456):
```python
CLIPBOARD_TRANSPORTS = [_try_xclip, _try_pyperclip]      # Local sessions
SSH_TRANSPORTS = [_try_osc52, _try_tmux_buffer]           # SSH sessions
```

Dispatch logic in `copy_to_clipboard()` (line 459, ~15 lines):
1. Build content via `_build_clipboard_content(prompt, index_path)`
2. Detect SSH via `SSH_CONNECTION` or `SSH_CLIENT` env vars
3. Iterate appropriate transport list; first non-None result wins
4. SSH transports also write file fallback (content too large for clipboard alone)
5. If all transports fail: `_try_file_fallback()` (always succeeds)

Each transport returns `(transport_type, data)` on success, `None` on failure. Exceptions caught and skipped.

## Consequences

- No silent Xvfb spawning (removed — previously auto-started X11 virtual framebuffer)
- No hardcoded IPs or VM Bridge code (removed in security remediation)
- File fallback uses restricted permissions (0o600) via `os.fchmod()`
- Content helper `_build_clipboard_content()` separates content construction from transport

## Verified Against

- `scripts/i_flag_hook.py:351-477` — all transport functions and dispatch
- `scripts/i_flag_hook.py:455-456` — CLIPBOARD_TRANSPORTS and SSH_TRANSPORTS lists
- `scripts/i_flag_hook.py:459-477` — copy_to_clipboard dispatch function
