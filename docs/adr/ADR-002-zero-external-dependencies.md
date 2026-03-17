# ADR-002: Zero External Python Dependencies

**Status:** Accepted
**Date:** 2026-03-17
**Context:** Dependency management strategy for a tool installed to `~/.claude-code-project-index/`

## Decision

Use only Python stdlib modules. No pip packages required. `pyperclip` is optional (clipboard fallback position 4 of 5).

## Rationale

- No virtualenv, no pip install, no version conflicts with user's projects
- Install is a simple directory copy (`install.sh` uses `cp`, not pip)
- No supply chain risk — zero transitive dependencies
- Works on air-gapped systems after installation
- Python 3.8+ is the only version constraint

## Alternatives Considered

- **tree-sitter** (`pip install tree-sitter tree-sitter-languages`): Would provide 100% parsing accuracy for all languages. Rejected because it requires native compiled extensions, adding install complexity and platform-specific failures.
- **NetworkX** (`pip install networkx`): Would enable PageRank-based file importance ranking (like Aider). Rejected to maintain zero-dep constraint. Can be revisited in v2.

## Implementation

Stdlib modules used: `json`, `sys`, `os`, `re`, `subprocess`, `hashlib`, `tempfile`, `time`, `pathlib`, `datetime`, `fnmatch`, `typing`, `fcntl` (guarded import), `base64`.

## Consequences

- Parsers use regex instead of AST/tree-sitter (lower accuracy for edge cases)
- No graph algorithms beyond manual BFS (no PageRank ranking)
- Clipboard transport limited to subprocess-based tools + pyperclip optional fallback

## Verified Against

- `scripts/project_index.py:19-25` — all imports are stdlib
- `scripts/index_utils.py:7-10` — re, fnmatch, pathlib, typing only
- `scripts/i_flag_hook.py:7-16` — all stdlib except guarded fcntl
