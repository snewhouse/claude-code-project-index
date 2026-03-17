# Design: Project Index Workflow Integration

**Date:** 2026-03-17
**Status:** Approved
**Scope:** Integrate claude-code-project-index into Claude Code's skill ecosystem, AA-MA workflows, and session awareness

---

## Problem Statement

The project index system (`PROJECT_INDEX.json`) provides powerful structural intelligence — call graphs, dependency chains, blast radius analysis, dead code detection — but it's siloed behind the `-i` flag. Sessions don't know it exists. Skills that would benefit enormously (system-mapping, impact-analysis, ultraplan, codebase-deep-dive) still rely on slow Grep/sg-based analysis. AA-MA workflows have no automated structural awareness.

## Goals

1. **Session awareness**: Every Claude Code session knows whether a PROJECT_INDEX.json exists and offers to create one if missing
2. **Skill integration**: QueryEngine capabilities (who_calls, blast_radius, dead_code, dependency_chain) replace Grep-based analysis in 4 major skills
3. **MCP native tools**: Register the MCP server globally so Claude has structural query tools available without `-i` flags
4. **AA-MA integration**: Milestone planning, implementation, and completion workflows use index data
5. **Production skill**: A polished `code-intelligence-index` skill as the single hub that other skills call

## Non-Goals

- Converting claude-code-project-index into a full Claude Code plugin (deferred)
- Cross-project index federation (deferred)
- Real-time file watching / auto-regeneration (deferred)
- Modifying the index generation pipeline itself

---

## Architecture

```
                    Session Start
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
    rules/project-               MCP Server
    index-awareness.md           (user scope)
    "INDEX exists? ──┐           stdio transport
     Offer /index"   │           in ~/.claude.json
                     │                │
    ┌────────────────┼────────────────┤
    ▼                ▼                ▼
┌──────────┐  ┌───────────┐   ┌───────────┐
│ system-  │  │ impact-   │   │ ultraplan │
│ mapping  │  │ analysis  │   │ Phase 1   │
│ Points   │  │ 5-point   │   │ Context   │
│ 1,2,4    │  │ checklist │   │ Gathering │
└────┬─────┘  └─────┬─────┘   └─────┬─────┘
     │              │               │
     └──────────────┼───────────────┘
                    ▼
        ┌───────────────────┐
        │ Skill:            │
        │ code-intelligence │
        │ -index            │
        │                   │
        │ Checks freshness  │
        │ Calls QueryEngine │
        │ Falls back to     │
        │ Grep/sg if no idx │
        └─────────┬─────────┘
                  ▼
         PROJECT_INDEX.json
```

### Three Access Paths

| Path | Mechanism | When Used |
|------|-----------|-----------|
| **MCP tools** | `who_calls`, `blast_radius`, etc. as native Claude tools | Any time Claude needs structural info — automatic via Tool Search |
| **Skill invocation** | `Skill(code-intelligence-index)` called by other skills | Formal workflow integration with freshness checks and fallbacks |
| **CLI** | `python3 scripts/cli.py query <command>` via Bash | Direct user invocation or skill fallback |

---

## Component Design

### 1. MCP Server Fix (`scripts/mcp_server.py`)

**Current problem:** `find_index()` raises `FileNotFoundError` when no PROJECT_INDEX.json exists, crashing the MCP server at startup.

**Fix:** Lazy initialization. Don't load the index at startup. Load it on first tool call. If missing, return a helpful message:

```python
def _get_engine() -> QueryEngine:
    """Lazy-load QueryEngine. Returns None if no index."""
    try:
        index_path = find_index()
        return QueryEngine.from_file(index_path)
    except FileNotFoundError:
        return None

# Each tool checks:
@mcp.tool()
def who_calls(symbol: str, depth: int = 1) -> str:
    """Find all callers of a symbol. readOnlyHint: true"""
    qe = _get_engine()
    if qe is None:
        return json.dumps({
            "error": "No PROJECT_INDEX.json found",
            "hint": "Run /index or python3 ~/.claude-code-project-index/scripts/project_index.py to create one"
        })
    return json.dumps(qe.who_calls(symbol, depth=depth), indent=2)
```

**MCP server instructions** (for Tool Search):
```
"Code intelligence for the current project. Query the call graph, find dead code, "
"trace dependencies. Run /index first if tools report no index. "
"Use who_calls/blast_radius for impact analysis, dead_code for cleanup, "
"search_symbols to find symbols by name, dependency_chain for imports."
```

### 2. MCP Registration

**Via CLI (in `install.sh`):**
```bash
claude mcp add --transport stdio --scope user project-index -- \
    python3 ~/.claude-code-project-index/scripts/mcp_server.py
```

**Result in `~/.claude.json`:**
```json
{
  "mcpServers": {
    "project-index": {
      "type": "stdio",
      "command": "python3",
      "args": ["~/.claude-code-project-index/scripts/mcp_server.py"],
      "env": {}
    }
  }
}
```

**Scope: `user`** — available across all projects. Graceful degradation handles projects without an index.

### 3. New Skill: `code-intelligence-index`

**Location:** `~/.claude/skills/code-intelligence-index/SKILL.md`

**Purpose:** Single hub skill that:
- Checks if PROJECT_INDEX.json exists and is fresh (< 24h, matching files hash)
- Provides structured query patterns for other skills to call
- Falls back to Grep/sg when no index available
- Teaches Claude the right mental model for when to use structural queries vs text search

**Key sections:**
- **Freshness check protocol** — compare `_meta.files_hash` with current hash
- **Query method guide** — which QueryEngine method for which question
- **Fallback matrix** — what to do when index is missing or stale
- **Integration patterns** — how system-mapping and impact-analysis should call this

### 4. SessionStart Rule: `project-index-awareness.md`

**Location:** `~/.claude/rules/project-index-awareness.md`

**Content:** Auto-loaded rule that:
- Checks `PROJECT_INDEX.json` exists in project root at session start
- If present: notes freshness and available queries
- If missing: suggests running `/index` to create one (once per project, not every session)
- Does NOT auto-create — always asks first

### 5. Skill Updates

#### system-mapping (deep integration)

**Point 1 (Architecture):**
- Before: Glob + Grep for files, entry points, modules
- After: `file_summary` for each relevant file + `dir_purposes` from index + `tree` structure
- Fallback: Original Grep/sg patterns

**Point 2 (Execution Flow):**
- Before: Grep for function calls, async patterns
- After: `who_calls(target, depth=3)` for call chains + `blast_radius` for impact scope
- Fallback: Original sg patterns

**Point 4 (Dependencies):**
- Before: Grep for imports, reverse deps
- After: `dependency_chain(file, depth=5)` for forward deps + Grep for reverse deps (QueryEngine doesn't have reverse file deps yet)
- Fallback: Original Grep patterns

#### impact-analysis (deep integration)

| Check | Before | After |
|-------|--------|-------|
| UPSTREAM (Callers) | `Grep` for imports and calls | `who_calls(symbol, depth=2)` |
| DOWNSTREAM (Deps) | Read imports in file | `dependency_chain(file)` |
| CONTRACTS | Manual comparison | `file_summary(file)` for signatures |
| TEST COVERAGE | Find test files | `search_symbols("test_.*<func>")` |
| SIDE EFFECTS | Read function body | Still manual (index doesn't track side effects) |
| BLAST RADIUS | Estimated from caller count | `blast_radius(symbol, depth=3)` with stratified output |

#### ultraplan (Phase 1 enhancement)

Add to Phase 1 "Gather Initial Context":
```bash
# Check for project index
if [ -f PROJECT_INDEX.json ]; then
    echo "PROJECT_INDEX.json found — structural queries available"
    python3 ~/.claude-code-project-index/scripts/cli.py query dead-code | head -20
else
    echo "No project index. Consider running /index for structural intelligence."
fi
```

Also: Phase 3 research agents can use MCP tools for structural questions.

#### codebase-deep-dive (Phase 2 bootstrap)

Phase 2 (Structural Analysis) Agent 1 gets an index-awareness preamble:
```
If PROJECT_INDEX.json exists, start by loading it:
- tree structure from 'tree' key
- dir_purposes for directory roles
- file_summary for each major file
- call graph edges from 'g' and 'xg'
This bootstraps 80% of structural analysis. Use sg/Grep to fill gaps.
```

### 6. AA-MA Integration

**During milestone planning (`/ultraplan`):**
- Auto-populate `reference.md` with structural facts:
  - Files involved (from `search_symbols` and `dependency_chain`)
  - Blast radius of planned changes
  - Entry points affected

**During implementation (`/execute-aa-ma-milestone`):**
- Before writing files: `blast_radius` check for high-impact warnings
- After writing: diff against index to detect new dead code

**On milestone completion:**
- `dead_code` check to flag cleanup opportunities
- Updated index regeneration via stop hook

---

## Deliverables

| # | Deliverable | File | Effort |
|---|-------------|------|--------|
| 1 | Fix MCP server graceful degradation | `scripts/mcp_server.py` | Low |
| 2 | Create code-intelligence-index skill | `~/.claude/skills/code-intelligence-index/SKILL.md` | Medium |
| 3 | Update system-mapping skill | `~/.claude/skills/system-mapping/SKILL.md` | Medium |
| 4 | Update impact-analysis skill | `~/.claude/skills/impact-analysis/SKILL.md` | Medium |
| 5 | Update ultraplan command | `~/.claude/commands/ultraplan.md` | Low |
| 6 | Update codebase-deep-dive command | `~/.claude/commands/codebase-deep-dive.md` | Low |
| 7 | Create SessionStart awareness rule | `~/.claude/rules/project-index-awareness.md` | Low |
| 8 | Update install.sh with MCP registration | `install.sh` | Low |

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Stale index gives wrong answers | Medium | Freshness check in skill; regenerate if >24h or hash mismatch |
| MCP server fails in some projects | Low | Graceful degradation returns helpful error messages |
| Over-dependence on index | Medium | Every integration has Grep/sg fallback |
| Large skill files become unwieldy | Low | Hub skill pattern keeps individual skill changes focused |
| Breaking existing skill behavior | Medium | Test each skill update independently; keep original patterns as fallback |

## Success Criteria

1. New sessions in indexed projects show index awareness without `-i` flag
2. `Skill(system-mapping)` completes 3x faster with index vs without
3. `Skill(impact-analysis)` produces transitive caller chains (depth > 1)
4. `/ultraplan` Phase 1 includes structural context from index
5. MCP tools (`who_calls`, `blast_radius`, etc.) available in every session
6. All skills gracefully degrade when no index exists

---

## Implementation Deviations (2026-03-17)

| Design Spec | Actual Implementation | Reason |
|-------------|----------------------|--------|
| Post-write dead_code diff during milestone execution | Not implemented | Low value-to-complexity ratio; dead code check is already available via CLI/MCP on demand |
| On milestone completion: dead_code check + index regeneration | Not implemented | Stop hook already handles regeneration; dead code check as a mandatory gate would slow workflows |
| `xg` (cross-file graph) populated | 0 edges in test index | Cross-file resolution depends on import map quality; works for projects with explicit imports but this project's structure doesn't produce many cross-file edges |

All deviations are scope reductions, not design changes. The core architecture (3 access paths, hub skill, fallback matrix, SessionStart rule) was implemented as designed.

---

## Sources

- [Claude Code MCP Documentation](https://code.claude.com/docs/en/mcp)
- [Claude Code MCP Configuration Guide](https://www.builder.io/blog/claude-code-mcp-servers)
- [Configuring MCP Tools in Claude Code](https://scottspence.com/posts/configuring-mcp-tools-in-claude-code)
