# Project Index Workflow Integration — Plan

**Objective:** Integrate claude-code-project-index into Claude Code's skill ecosystem, AA-MA workflows, and session awareness so every session has structural code intelligence available.
**Owner:** Stephen Newhouse + Claude Code
**Created:** 2026-03-17
**Last Updated:** 2026-03-17
**Design Doc:** `docs/plans/2026-03-17-project-index-workflow-integration-design.md`

## Executive Summary

This plan integrates the PROJECT_INDEX.json system into 4 core Claude Code workflows (system-mapping, impact-analysis, ultraplan, codebase-deep-dive) by creating a hub skill (`code-intelligence-index`), fixing the MCP server for graceful degradation, registering it globally via `claude mcp add --scope user`, and adding a SessionStart awareness rule. The result: every session automatically knows about and can use structural code intelligence.

## Milestones

### Milestone 1: Foundation (MCP Fix + Registration + SessionStart Rule)
**Goal:** Make index tools globally available and sessions index-aware
**Complexity:** 35%
**Acceptance Criteria:**
1. MCP server starts without crashing when no PROJECT_INDEX.json exists
2. MCP tools return helpful guidance messages when no index
3. MCP server registered at user scope in `~/.claude.json`
4. `install.sh` includes MCP registration step
5. SessionStart rule detects index presence and suggests `/index` when missing
6. All 135 existing tests still pass

**Risks:**
1. MCP registration command syntax may differ across Claude Code versions → Mitigation: test with `claude mcp list` after registration
2. SessionStart rule may be too noisy → Mitigation: only suggest once per project, not every session
3. Lazy-loading QueryEngine may add latency to first tool call → Mitigation: negligible for JSON.load on <1MB file

**Rollback:** Remove MCP registration with `claude mcp remove project-index`; delete rule file

### Milestone 2: Hub Skill (code-intelligence-index)
**Goal:** Create the central skill that wraps QueryEngine with workflow-aware logic
**Complexity:** 50%
**Acceptance Criteria:**
1. Skill file exists at `~/.claude/skills/code-intelligence-index/SKILL.md`
2. Skill documents: freshness check protocol, query method guide, fallback matrix, integration patterns
3. Skill correctly maps each QueryEngine method to its workflow use case
4. Skill provides clear guidance for when index is missing/stale vs when to use Grep/sg fallback
5. Skill is invocable via `Skill(code-intelligence-index)` in any session

**Risks:**
1. Skill may be too long/complex for token efficiency → Mitigation: keep under 300 lines; use sections with clear skip-to guidance
2. Freshness check protocol may be too strict (forces regeneration too often) → Mitigation: 24h TTL with hash-based override
3. Integration patterns may not match all skill invocation contexts → Mitigation: test with each consuming skill

**Rollback:** Delete skill directory; consuming skills fall back to Grep/sg

### Milestone 3: Deep Skill Integration
**Goal:** Update system-mapping, impact-analysis, ultraplan, and codebase-deep-dive to use the hub skill
**Complexity:** 65%
**Acceptance Criteria:**
1. `system-mapping` Points 1, 2, 4 use QueryEngine when index available; Grep fallback preserved
2. `impact-analysis` all 5 checks map to QueryEngine methods with structured output
3. `ultraplan` Phase 1 checks for index and includes structural context
4. `codebase-deep-dive` Phase 2 Agent 1 bootstraps from index when available
5. All skills gracefully degrade when no index exists (identical behavior to today)
6. No breaking changes to existing skill behavior for projects without an index

**Risks:**
1. Large blast radius — 4 skill files modified → Mitigation: each skill update is independent; test individually
2. Skills may produce different output quality with/without index → Mitigation: document that index-enhanced mode is additive, not replacement
3. Ultraplan Phase 1 changes may interfere with existing clarification flow → Mitigation: add index check as silent context, not a new user prompt

**Rollback:** Revert each skill file independently from git

### Milestone 4: AA-MA Integration + Polish
**Goal:** Wire index intelligence into AA-MA execution workflows and verify end-to-end
**Complexity:** 45%
**Acceptance Criteria:**
1. During `/ultraplan` Phase 3, research agents can query index via MCP tools
2. During `/execute-aa-ma-milestone`, blast_radius check warns for high-impact file writes
3. `reference.md` population guidance includes index-derived structural facts
4. End-to-end test: new project → `/index` → system-mapping uses index → impact-analysis uses index
5. Design doc updated with any implementation deviations
6. All changes committed and pushed

**Risks:**
1. AA-MA execution commands are complex — changes may break milestone flow → Mitigation: modify guidance only, not control flow
2. blast_radius hook during execution may slow down writes → Mitigation: advisory only, never blocking
3. End-to-end test requires a fresh project context → Mitigation: use this repo as the test project

**Rollback:** Revert AA-MA command files; remove blast_radius advisory

---

## Dependencies & Assumptions

**Dependencies:**
- `claude mcp add` CLI available (Claude Code v2.1+)
- Python 3.8+ with stdlib (no new deps)
- Existing PROJECT_INDEX.json format unchanged
- `~/.claude/skills/` directory writable

**Assumptions:**
- MCP server with user scope is inherited by all projects (verified via docs)
- Tool Search auto-discovers MCP tools when context budget allows
- Skills can reference other skills via `Skill(name)` invocation
- SessionStart rules in `~/.claude/rules/` auto-load every session

## Effort Estimate

| Milestone | Effort | Sessions |
|-----------|--------|----------|
| M1: Foundation | 30-45 min | 1 |
| M2: Hub Skill | 45-60 min | 1 |
| M3: Deep Integration | 60-90 min | 1-2 |
| M4: AA-MA + Polish | 30-45 min | 1 |
| **Total** | **~3-4 hours** | **3-4 sessions** |

## Next Action

Begin Milestone 1: Fix `scripts/mcp_server.py` for graceful degradation, then register via CLI.
