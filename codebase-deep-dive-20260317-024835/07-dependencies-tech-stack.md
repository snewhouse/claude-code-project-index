# Dependencies & Tech Stack

## Primary Technologies

| Technology | Version | Role |
|------------|---------|------|
| Python | 3.8+ (supports 3.8-3.13) | Core language for all scripts |
| Bash | 3.2+ | Shell scripts (install, find_python, run_python) |
| Git | Any | File discovery (`git ls-files`) |
| jq | Any | JSON manipulation during install |

## External Python Libraries: ZERO

This project uses **zero external pip dependencies**. All Python code is pure stdlib.

### Stdlib Modules Used

| Module | Purpose | Files |
|--------|---------|-------|
| `json` | Index I/O, hook communication | All 4 .py files |
| `sys` | stderr, exit codes | All 4 .py files |
| `os` | Env vars, paths, process management | All 4 .py files |
| `re` | Regex (signatures, imports, flags) | 3 files |
| `pathlib` | Cross-platform path handling | All 4 .py files |
| `subprocess` | External commands (git, Python) | 3 files |
| `hashlib` | SHA-256 for cache validation | `i_flag_hook.py` |
| `time` | Timestamps | `i_flag_hook.py` |
| `datetime` | Index generation timestamps | 2 files |
| `fnmatch` | Glob-pattern file matching | `index_utils.py` |
| `typing` | Type hints | 2 files |

### Optional: `pyperclip`
- **Status:** OPTIONAL (graceful degradation)
- **Used in:** `i_flag_hook.py` clipboard fallback chain (position 6 of 7)
- **Fallback:** OSC 52 → xclip → pyperclip → file fallback

## System Tool Dependencies

| Tool | Required | Purpose | Fallback |
|------|----------|---------|----------|
| `bash` | YES | Shell interpreter | None |
| `python3` (3.8+) | YES | All hook execution | None |
| `git` | Recommended | File discovery | `Path.rglob('*')` |
| `jq` | Install only | Update settings.json | None |
| `xclip` | Optional | Clipboard (X11 Linux) | OSC 52 → pyperclip → file |
| `pbcopy` | Optional | Clipboard (macOS) | Same fallback chain |

## Internal Module Dependencies

```
project_index.py
  └── imports from index_utils.py:
      ├── IGNORE_DIRS, PARSEABLE_LANGUAGES, CODE_EXTENSIONS
      ├── extract_python_signatures()
      ├── extract_javascript_signatures()
      ├── extract_shell_signatures()
      ├── extract_markdown_structure()
      ├── infer_file_purpose(), infer_directory_purpose()
      ├── get_language_name(), should_index_file()
      └── get_git_files()

i_flag_hook.py → subprocess → project_index.py (process isolation)
stop_hook.py   → subprocess → project_index.py (process isolation)
index_utils.py → no internal dependencies (stdlib only)
```

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| macOS | Supported | Bash 3.2+, Homebrew Python detection |
| Linux | Supported | Bash 4.0+, apt/dnf/pacman |
| Windows | WSL only | Requires WSL2 + Linux environment |

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `INDEX_TARGET_SIZE_K` | Target compression size (tokens) |
| `PYTHON_CMD` | Override auto-detected Python |
| `VIRTUAL_ENV` | Detect active venv |
| `SSH_CONNECTION` / `SSH_CLIENT` | SSH session detection |
| `TMUX` | tmux session detection |
| `DISPLAY` | X11 display for xclip |

## Assessment

| Dimension | Result |
|-----------|--------|
| External Python packages | **0** |
| System tool dependencies | **4 required** (bash, python3, git, jq) |
| Optional dependencies | **1** (pyperclip, with 4-step fallback) |
| Security risk | **Minimal** (no transitive deps, no lockfile poisoning) |
| Maintainability | **Excellent** (no version chasing) |
| Portability | **High** (macOS + Linux, Python 3.8-3.13) |
| Installation complexity | **Low** (single bash script) |
