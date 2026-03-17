# ADR-008: .python_cmd Executable Validation

**Status:** Accepted
**Date:** 2026-03-17
**Context:** Preventing arbitrary code execution via the `.python_cmd` file

## Decision

Validate the content of `~/.claude-code-project-index/.python_cmd` before using it as a subprocess executable. The file is also written with `chmod 600` during installation.

## Rationale

- `.python_cmd` stores the Python interpreter path discovered during installation
- Its content is used as the first argument to `subprocess.run()` — controlling what binary executes
- Without validation, an attacker who can write to this file achieves persistent code execution on every Claude Code prompt
- The file runs automatically (via hooks) with user privileges

## Implementation

`_validate_python_cmd(cmd_path)` function — duplicated in both `i_flag_hook.py` (line 31) and `stop_hook.py` (line 13) because hooks are self-contained (don't import from each other):

```python
def _validate_python_cmd(cmd_path: str) -> bool:
    path = Path(cmd_path)
    if not path.is_absolute():         # Must be absolute path
        return False
    if not path.exists() or not os.access(str(path), os.X_OK):  # Must exist and be executable
        return False
    basename = path.name
    if not (basename.startswith('python') or basename == 'python3'):  # Must look like Python
        return False
    return True
```

Validation is called before every subprocess invocation. On failure: falls back to `sys.executable` (current interpreter) with a warning to stderr.

`install.sh` line 159: `chmod 600 "$INSTALL_DIR/.python_cmd"` — restricts to owner read/write only.

## Consequences

- Relative paths like `python3` are rejected (must be absolute like `/usr/bin/python3`)
- Non-Python executables (e.g., `/bin/bash`) are rejected
- The validation is a defense-in-depth measure — the file should already be owner-only writable
- Function is duplicated (not shared) because hooks are independent scripts with no shared import path

## Verified Against

- `scripts/i_flag_hook.py:31-50` — _validate_python_cmd definition
- `scripts/stop_hook.py:13-33` — duplicate definition
- `scripts/i_flag_hook.py:218-222` — validation called in generate_index_at_size
- `scripts/stop_hook.py:110-112` — validation called before subprocess
- `install.sh:159` — chmod 600
