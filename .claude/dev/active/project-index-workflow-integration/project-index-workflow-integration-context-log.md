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
