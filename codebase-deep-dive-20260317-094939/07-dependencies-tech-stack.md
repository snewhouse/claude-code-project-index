# Dependencies & Tech Stack

## Primary Technologies

| Category | Technology | Version |
|----------|-----------|---------|
| Language | Python | 3.8+ (recommend 3.9+ for ast.unparse) |
| Shell | Bash | macOS/Linux built-in |
| Output | JSON | Minified, compressed |
| VCS | Git | Required for file discovery |

## Design Philosophy: Zero External Dependencies

The project enforces **zero required pip packages** (ADR-002). All core functionality uses Python stdlib only.

## Python Standard Library Usage (12 core + 1 optional)

### Core Modules
| Module | Scripts | Purpose |
|--------|---------|---------|
| `os` | i_flag_hook, project_index | File ops, environ, process execution |
| `sys` | All scripts + tests | Exit, stderr, version checking |
| `pathlib` | All scripts | Path manipulation |
| `json` | All scripts + tests | Index serialization/deserialization |
| `tempfile` | i_flag_hook, project_index | Atomic writes (mkstemp) |
| `re` | index_utils, i_flag_hook | Regex parsing, flag detection |
| `fnmatch` | index_utils | File glob pattern matching |
| `typing` | All scripts | Type annotations |
| `datetime` | project_index, i_flag_hook | Timestamps |
| `hashlib` | i_flag_hook, stop_hook | SHA256 staleness detection |
| `subprocess` | i_flag_hook, stop_hook | git ls-files, indexer spawning |

### Optional Platform-Specific
| Module | Scripts | Purpose | Availability |
|--------|---------|---------|-------------|
| `fcntl` | i_flag_hook | File locking (advisory) | Linux/WSL2 only |

## External Dependencies

### Required: NONE (Zero)

### Optional (Single Fallback)
| Package | When Used | Priority | Fallback |
|---------|-----------|----------|----------|
| `pyperclip` | `-ic` clipboard mode | 4th of 5 transports | File fallback |

### System Tool Dependencies
| Tool | Required? | Usage | Install |
|------|-----------|-------|---------|
| `git` | **Yes** | File discovery (`git ls-files`) | System package |
| `jq` | **Yes** | Hook registration in settings.json | System package |
| `python3` | **Yes** | Script execution | System package |
| `xclip` | No | Clipboard (Linux X11) | `apt install xclip` |
| `clip.exe` | No | Clipboard (WSL2) | Built-in WSL2 |

## Internal Module Dependency Graph

```
project_index.py ──imports──> index_utils.py
    ├── PARSEABLE_LANGUAGES, CODE_EXTENSIONS, MARKDOWN_EXTENSIONS
    ├── IGNORE_DIRS, DIRECTORY_PURPOSES
    ├── extract_python_signatures()
    ├── extract_javascript_signatures()
    ├── extract_shell_signatures()
    ├── extract_markdown_structure()
    ├── parse_file(), get_language_name(), should_index_file()
    └── infer_file_purpose(), infer_directory_purpose()

i_flag_hook.py ──subprocess──> project_index.py
    └── env: INDEX_TARGET_SIZE_K

stop_hook.py ──subprocess──> project_index.py
    └── (no env vars)
```

## Language Parsing Coverage

### Fully Parsed (Signature + Call Graph)
| Language | Extensions | Parser | Accuracy |
|----------|-----------|--------|----------|
| Python | `.py` | `extract_python_signatures()` | ~70% (regex) |
| JavaScript | `.js`, `.jsx` | `extract_javascript_signatures()` | ~60% (regex) |
| TypeScript | `.ts`, `.tsx` | `extract_javascript_signatures()` | ~60% (regex) |
| Shell/Bash | `.sh`, `.bash` | `extract_shell_signatures()` | ~80% (regex) |

### Listed Only (File tracked, not parsed)
`.go`, `.rs`, `.java`, `.c`, `.cpp`, `.rb`, `.php`, `.swift`, `.kt`, `.scala`, `.cs`, `.sql`, `.r`, `.lua`, `.m`, `.ex`, `.exs`, `.jl`, `.dart`, `.vue`, `.svelte` (20+ extensions)

### Special Handling
| Format | Handler | Purpose |
|--------|---------|---------|
| Markdown | `extract_markdown_structure()` | Section headers |
| JSON/HTML/CSS | File listed | Asset tracking |

## Size & Performance Limits

| Constant | Value | Purpose |
|----------|-------|---------|
| `MAX_FILES` | 10,000 | Skip if project exceeds |
| `MAX_INDEX_SIZE` | 1 MB | Hard limit on output JSON |
| `MAX_TREE_DEPTH` | 5 | Directory tree depth |
| `DEFAULT_SIZE_K` | 50 | Default `-i` token target |
| `CLAUDE_MAX_K` | 100 | Max for Claude context |
| `EXTERNAL_MAX_K` | 800 | Max for clipboard export |
