# Recommendations & Action Plan

## Priority Matrix

| Priority | ID | Category | Issue | Effort | Impact |
|----------|-----|----------|-------|--------|--------|
| P0 | C-1 | Security | Remove hardcoded IPs + SSH injection | 1h | Critical |
| P0 | C-2 | Security | Validate `.python_cmd` before execution | 1h | Critical |
| P0 | H-1 | Security | Remove unauthenticated LAN probing | 30min | Critical |
| P1 | H-2 | Security | Replace `os.chdir()` with `cwd=` | 5min | High |
| P1 | H-3 | Security | Remove author-specific `sys.path` insertions | 30min | High |
| P1 | M-2 | Quality | Replace 12 bare `except:` with `except Exception:` | 1h | High |
| P1 | Q-1 | Quality | Delete dead `build_call_graph` function | 15min | Medium |
| P2 | Q-2 | Quality | Deduplicate shell parser (~130 lines) | 1h | Medium |
| P2 | Q-3 | Testing | Add initial test suite (20 focused tests) | 3h | High |
| P2 | Q-4 | Design | Decompose `copy_to_clipboard` god function | 2-3h | High |
| P3 | Q-5 | Quality | Define dense format constants/TypedDict | 1h | Medium |
| P3 | Q-6 | Design | Implement parser registry (data-driven dispatch) | 1h | Medium |
| P3 | H-4 | Security | Implement atomic writes for `PROJECT_INDEX.json` | 1h | Medium |

## Quick Wins (Low Effort, High Impact)

### 1. Replace `os.chdir()` with `cwd=` parameter
- **Effort:** 5 minutes (one-line change)
- **Impact:** Eliminates global CWD mutation vulnerability
- **Location:** `scripts/stop_hook.py:63`
- **Fix:** `subprocess.run([...], cwd=str(project_root), ...)`

### 2. Replace 12 bare `except:` with `except Exception:`
- **Effort:** 1 hour (global search-replace + review)
- **Impact:** Restores error visibility, allows Ctrl+C interruption
- **Fix:** `grep -n 'except:' scripts/*.py` → replace each

### 3. Delete dead code
- **Effort:** 15 minutes
- **Impact:** Prevents confusion, removes maintenance burden
- **Actions:**
  - Remove `build_call_graph()` from `index_utils.py:132-158`
  - Remove `call_graph: {}` from all 3 parser return dicts
  - Remove `in_function`, `current_function`, `function_start_line` from shell parser
  - Remove stale comments ("These functions are now imported from index_utils")

## Security Fixes (Prioritized)

### Critical (Fix Immediately)

**C-1: Remove all hardcoded IPs and SSH commands**
- Delete VM Bridge section at `i_flag_hook.py:270-316` (IP probing)
- Delete SSH sync at `i_flag_hook.py:476-492`
- Delete hardcoded IP references at `i_flag_hook.py:681`
- Replace with: configurable dotfile or env var, local file fallback + OSC 52 for SSH

**C-2: Validate `.python_cmd` content**
- At `i_flag_hook.py:189-200` and `stop_hook.py:44-65`:
  - Assert path is absolute
  - Assert file exists and is executable
  - Assert path matches `python*` pattern
- In `install.sh:158`: add `chmod 600 "$INSTALL_DIR/.python_cmd"`

### High (Fix This Sprint)

**H-1: Remove LAN probing** — Delete `10.211.55.x` and `192.168.1.1` IP array. Require explicit opt-in.

**H-3: Remove `sys.path` insertions** — Delete all `sys.path.insert(0, bridge_path)` referencing author-specific directories.

## Refactoring Opportunities

### Decompose `copy_to_clipboard` (305 lines → 5 strategy functions)

**Current:** Single monolith with 7 nested try/except blocks.

**Desired:**
```python
CLIPBOARD_TRANSPORTS = [
    _try_osc52,      # SSH sessions
    _try_xclip,      # Local Linux
    _try_pyperclip,  # Python fallback
    _try_file,       # File fallback
]

def copy_to_clipboard(content: str) -> Tuple[str, Any]:
    for transport in CLIPBOARD_TRANSPORTS:
        result = transport(content)
        if result:
            return result
    return ('error', 'All transports failed')
```

### Implement Parser Registry

**Current:** Hardcoded if/elif in `build_index()`.

**Desired:**
```python
PARSER_REGISTRY = {
    '.py': extract_python_signatures,
    '.js': extract_javascript_signatures,
    '.ts': extract_javascript_signatures,
    '.sh': extract_shell_signatures,
    '.bash': extract_shell_signatures,
}
```

## Testing Strategy

### Initial Test Suite (20 focused tests)

| File | Tests | Focus |
|------|-------|-------|
| `test_parsers.py` | 8 | Python: async, decorators, multi-line sigs, nested classes, enums |
| `test_js_parser.py` | 4 | Arrow functions, class methods, TS interfaces, type aliases |
| `test_shell_parser.py` | 3 | Style-1 vs style-2 parity, parameter inference |
| `test_flag_parsing.py` | 3 | `-i`, `-i50`, `-ic`, `-ic200`, no flag, edge cases |
| `test_compression.py` | 2 | Size reduction verification, idempotency |

### Test Command
```bash
python3 -m pytest tests/ -v
```

## Architecture Improvements

### Adopt Python `ast` Module for Python Parsing
- Zero additional dependencies
- Handles all edge cases regex misses (multi-line signatures with parentheses in strings)
- JS/TS/Shell continue using regex
- Effort: 3-4 hours

### Implement Atomic Writes
```python
import tempfile
tmp_fd, tmp_path = tempfile.mkstemp(dir=output_path.parent, suffix='.tmp')
os.write(tmp_fd, json.dumps(index).encode())
os.close(tmp_fd)
os.replace(tmp_path, str(output_path))  # Atomic on POSIX
```

### Smart Stop Hook
Reuse `should_regenerate_index()` staleness check from `i_flag_hook.py` to skip unnecessary regeneration work at session end.

## Implementation Roadmap

### Phase 1: Day 1 — Critical Security
- [ ] Remove hardcoded IPs and SSH commands (C-1)
- [ ] Validate `.python_cmd` (C-2)
- [ ] Remove LAN probing (H-1)
- [ ] Replace `os.chdir()` (H-2)

### Phase 2: Day 2 — Quick Wins
- [ ] Replace bare `except:` blocks (M-2)
- [ ] Delete dead code (Q-1)
- [ ] Extract shell duplication (Q-2)
- [ ] Add symlink protection for file writes (M-1)

### Phase 3: Week 2 — Quality & Testability
- [ ] Decompose `copy_to_clipboard` (Q-4)
- [ ] Add initial test suite (Q-3)
- [ ] Implement atomic writes (H-4)

### Phase 4: Month 2 — Architecture
- [ ] Parser registry (Q-6)
- [ ] TypedDict schema (Q-5)
- [ ] Python `ast` module adoption
- [ ] Smart stop hook
- [ ] Shared utilities extraction
