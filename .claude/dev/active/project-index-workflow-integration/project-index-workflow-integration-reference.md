# Project Index Workflow Integration — Reference

## Immutable Facts

### File Locations

| Item | Path |
|------|------|
| MCP server source | `scripts/mcp_server.py` |
| QueryEngine source | `scripts/query_engine.py` |
| CLI source | `scripts/cli.py` |
| Install script | `install.sh` |
| Installed location | `~/.claude-code-project-index/scripts/` |
| MCP config file | `~/.claude.json` (under `mcpServers` key) |
| New skill | `~/.claude/skills/code-intelligence-index/SKILL.md` |
| SessionStart rule | `~/.claude/rules/project-index-awareness.md` |
| system-mapping skill | `~/.claude/skills/system-mapping/SKILL.md` |
| impact-analysis skill | `~/.claude/skills/impact-analysis/SKILL.md` |
| ultraplan command | `~/.claude/commands/ultraplan.md` |
| deep-dive command | `~/.claude/commands/codebase-deep-dive.md` |
| Design doc | `docs/plans/2026-03-17-project-index-workflow-integration-design.md` |
| Test suite | `tests/` (135 tests as of b2e80b7) |

### MCP Configuration (Verified 2026-03-17)

- MCP servers stored in `~/.claude.json`, NOT `settings.json`
- `settings.json` controls permissions/allowlists only
- Registration command: `claude mcp add --transport stdio --scope user project-index -- python3 ~/.claude-code-project-index/scripts/mcp_server.py`
- Three scopes: `local` (per-user-per-project), `project` (shared `.mcp.json`), `user` (cross-project)
- Source: https://code.claude.com/docs/en/mcp

### QueryEngine Methods

| Method | Signature | Returns |
|--------|-----------|---------|
| `who_calls` | `(symbol: str, depth: int = 1)` | `List[str]` — caller identifiers |
| `blast_radius` | `(symbol: str, max_depth: int = 3)` | `Dict[str, List[str]]` — callers by depth |
| `dead_code` | `()` | `List[str]` — uncalled functions |
| `dependency_chain` | `(file_path: str, max_depth: int = 5)` | `Dict[str, List[str]]` — deps by depth |
| `search_symbols` | `(pattern: str, max_results: int = 50)` | `List[Dict]` — {file, name, type, line} |
| `file_summary` | `(file_path: str)` | `Optional[Dict]` — {language, functions, classes, imports} |
| Factory | `QueryEngine.from_file(path: Path)` | `QueryEngine` instance |

### Skill-to-QueryEngine Mapping

| Skill Check | QueryEngine Method | Replaces |
|-------------|-------------------|----------|
| system-mapping Point 1 (Architecture) | `file_summary`, `dir_purposes`, `tree` | Glob + Grep for files/modules |
| system-mapping Point 2 (Execution Flow) | `who_calls(target, depth=3)` | Grep for function calls |
| system-mapping Point 4 (Dependencies) | `dependency_chain(file)` | Grep for imports |
| impact-analysis UPSTREAM | `who_calls(symbol, depth=2)` | Grep for imports/calls |
| impact-analysis DOWNSTREAM | `dependency_chain(file)` | Read imports |
| impact-analysis CONTRACTS | `file_summary(file)` | Manual comparison |
| impact-analysis BLAST RADIUS | `blast_radius(symbol, depth=3)` | Estimated from caller count |
| impact-analysis TEST COVERAGE | `search_symbols("test_.*func")` | Find test files |

### Dense Index Keys (for skill authors)

| Key | Content |
|-----|---------|
| `f` | Files dict (abbreviated paths → `[lang, [funcs], {classes}]`) |
| `g` | Intra-file call graph edges `[[caller, callee], ...]` |
| `xg` | Cross-file call graph edges `[[caller, callee], ...]` |
| `deps` | Dependency graph (imports per file) |
| `d` | Documentation map (markdown headers) |
| `dir_purposes` | Inferred directory purposes |
| `tree` | ASCII directory structure |
| `_meta.symbol_importance` | Top 50 PageRank-scored symbols |
| `_meta.files_hash` | Hash for staleness detection |

### Constants

- `CURRENT_TOOL_VERSION = "1.0.0"` (cache_db.py — bump invalidates all caches)
- `MAX_FILES = 10000`, `MAX_INDEX_SIZE = 1MB` (project_index.py)
- Index freshness TTL: 24 hours (design decision, not yet in code)
- `V2_AST_PARSER` env var controls Python parser (default: "1" = AST-based)

_Last Updated: 2026-03-17_
