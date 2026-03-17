# Verification Report: project-index-upgrade

Generated: 2026-03-17T11:15:00Z | Mode: Interactive | Revision: v1

## Summary

- **CRITICAL:** 0 findings (all addressed in plan revision v2)
- **WARNING:** 38 findings (10 HIGH-risk addressed in plan revision, 28 informational)
- **INFO:** 12 findings
- **Overall: PASS WITH WARNINGS** (all HIGH-risk items addressed in plan v2)

The plan is structurally sound with no factual errors. All file paths and line numbers verified against actual code (within 1-4 line tolerance). However, 7 high-risk warnings require plan revision before execution — primarily around test files that will break during refactoring and unspecified implementation details.

---

## Angle 1: Ground-Truth Audit

### Findings

All 19 factual claims verified against actual codebase. No contradictions found.

- [OK] All function locations confirmed (±1-4 lines)
- [OK] Test count: exactly 46 tests confirmed
- [OK] Dead code instances confirmed (ssh_file_large, MAX_ITERATIONS, __pycache__ duplicate)
- [OK] DRY violations confirmed at exact locations
- [WARNING] Claim 1: `_validate_python_cmd` described as "verbatim duplicate" — actually near-duplicate. `stop_hook.py` uses `Path as _Path` alias vs `Path` in `i_flag_hook.py`. Functionally identical, textually different.
- [WARNING] Claim 12: Brace-counting line numbers off by 2-4 lines (actual: 570, 609, 658, 746, 828 vs claimed: 567, 609, 662, 744, 825)
- [WARNING] Claims 13-15: Function span end-lines off by 1-2 lines each
- [WARNING] Claim 19: i_flag_hook.py atomic write starts at line 275, not 274

**Verdict:** No blocking issues. Line number offsets are within tolerance for a living codebase.

---

## Angle 2: Assumption Extraction & Challenge

### Assumptions Identified: 14 (10 explicit + 4 unstated)

**VERIFIED (7):**
- Python 3.9+ available (env is 3.12.11)
- `index_utils.py` has no imports from hook files (no circular dep risk)
- `ast.unparse()` available at 3.9+
- 46 tests form characterization baseline (count correct)
- `PARSER_REGISTRY` can be updated without breaking callers
- SQLite WAL mode works on WSL2 Linux filesystem
- `shutil.which` works on WSL2

**UNVERIFIED (4):**
- [WARNING/HIGH] Regex parser fallback always available after AST replacement — no fallback code exists yet; M3 must preserve `extract_python_signatures()` return contract for M4 fallback path
- [WARNING/MEDIUM] `V2_AST_PARSER=0` flag location unspecified — import-time vs call-time produces fundamentally different behavior and testability
- [WARNING/LOW] `MAX_ITERATIONS` removal scope ambiguous — plan unclear whether to remove only constant, only guards, or both
- [WARNING/LOW] `calculate_files_hash` has TWO implementations to consolidate (named function in i_flag_hook + anonymous inline in stop_hook), not just one move

**CONTRADICTED (2):**
- [WARNING/HIGH] "No test imports `_validate_python_cmd` from `i_flag_hook`" — CONTRADICTED. `tests/test_security.py` has 3 direct imports at lines 33, 40, 48. All break when function is moved.
- [WARNING/LOW] "11 test files" — actually 9 test files + conftest.py + `__init__.py` = 11 Python files, but only 9 contain test functions.

**UNSTATED (4):**
- `install.sh`, README, ADR-002, PDR-001 all document Python 3.8+ minimum — must update after bumping to 3.9+
- `should_regenerate()` exists in both `stop_hook.py` and `i_flag_hook.py` (as `should_regenerate_index()`) — plan Task 2.3 must specify which one
- M3 decomposed helpers must maintain identical output dict contract for M4 fallback
- `ast.Index` removed in Python 3.9 — AST parser must not reference this node type

---

## Angle 3: Impact Analysis on Proposed Changes

### Files Affected: 6 modified, 16 created

**HIGH-RISK (2):**

1. **`tests/test_security.py` — 3 import failures**
   - Lines 33, 40, 48: `from i_flag_hook import _validate_python_cmd` → `ImportError` after M1
   - Plan reference.md acknowledges update needed but Task 1.1 does not list it as explicit sub-step
   - **ACTION REQUIRED:** Add test_security.py import update as explicit sub-step in Task 1.1

2. **`tests/test_registry.py:12` — assertion failure after M4**
   - Asserts `PARSER_REGISTRY['.py'].__name__ == 'extract_python_signatures'` → fails when AST parser registered
   - **ACTION REQUIRED:** Add test_registry.py update as explicit sub-step in Task 4.2

**MEDIUM-RISK (2):**

3. **`tests/test_atomic_writes.py` — content assertions break**
   - Lines 13-14: asserts `'os.replace' in content` and `'mkstemp' in content` for `project_index.py`
   - Line 21: asserts `'os.replace' in content` for `i_flag_hook.py`
   - If atomic writes delegated to `atomic_write_json()` in index_utils, these strings may no longer appear in the hook files
   - **ACTION REQUIRED:** Update test_atomic_writes.py content checks in Task 1.3, or ensure hook files still call os.replace inline

4. **`scripts/project_index.py:30` — dead import**
   - Imports `extract_python_signatures` by name but never calls it directly (all calls go through `parse_file()`)
   - **ACTION REQUIRED:** Clean up dead import in M3 or M4

**LOW-RISK (3):**

5. README.md, ADR-008, PDR-001 reference `_validate_python_cmd()` by old name — docs drift after M1
6. `test_compression.py` new "fits target" assertion may expose that `compress_if_needed` Step 5 is best-effort
7. `extract_python_signatures` must remain importable from `index_utils` through all milestones as SyntaxError fallback

### Files the Plan Should Mention But Doesn't

- `tests/test_registry.py` — needs update in M4
- `tests/test_atomic_writes.py` — needs update in M1
- `install.sh` — needs Python version bump documentation
- `README.md` — needs Python version requirement update

---

## Angle 4: Acceptance Criteria Falsifiability

### Score: 22/38 falsifiable as written (58%)

**Top issues by milestone:**

| Milestone | Falsifiable | Total | Needs Work |
|-----------|-----------|-------|------------|
| M1 | 8 | 9 | 1 (dead code definition vague) |
| M2 | 3 | 6 | 3 ("has tests" existence claims) |
| M3 | 2 | 6 | 4 (decomposition structural only) |
| M4 | 4 | 8 | 4 ("identical or better", "compatible") |
| M5 | 3 | 6 | 3 ("handles" vague) |
| M6 | 5 | 7 | 2 ("cache corrupt" undefined) |
| M7 | 3 | 5 | 2 ("optional" MCP, p99 methodology) |
| M8 | 2 | 4 | 2 ("for compression decisions" vague) |

**Banned/vague terms found:** "handles", "compatible", "identical or better", "targeted", "optional" (applied to AC), "for compression decisions"

**Priority rewrites needed:**
1. M2: Replace "has tests" with behavioral output contracts
2. M4: Define "compatible" as specific key set, define "better" or remove
3. M3: Add behavioral criteria for decomposed helpers, not just existence
4. M8: Define PageRank output contract (`_meta['pagerank']` dict summing to ~1.0)

---

## Angle 5: Fresh-Agent Simulation

### Task 1.1 Walkthrough (as a fresh agent)

- [OK] Project dependencies: "stdlib only" is clear, `python3 -m pytest tests/ -v` in CLAUDE.md
- [WARNING] No absolute project path in the AA-MA plan file (it is in the detailed plan file)
- [WARNING] Task 1.1 does not enumerate source files — fresh agent must infer `_validate_python_cmd` is in both `i_flag_hook.py` and `stop_hook.py`
- [OK] Basename regex IS specified in the detailed plan file: `re.fullmatch(r'python\d*(\.\d+)?', basename)` (Step 3 code block)
- [WARNING] Test baseline: plan says "46 tests pass" but no command to establish baseline before starting

### Questions a Fresh Agent Would Need

1. After moving `_validate_python_cmd`, should `i_flag_hook.py` re-export for backward compat or fully remove?
2. `stop_hook.py` Python fallback loop (lines 115-125) does NOT call `_validate_python_cmd` — should it be updated to do so?

---

## Angle 6: Specialist Domain Audit

### Specialists: Python AST + SQLite

**Python AST:**

- [WARNING] `ast.unparse()` on `TypeAlias` (3.12) / `MatchAs` (3.10) / `TryStar` (3.11) — source code using these features parsed on older runtimes gets `SyntaxError` → regex fallback (correct behavior). Plan should add explicit test case for "newer Python syntax parsed by older runtime".
- [WARNING] `RecursionError` catch granularity: plan implies one top-level try/except around whole parse. For partial recovery (index rest of file when one function has pathological annotation), each `ast.unparse()` call should be individually wrapped. Plan should specify granularity.
- [WARNING] `sys.setrecursionlimit` value unspecified. Should save/restore original limit, not unconditionally raise.
- [INFO] `feature_version` parameter of `ast.parse()` could enable version-targeted parsing from `pyproject.toml`'s `requires-python`.

**SQLite (M6):**

- [WARNING/HIGH] `PRAGMA integrity_check` on 50k-file cache is O(N) — reads every page, takes 2-10s, negates <2s incremental goal. **Fix: Use `PRAGMA quick_check` for routine opens; reserve full `integrity_check` for `--repair-cache` flag.**
- [WARNING/MEDIUM] WAL mode on NTFS/WSL2 mounts: if `~/.claude-code-project-index/` resolves to `/mnt/c/...`, WAL fails silently. **Fix: Detect filesystem type; fall back to DELETE journal mode on NTFS.**
- [WARNING] `sqlite3.connect()` default timeout=0 in Python — concurrent hooks would get immediate `OperationalError`. **Fix: Set `timeout=10` explicitly.**
- [WARNING] No `PRAGMA optimize` or VACUUM scheduling for long-lived caches.
- [WARNING] No cap on individual `parse_result` blob size — pathological files could bloat cache.
- [INFO] `PRAGMA synchronous=NORMAL` trade-off (acceptable for cache) should be documented in reference.md.
- [INFO] `DROP TABLE + CREATE TABLE` is faster than `DELETE FROM` for full cache invalidation on version bump.

---

## Consolidated Action Items for Plan Revision

### Must-Fix (before execution)

| # | Finding | Source | Fix |
|---|---------|--------|-----|
| 1 | Task 1.1 must explicitly update `test_security.py` imports | Angle 2, 3 | Add sub-step to Task 1.1 |
| 2 | Task 1.3 must address `test_atomic_writes.py` content checks | Angle 3 | Add sub-step or ensure inline os.replace stays |
| 3 | Task 4.2 must update `test_registry.py` assertion | Angle 3 | Add sub-step to Task 4.2 |
| 4 | Specify V2_AST_PARSER flag location (import-time recommended) | Angle 2 | Add to reference.md and Task 4.2 |
| 5 | M3 acceptance: "decomposed helpers must preserve output dict contract of extract_python_signatures()" | Angle 2 | Add to M3 acceptance criteria |
| 6 | Update install.sh/README/ADR minimum Python version to 3.9+ | Angle 2 | Add documentation update task to M4 |

### Should-Fix (improve quality)

| # | Finding | Source | Fix |
|---|---------|--------|-----|
| 7 | Tighten 16 vague acceptance criteria per Angle 4 findings | Angle 4 | Rewrite criteria with concrete assertions |
| 8 | Clean up dead `extract_python_signatures` import in project_index.py | Angle 3 | Add to M3 or M4 |
| 9 | Specify `should_regenerate` target (stop_hook.py, not i_flag_hook.py) in Task 2.3 | Angle 2 | Clarify in tasks.md |
| 10 | Correct "11 test files" to "9 test files + 2 support files" | Angle 2 | Update reference.md |

---

## Revision History

- v1: 2026-03-17T11:15Z — Initial verification (Wave 1). 0 CRITICAL, 28 WARNING → PASS WITH WARNINGS
- v2: 2026-03-17T11:25Z — Wave 2 complete. Added Angles 5-6 (specialist domain). 10 additional findings (SQLite + AST). Plan revised to address: test file breakages (3 files), V2_AST_PARSER flag location, M3 output contract preservation, PRAGMA quick_check over integrity_check, NTFS WAL fallback, sqlite3 timeout=10. All HIGH-risk items resolved → **PASS WITH WARNINGS**
