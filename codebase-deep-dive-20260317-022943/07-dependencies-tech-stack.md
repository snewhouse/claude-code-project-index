# Dependencies & Tech Stack

## Primary Technologies

| Technology | Version | Role |
|-----------|---------|------|
| Python | 3.8+ (minimum) | Core implementation language |
| Bash | 4.x+ | Installation, Python discovery, execution shim |
| JSON | N/A | Data format for index output and hook protocol |
| Claude Code Hooks | Current | Integration mechanism (UserPromptSubmit, Stop) |

## External Libraries

**Zero external Python package dependencies.** The entire codebase runs on Python's standard library.

### Required Standard Library Modules

| Module | Used By | Purpose |
|--------|---------|---------|
| `json` | All scripts | JSON parsing, file I/O, hook protocol |
| `sys` | All scripts | Exit codes, stderr output, stdin reading |
| `os` | project_index, i_flag_hook | Env vars, path operations, cwd |
| `re` | index_utils, i_flag_hook | Regex-based code parsing, flag detection |
| `subprocess` | index_utils, i_flag_hook, stop_hook | External command execution (git, python) |
| `hashlib` | i_flag_hook | SHA256 file hashing for staleness detection |
| `time` | i_flag_hook | Timestamps for metadata |
| `pathlib` | All scripts | Modern path manipulation |
| `datetime` | project_index, i_flag_hook | ISO format timestamps |
| `fnmatch` | index_utils | Glob pattern matching for gitignore |
| `typing` | project_index, index_utils | Type annotations |
| `base64` | i_flag_hook | OSC 52 clipboard encoding |

### Required System Tools

| Tool | Required By | Purpose |
|------|-------------|---------|
| **git** | index_utils, i_flag_hook, install.sh | File discovery via `git ls-files`, project root detection |
| **python3** | All scripts | Core interpreter (3.8+ minimum enforced by find_python.sh) |
| **jq** | install.sh, uninstall.sh | JSON manipulation for hook registration in settings.json |

### Optional External Packages

| Package | Import Location | Fallback | Purpose |
|---------|----------------|----------|---------|
| `pyperclip` | i_flag_hook.py:547 | File fallback | Generic clipboard access |
| `vm_client_network` | i_flag_hook.py:280 | Falls through to xclip/pyperclip | VM Bridge Mac clipboard over mosh |
| `vm_client` | i_flag_hook.py:306 | Falls through to other methods | VM Bridge tunnel client (legacy) |

### Optional System Tools

| Tool | Platform | Fallback | Purpose |
|------|----------|----------|---------|
| `xclip` | Linux | pyperclip -> file | Clipboard copy on Linux |
| `Xvfb` | Linux (headless) | Auto-started if no DISPLAY | Virtual display for xclip |
| `tmux` | SSH sessions | File fallback | Buffer management for large clipboard over mosh |
| `pbcopy` | macOS | N/A (Mac only) | Native macOS clipboard |

### Clipboard Fallback Chain

1. VM Bridge network client (`vm_client_network`)
2. VM Bridge tunnel client (`vm_client`)
3. `xclip` with optional `Xvfb`
4. `pyperclip` Python package
5. Write to `.clipboard_content.txt` (always works)

## Internal Dependencies

```
project_index.py
  └── imports from index_utils.py:
      ├── Constants: IGNORE_DIRS, PARSEABLE_LANGUAGES, CODE_EXTENSIONS, etc.
      └── Functions: extract_python_signatures, extract_javascript_signatures,
                     extract_shell_signatures, extract_markdown_structure,
                     infer_file_purpose, infer_directory_purpose,
                     get_language_name, should_index_file, get_git_files

i_flag_hook.py
  └── No internal imports (standalone; calls project_index.py via subprocess)

stop_hook.py
  └── No internal imports (standalone; calls project_index.py via subprocess)

index_utils.py
  └── No internal imports (utility library)
```

## Outdated Dependencies

No external dependencies to track. System tools (git, jq, python3) are universally maintained.

## Known Vulnerabilities

- **No shell injection risk** — All subprocess calls use explicit command lists (not `shell=True`)
- **No network exposure** — Tool runs locally only; VM Bridge IPs are hardcoded for specific author's setup
- **File write to cwd** — `PROJECT_INDEX.json` and `.clipboard_content.txt` are written to the project root

## Environment Variables

| Variable | Consumer | Purpose | Default |
|----------|----------|---------|---------|
| `INDEX_TARGET_SIZE_K` | project_index.py | Target token size | 0 (uses MAX_INDEX_SIZE) |
| `DISPLAY` | i_flag_hook.py | X11 display for xclip | Auto-detect or `:99` |
| `TMUX` | i_flag_hook.py | Detect tmux session | None |
| `SSH_CONNECTION` | i_flag_hook.py | Detect SSH session | None |
| `SSH_CLIENT` | i_flag_hook.py | Detect SSH (fallback) | None |
| `USER` | i_flag_hook.py | Username for SSH commands | System |
| `VIRTUAL_ENV` | find_python.sh | Detect virtualenv | None |
