# ADR-007: Smart Stop Hook with Staleness Check

**Status:** Accepted
**Date:** 2026-03-17
**Context:** Avoiding unnecessary index regeneration at session end

## Decision

The stop hook checks if the index is already up-to-date before spawning the regeneration subprocess. Uses the same SHA-256 hash comparison as the start hook.

## Rationale

- Previous behavior: unconditionally regenerated on every session end, even if nothing changed
- For large projects, regeneration takes 10-30 seconds — wasted if no files changed
- The hash comparison runs in <1 second (git ls-files + stat calls)
- Conservative default: on any error in the staleness check, regenerate (safe fallback)

## Implementation

`should_regenerate()` function in `scripts/stop_hook.py` (line 36):

1. If `PROJECT_INDEX.json` doesn't exist: return True
2. Run `git ls-files --cached --others --exclude-standard` (timeout: 5s)
3. Build SHA-256 hash of sorted `filepath:mtime` strings, truncate to 16 hex chars
4. Read `_meta.files_hash` from existing index
5. Return `current_hash != stored_hash`
6. On any exception: return True (regenerate to be safe)

Called in `main()` at line 90, before the subprocess spawn:
```python
if not should_regenerate(project_root, index_path):
    print("PROJECT_INDEX.json is up to date, skipping refresh", file=sys.stderr)
    return
```

## Consequences

- Sessions where no code changed exit the stop hook in <1 second (was 10-30s)
- The hash uses the same algorithm as `i_flag_hook.py:calculate_files_hash()` — any mismatch means one of them will trigger regeneration
- If `git` is unavailable, always regenerates (conservative)

## Verified Against

- `scripts/stop_hook.py:36-68` — should_regenerate() implementation
- `scripts/stop_hook.py:88-92` — called before subprocess.run
- `scripts/stop_hook.py:131` — cwd=str(project_root) (no os.chdir)
