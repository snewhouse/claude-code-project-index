# Project Index Workflow Integration — Tasks (HTP)

## Milestone 1: Foundation (MCP Fix + Registration + SessionStart Rule)
- Status: COMPLETE
- Dependencies: None
- Complexity: 35%
- Acceptance Criteria: MCP server doesn't crash without index; registered at user scope; SessionStart rule suggests /index; 135 tests pass

### Step 1.1: Fix mcp_server.py for graceful degradation
- Status: COMPLETE
- Files: `scripts/mcp_server.py`
- Action: Replace eager `find_index()` at startup with lazy `_get_engine()` per-tool-call. Each tool returns helpful JSON error when no index.
- Result Log:
  ✅ COMPLETE 2026-03-17 14:45
  **Output**: Rewrote mcp_server.py — `find_index()` now returns `None` instead of raising. Added `_get_engine()` lazy-loader with caching. All 6 tools check engine availability and return `NO_INDEX_MSG` JSON when unavailable.
  **Artifacts**: `scripts/mcp_server.py` (rewritten)

### Step 1.2: Add MCP server instructions for Tool Search
- Status: COMPLETE
- Files: `scripts/mcp_server.py`
- Action: Add descriptive server instructions to FastMCP constructor so Tool Search can discover tools by relevance.
- Result Log:
  ✅ COMPLETE 2026-03-17 14:45
  **Output**: Added `SERVER_INSTRUCTIONS` string and passed as `instructions=SERVER_INSTRUCTIONS` to `FastMCP()` constructor. Describes all 6 tools and their use cases.

### Step 1.3: Write tests for graceful degradation
- Status: COMPLETE
- Files: `tests/test_mcp_server.py` (new)
- Action: Test that create_mcp_server() works when no PROJECT_INDEX.json exists; test tool responses with and without index.
- Result Log:
  ✅ COMPLETE 2026-03-17 14:46
  **Output**: Created 8 tests covering: find_index returns None/Path, _get_engine returns None/engine, engine caching, create_mcp_server succeeds without index, NO_INDEX_MSG validity, SERVER_INSTRUCTIONS presence. All 8 pass.
  **Artifacts**: `tests/test_mcp_server.py` (new, 8 tests)

### Step 1.4: Run full test suite
- Status: COMPLETE
- Action: `python3 -m pytest tests/ -v` — all 135+ tests pass
- Result Log:
  ✅ COMPLETE 2026-03-17 14:47
  **Output**: 143 tests passed in 1.00s (135 original + 8 new MCP server tests). Zero failures.

### Step 1.5: Update install.sh with MCP registration
- Status: COMPLETE
- Files: `install.sh`
- Action: Add `claude mcp add --transport stdio --scope user project-index -- python3 ~/.claude-code-project-index/scripts/mcp_server.py` to installer. Include idempotency check (skip if already registered).
- Result Log:
  ✅ COMPLETE 2026-03-17 14:46
  **Output**: Added MCP registration section to install.sh with 3-tier logic: (1) skip if already registered, (2) register if fastmcp installed, (3) print manual instructions otherwise. Checks for `claude` CLI availability.
  **Artifacts**: `install.sh` (modified)

### Step 1.6: Create SessionStart rule
- Status: COMPLETE
- Files: `~/.claude/rules/project-index-awareness.md` (new)
- Action: Auto-loaded rule that checks for PROJECT_INDEX.json; suggests /index if missing. Keep concise (<50 lines).
- Result Log:
  ✅ COMPLETE 2026-03-17 14:46
  **Output**: Created 10-line rule file. Checks for PROJECT_INDEX.json presence, describes MCP tools when present, suggests `/index` when missing. Concise and non-intrusive.
  **Artifacts**: `~/.claude/rules/project-index-awareness.md` (new)

### Step 1.7: Commit and push M1
- Status: COMPLETE
- Action: `git add` changed files, commit with conventional message, push
- Result Log:
  ✅ COMPLETE 2026-03-17 14:48
  **Output**: Commit 8fcf408 — 4 files changed, 204 insertions, 16 deletions. Pushed to origin/main.

---

## Milestone 2: Hub Skill (code-intelligence-index)
- Status: ACTIVE
- Dependencies: Milestone 1
- Complexity: 50%
- Acceptance Criteria: Skill exists, is invocable, documents freshness checks, query patterns, fallback matrix, and integration patterns

### Step 2.1: Create skill directory and SKILL.md
- Status: COMPLETE
- Files: `~/.claude/skills/code-intelligence-index/SKILL.md` (new)
- Action: Write the hub skill with sections: When to Use, Freshness Check Protocol, Query Method Guide, Fallback Matrix, Integration Patterns for Consuming Skills
- Result Log:
  ✅ COMPLETE 2026-03-17 14:52
  **Output**: Created skill with 5 sections: When to Use, Freshness Check Protocol, Query Method Guide, Fallback Matrix, Integration Patterns. ~120 lines, well under 300-line budget.
  **Artifacts**: `~/.claude/skills/code-intelligence-index/SKILL.md` (new)

### Step 2.2: Write freshness check protocol section
- Status: COMPLETE
- Files: Same as 2.1
- Action: Document how to check `_meta.files_hash` vs current `calculate_files_hash()`, age check (<24h), and when to suggest regeneration
- Result Log:
  ✅ COMPLETE 2026-03-17 14:52
  **Output**: Documented 3-tier freshness check: existence → age (<24h TTL) → hash comparison. Includes quick check pattern for consuming skills.

### Step 2.3: Write query method guide section
- Status: COMPLETE
- Files: Same as 2.1
- Action: Map each workflow question to the right QueryEngine method with examples. Include MCP tool names and CLI equivalents.
- Result Log:
  ✅ COMPLETE 2026-03-17 14:52
  **Output**: Created MCP tools table (6 tools with examples) and CLI equivalents section. Also documented direct JSON access keys for lightweight queries.

### Step 2.4: Write fallback matrix section
- Status: COMPLETE
- Files: Same as 2.1
- Action: Document: index exists + fresh → use QueryEngine; index exists + stale → use but warn; no index → fall back to Grep/sg with suggestion to run /index
- Result Log:
  ✅ COMPLETE 2026-03-17 14:52
  **Output**: Created 5-row fallback matrix covering: fresh, stale, hash mismatch, no index + tool available, no index + no tool. Key rule: "Never block on missing index."

### Step 2.5: Test skill invocation
- Status: COMPLETE
- Action: Verify `Skill(code-intelligence-index)` loads correctly in a new session
- Result Log:
  ✅ COMPLETE 2026-03-17 14:53
  **Output**: Verified skill appears in available skills list as `code-intelligence-index` with correct description. Skill is discoverable by the system.

### Step 2.6: Commit and push M2
- Status: PENDING
- Action: Commit skill file, push
- Result Log:

---

## Milestone 3: Deep Skill Integration
- Status: PENDING
- Dependencies: Milestone 2
- Complexity: 65%
- Acceptance Criteria: 4 skills/commands updated; each uses QueryEngine when index available; graceful degradation preserved; no breaking changes

### Step 3.1: Update system-mapping — Point 1 (Architecture)
- Status: PENDING
- Files: `~/.claude/skills/system-mapping/SKILL.md`
- Action: Add "Index-enhanced" section to Point 1. Use `file_summary` + `dir_purposes` + `tree` from index. Preserve original Grep/sg as fallback.
- Result Log:

### Step 3.2: Update system-mapping — Point 2 (Execution Flow)
- Status: PENDING
- Files: Same as 3.1
- Action: Add `who_calls(target, depth=3)` for call chain tracing. Preserve sg fallback.
- Result Log:

### Step 3.3: Update system-mapping — Point 4 (Dependencies)
- Status: PENDING
- Files: Same as 3.1
- Action: Add `dependency_chain(file, depth=5)` for forward deps. Keep Grep for reverse deps.
- Result Log:

### Step 3.4: Update impact-analysis — all 5 checks
- Status: PENDING
- Files: `~/.claude/skills/impact-analysis/SKILL.md`
- Action: Add "Index-Enhanced Analysis" section with QueryEngine method for each check. Update Quick Reference table. Preserve fallback.
- Result Log:

### Step 3.5: Update ultraplan — Phase 1 context gathering
- Status: PENDING
- Files: `~/.claude/commands/ultraplan.md`
- Action: Add index check to Phase 1 Step 1.2. If PROJECT_INDEX.json exists, include structural summary. If missing, note suggestion.
- Result Log:

### Step 3.6: Update codebase-deep-dive — Phase 2 bootstrap
- Status: PENDING
- Files: `~/.claude/commands/codebase-deep-dive.md`
- Action: Add index-awareness preamble to Phase 2 Agent 1 prompt. Bootstrap structural analysis from index when available.
- Result Log:

### Step 3.7: Verify all skills degrade gracefully without index
- Status: PENDING
- Action: In a project without PROJECT_INDEX.json, invoke each modified skill and verify identical behavior to pre-modification.
- Result Log:

### Step 3.8: Commit and push M3
- Status: PENDING
- Action: Commit all skill/command changes, push
- Result Log:

---

## Milestone 4: AA-MA Integration + Polish
- Status: PENDING
- Dependencies: Milestone 3
- Complexity: 45%
- Acceptance Criteria: AA-MA execution uses index; end-to-end test passes; all committed and pushed

### Step 4.1: Add blast_radius advisory to execute-aa-ma-milestone
- Status: PENDING
- Files: `~/.claude/commands/execute-aa-ma-milestone.md`
- Action: Add advisory step: before writing files, check blast_radius if index available. Display warning for high-impact changes. Never blocking.
- Result Log:

### Step 4.2: Add index-derived reference.md guidance
- Status: PENDING
- Files: `~/.claude/commands/ultraplan.md` (Phase 5 section)
- Action: When populating reference.md, include guidance to extract structural facts from index: file paths, entry points, dependencies, symbol importance.
- Result Log:

### Step 4.3: End-to-end verification
- Status: PENDING
- Action: In this repo (which has PROJECT_INDEX.json): invoke system-mapping, verify index-enhanced output. Invoke impact-analysis on a symbol, verify transitive callers. Check MCP tools via `/mcp`.
- Result Log:

### Step 4.4: Update design doc with deviations
- Status: PENDING
- Files: `docs/plans/2026-03-17-project-index-workflow-integration-design.md`
- Action: If any implementation deviated from design, document what changed and why.
- Result Log:

### Step 4.5: Final commit and push
- Status: PENDING
- Action: Commit all remaining changes, push. Update provenance log.
- Result Log:

### Step 4.6: Sync AA-MA artifacts
- Status: PENDING
- Action: Mark all milestones COMPLETE in tasks.md. Final provenance entry. Commit and push AA-MA files.
- Result Log:
