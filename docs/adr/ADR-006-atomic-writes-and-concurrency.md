# ADR-006: Atomic Writes and Concurrency Safety

**Status:** Accepted
**Date:** 2026-03-17
**Context:** Preventing PROJECT_INDEX.json corruption from interrupted writes or concurrent Claude Code sessions

## Decision

Use `tempfile.mkstemp()` + `os.replace()` for all `PROJECT_INDEX.json` writes. Use `fcntl.flock(LOCK_EX)` for read-modify-write operations. Guard `fcntl` import for non-Linux portability.

## Rationale

- `os.replace()` is atomic on POSIX (same-filesystem rename)
- `tempfile.mkstemp()` creates the temp file in the same directory, ensuring same filesystem
- `fcntl.flock` prevents concurrent sessions from interleaving read-modify-write cycles
- Previous non-atomic `write_text()` could produce corrupt JSON on interrupt

## Implementation

### Atomic write in `project_index.py` (line 749-768)

```python
tmp_fd, tmp_path = tempfile.mkstemp(dir=str(output_path.parent), suffix='.tmp', prefix='.PROJECT_INDEX_')
try:
    os.write(tmp_fd, content.encode('utf-8'))
    os.close(tmp_fd)
    os.replace(tmp_path, str(output_path))  # POSIX atomic
except Exception:
    # cleanup temp file on failure
    ...
```

### Locked read-modify-write in `i_flag_hook.py` (generate_index_at_size)

The hook reads `PROJECT_INDEX.json`, adds `_meta` fields, writes back. This uses `fcntl.flock(LOCK_EX)` when available:

```python
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False
```

If `HAS_FCNTL` is False (e.g., Windows), locking is skipped but atomic writes still apply.

### File fallback writes

Clipboard file fallback uses `tempfile.mkstemp()` + `os.fchmod(fd, 0o600)` — restricted permissions, no world-readable files in project directory.

## Consequences

- Temp files (`.PROJECT_INDEX_*.tmp`) may be left behind on hard crash (acceptable — cleaned on next run)
- `fcntl.flock` is advisory, not mandatory — a non-cooperating process could still interleave
- On non-Linux (if ever ported), locking is silently skipped

## Verified Against

- `scripts/project_index.py:749-768` — atomic write with try/finally cleanup
- `scripts/i_flag_hook.py:18-22` — guarded fcntl import with HAS_FCNTL
- `scripts/i_flag_hook.py:441-451` — _try_file_fallback with tempfile + fchmod
