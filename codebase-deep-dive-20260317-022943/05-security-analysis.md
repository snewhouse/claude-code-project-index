# Security Analysis

**Risk Level: HIGH** (2 critical, 4 high, 5 medium, 6 low findings)

## Executive Summary

This is a local developer tool with no network-facing services or user authentication. The primary attack surface is the hook execution environment (Claude Code runs hooks on every prompt/session). The two critical findings involve hardcoded third-party IP addresses with shell-injectable SSH commands, and unvalidated execution of file content as a Python interpreter path. The high-risk findings involve symlink-attackable file writes, global CWD mutation, and unauthenticated LAN probing. All findings are calibrated to a local tool threat model.

## Vulnerability Assessment

### Critical Issues

**C-1: Hardcoded third-party IPs + shell-injectable SSH command construction**
- **Location:** `i_flag_hook.py:283, 478-483, 492, 681`
- **Risk:** The clipboard fallback constructs an SSH command with `os.environ.get('USER', 'user')` interpolated without sanitization, targeting hardcoded IP `10.211.55.4` (a Parallels VM address belonging to the original author). If `USER` contains shell metacharacters, this enables remote code execution. Any user triggers outbound SSH to an address they don't own.
- **Mitigation:** Remove all hardcoded third-party IPs and the `tmux run-shell` SSH construction entirely. Clipboard fallback for SSH should be local file write only.

**C-2: Unvalidated `.python_cmd` file content used as executable path**
- **Location:** `run_python.sh:9-10`, `i_flag_hook.py:190-193`, `stop_hook.py:44-46`
- **Risk:** All three read `~/.claude-code-project-index/.python_cmd` and use its content as an executable path with no validation. If an attacker can write to this file (symlink attack, compromised package), they control the executable that runs on every Claude session.
- **Mitigation:** Validate path is absolute, exists, is executable, and matches `python*`. Add integrity check and `chmod 600`.

### High-Risk Issues

**H-1: Symlink-attackable write of sensitive content to `cwd()`**
- **Location:** `i_flag_hook.py:388-390, 403-405, 557-560`
- **Risk:** `.clipboard_content.txt` written to `Path.cwd()` without symlink check. Content includes full PROJECT_INDEX.json and user's prompt. Symlink to any writable location causes overwrite.
- **Mitigation:** Use fixed cache directory with `O_NOFOLLOW`. Check `path.is_symlink()` before write.

**H-2: `os.chdir()` globally mutates process CWD**
- **Location:** `stop_hook.py:63`
- **Risk:** If a malicious `PROJECT_INDEX.json` exists higher in the directory tree (e.g. `$HOME`), the hook indexes sensitive home directory content.
- **Mitigation:** Pass `cwd=str(project_root)` to `subprocess.run` instead.

**H-3: Unauthenticated LAN probes with clipboard content exfiltration**
- **Location:** `i_flag_hook.py:282-292, 380`
- **Risk:** Probes 3 hardcoded LAN addresses (`10.211.55.2`, `10.211.55.1`, `192.168.1.1` — typically a gateway router). If any responds on the daemon port, receives full clipboard content (project code + prompts) via plaintext.
- **Mitigation:** Require explicit user-configured host. Never probe speculative LAN addresses.

**H-4: Unguarded `rm -rf` in non-interactive install**
- **Location:** `install.sh:89-90, 115-116`
- **Risk:** In curl-pipe mode, silently removes `$INSTALL_DIR`. Unquoted glob copy with `|| true` swallows all failures.
- **Mitigation:** Validate `INSTALL_DIR` starts with `$HOME/`. Quote globs. Remove `|| true` from security-relevant operations.

### Medium-Risk Issues

| ID | Location | Issue | Mitigation |
|----|----------|-------|------------|
| M-1 | i_flag_hook.py:60,133; index_utils.py:1295 | Bare `except: pass` hides security failures; gitignore parse errors cause secrets to be indexed | Replace with `except Exception:` + logging |
| M-2 | project_index.py:741; i_flag_hook.py:240-241 | Non-atomic JSON write; read-modify-write race between concurrent hook invocations | Write to temp file, `os.replace()`. Add `fcntl.flock()` |
| M-3 | i_flag_hook.py:278-279, 303-304 | `sys.path` mutated and never restored on VM Bridge import failure | Save/restore `sys.path` or use `importlib.util` |
| M-4 | i_flag_hook.py:570-571 | No length limit on prompt from stdin — OOM with huge prompts | Add `prompt = prompt[:100_000]` soft limit |
| M-5 | find_python.sh:71, 151 | PATH hijacking: candidate binaries executed unconditionally during install | Validate candidate paths against trusted prefixes |

### Low-Risk Issues

| ID | Location | Issue |
|----|----------|-------|
| L-1 | install.sh:158 | `.python_cmd` world-readable (644); should be 600 |
| L-2 | i_flag_hook.py:199-206 | Timed-out subprocess not explicitly killed |
| L-3 | i_flag_hook.py:492, 681 | `USER` env var leaked in output |
| L-4 | project_index.py:165-170 | Fallback `rglob` may follow symlinks; potential infinite traversal |
| L-5 | run_python.sh:23 | Python command from file not validated as single-word absolute path |
| L-6 | install.sh:133 | `git clone` HEAD with no commit hash pinning (supply chain risk) |

## OWASP Top 10 Check

| Vulnerability | Status | Findings |
|---------------|--------|----------|
| A01: Broken Access Control | N/A | No auth system |
| A02: Cryptographic Failures | N/A | No crypto used |
| A03: Injection | **FOUND** | C-1: Shell injection via `USER` env var in SSH command |
| A04: Insecure Design | **FOUND** | Hardcoded IPs, unvalidated executable paths |
| A05: Security Misconfiguration | **FOUND** | World-readable `.python_cmd`, bare excepts |
| A06: Vulnerable Components | Clean | No external dependencies |
| A07: Auth Failures | N/A | No auth system |
| A08: Data Integrity | **FOUND** | Non-atomic writes, no supply chain pinning |
| A09: Logging/Monitoring | Minimal | Errors printed to stderr only |
| A10: SSRF | **FOUND** | H-3: Unauthenticated outbound LAN probes |

## Security Strengths

- **No `shell=True`** — All subprocess calls use explicit command lists, preventing command injection in the primary execution paths
- **Zero external dependencies** — No supply chain risk from pip packages
- **Timeout limits** on all subprocess calls (5s, 10s, 30s)
- **`MAX_FILES` and `MAX_INDEX_SIZE` limits** prevent resource exhaustion
- **Git-based file discovery** respects `.gitignore` (when gitignore parsing works — see M-1)

## Immediate Actions Required

1. **Remove hardcoded IPs and SSH commands** (C-1) — Only finding affecting external hosts
2. **Validate `.python_cmd` before execution** (C-2) — Add path validation + `chmod 600`
3. **Remove unauthenticated LAN probing** (H-3) — Require explicit opt-in configuration
4. **Replace `os.chdir()` with `cwd=` parameter** (H-2) — One-line fix
5. **Add symlink check before file writes** (H-1) — Low effort, high impact
