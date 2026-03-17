# Project Index Workflow Integration — Context Log

## 2026-03-17 Initial Context (Brainstorm Session)

**Feature Request:** Integrate claude-code-project-index into the skill ecosystem, AA-MA workflows, and session awareness. Make QueryEngine capabilities (blast_radius, who_calls, dead_code, etc.) a first-class citizen across all major workflows.

**Key Decisions:**

1. **Always offer index creation** — SessionStart rule checks for PROJECT_INDEX.json and suggests `/index` if missing
2. **New hub skill architecture** — `code-intelligence-index` as single skill that other skills call (vs inline duplication)
3. **Deep integration** — Rewrite data-gathering sections of 4 skills, not just hints
4. **MCP with graceful degradation** — Fix server to handle missing index, register at user scope
5. **MCP goes in ~/.claude.json** — NOT settings.json (corrected assumption via web research of official Claude Code docs)
6. **AA-MA plan format** — Full milestone-based plan for structured tracking

**Research Findings:**

- system-mapping's Points 1, 2, 4 map directly to QueryEngine methods
- impact-analysis's 5-point checklist has 4/5 checks replaceable by QueryEngine (side effects remains manual)
- ultraplan Phase 1 has no index awareness currently
- codebase-deep-dive Phase 2 (structural analysis) would benefit most from bootstrapping
- Existing research doc (`10-workflow-integration-research.md`) already proposed the skill integration matrix
- MCP config verified: `claude mcp add --transport stdio --scope user` puts servers in `~/.claude.json`
- Current MCP server crashes with FileNotFoundError when no index — must fix before global registration

## 2026-03-17 Milestone 1 Completion: Foundation
- Status: COMPLETE
- Key outcome: MCP server now gracefully degrades without index; install.sh registers MCP at user scope; SessionStart rule created
- Artifacts: `scripts/mcp_server.py` (rewritten), `tests/test_mcp_server.py` (new, 8 tests), `install.sh` (MCP registration added), `~/.claude/rules/project-index-awareness.md` (new)
- Tests: 143 passing (135 original + 8 new)
- Decisions: Used `Path | None` return type in mcp_server.py (acceptable since fastmcp requires Python 3.10+). Kept SessionStart rule concise at 10 lines to avoid noise.

**Critical Correction:**
Initial assumption was MCP servers go in `settings.json`. User challenged this. Web research of https://code.claude.com/docs/en/mcp confirmed: MCP servers stored in `~/.claude.json` (user/local scope) or `.mcp.json` (project scope). `settings.json` only controls permissions/allowlists.

## 2026-03-17 Milestone 2 Completion: Hub Skill
- Status: COMPLETE
- Key outcome: `code-intelligence-index` skill created at `~/.claude/skills/code-intelligence-index/SKILL.md`
- Artifacts: Hub skill with 5 sections (When to Use, Freshness Check, Query Guide, Fallback Matrix, Integration Patterns)
- Decision: Kept skill under 120 lines — well within 300-line budget. Focus on patterns, not implementation detail.

## 2026-03-17 Milestone 3 Completion: Deep Skill Integration
- Status: COMPLETE
- Key outcome: 4 skills/commands updated with index-enhanced sections
- Artifacts: system-mapping (Points 1,2,4), impact-analysis (4/5 checks), ultraplan (Phase 1), codebase-deep-dive (Phase 2)
- Decision: All modifications are additive "Index-enhanced" blocks placed BEFORE existing fallback sections. No original content removed.

## 2026-03-17 Milestone 4 Completion: AA-MA Integration + Polish
- Status: COMPLETE
- Key outcome: AA-MA execution uses blast_radius advisory; ultraplan Phase 5 extracts structural facts; end-to-end verification passed
- Artifacts: execute-aa-ma-milestone.md (blast_radius pre-check), ultraplan.md (reference.md guidance), design doc (deviations section)
- Tests: 143 passing
- Scope reductions: Post-write dead_code diff and milestone completion dead_code gate not implemented (low value-to-complexity ratio)
- End-to-end verified: INDEX has 32 files, 126 graph edges, 50 symbol_importance entries; all CLI queries functional
