# ADR-004: Progressive Compression Pipeline

**Status:** Accepted
**Date:** 2026-03-17
**Context:** How to fit the index within Claude's context window for projects of any size

## Decision

Apply a 5-step compression ladder that progressively sheds less important data until the index fits the target size. Each step checks the current size and returns early if within budget.

## Rationale

- Projects range from 10 files to 50,000+ files — a fixed format cannot serve all
- Lossy compression acceptable because Claude needs spatial awareness, not byte-perfect data
- Progressive approach preserves the most architecturally important information longest
- Function signatures and call graph survive until the emergency step

## Implementation

`compress_if_needed()` in `scripts/project_index.py` (approximately line 540):

| Step | Action | What's Lost |
|------|--------|-------------|
| 1 | Truncate `tree` to 10 items | Deep directory structure |
| 2 | Truncate docstrings to 40 chars | Documentation detail |
| 3 | Strip docstrings entirely | All inline documentation |
| 4 | Delete `KEY_DOCS` (documentation map) | Markdown section headers |
| 5 | Emergency: keep top-N files by importance score | Least-important files dropped |

Importance scoring (step 5): `importance = len(file_data[1])` (function count) + 5 if classes present. Files with many functions are preserved; files with few functions and no classes are dropped first.

Target size comes from `INDEX_TARGET_SIZE_K` env var, converted to bytes: `target_size_k * 1000 * 4` (4 chars per token approximation).

Constants: `MAX_INDEX_SIZE = 1MB` (default when no env var), `MAX_FILES = 10000` hard cap.

## Consequences

- Large projects lose docstrings and tree depth but retain function signatures and call graph
- Emergency truncation is file-level (all-or-nothing per file), not function-level
- The 4-chars-per-token approximation is model-agnostic and may overshoot or undershoot

## Verified Against

- `scripts/project_index.py` — compress_if_needed() uses KEY_FILES, KEY_DOCS constants
- `scripts/project_index.py:36-38` — MAX_FILES=10000, MAX_INDEX_SIZE=1MB, MAX_TREE_DEPTH=5
- `scripts/project_index.py:723-726` — target_size_bytes = target_size_k * 1000 * 4
