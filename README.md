# Project Index for Claude Code

**⚠️ Beta Community Tool - Let Claude Code Fork It!** This is my personal indexing solution that I'm sharing (still in beta). I'm not maintaining this as a product. If you run into issues, have Claude Code help you fix them! Give this repo URL to Claude and ask it to fork, set up, and adapt it for your specific needs.

## Background

I created this tool for myself and talked about it in [this video](https://www.youtube.com/watch?v=JU8BwMe_BWg) and [this X post](https://x.com/EricBuess/status/1955271258939043996). People requested it, so here it is! This works alongside my [Claude Code Docs mirror](https://github.com/ericbuess/claude-code-docs) project.

I may post videos explaining how I use this project - check [my X/Twitter](https://x.com/EricBuess) for updates and explanations.

This isn't a product - just a tool that solves Claude Code's architectural blindness for me. Fork it, improve it, make it yours!

Automatically gives Claude Code architectural awareness of your codebase. Add `-i` to any prompt to generate or update a PROJECT_INDEX.json containing your project's functions, classes, and structure.

## Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/ericbuess/claude-code-project-index/main/install.sh | bash
```

## Usage

Just add `-i` to any Claude prompt:

```bash
claude "fix the auth bug -i"          # Auto-creates/uses index (default 50k)
claude "refactor database code -i75"  # Target ~75k tokens (if project needs it)
claude "analyze architecture -ic200"  # Export up to 200k to clipboard for external AI

# Or manually create/update the index anytime
/index
```

**Key behaviors:**
- **One-time setup**: Use `-i` once in a project and the index auto-updates forever
- **Size memory**: The number (e.g., 75) is remembered until you specify a new one
- **Auto-maintenance**: Every file change triggers automatic index updates
- **To stop indexing**: Simply delete PROJECT_INDEX.json

## What It Does

PROJECT_INDEX extracts and tracks:
- **Functions & Classes**: Full signatures with parameters and return types
- **Call Relationships**: Which functions call which others
- **File Organization**: All code files respecting .gitignore
- **Directory Structure**: Project layout with file counts

This helps Claude:
- Find the right code without searching
- Understand dependencies before making changes
- Place new code in the correct location
- Avoid creating duplicate functions

## Three Ways to Use

### Small Projects - Direct Reference with `@PROJECT_INDEX.json`
```bash
# Reference directly in your prompt
@PROJECT_INDEX.json what functions call authenticate_user?

# Or auto-load in every session by adding to CLAUDE.md:
# Add @PROJECT_INDEX.json to your CLAUDE.md file
```

**Best for**: Small projects where the index fits comfortably in context. Gives Claude's main agent direct awareness of your whole project structure.

### Medium Projects - Subagent Mode with `-i` flag
```bash
# Invokes specialized subagent to analyze PROJECT_INDEX.json
claude "refactor the auth system -i"   # Default up to 50k tokens
claude "find performance issues -i75"  # Target ~75k tokens for more detail
```

**Best for**: Medium to large projects where you want to preserve the main agent's context. The subagent analyzes the index separately and returns only relevant findings.

The subagent provides:
- Call graph analysis and execution paths
- Dependency mapping and impact analysis
- Dead code detection
- Strategic recommendations on where to make changes

### Large Projects - Clipboard Export with `-ic` flag
```bash
# Export to clipboard for external AI with larger contexts
claude "analyze entire codebase -ic200"  # Up to 200k tokens
claude "architecture review -ic800"      # Up to 800k tokens
```

**Best for**: Very large projects whose index won't fit in Claude's context window. Export to AI models with larger context windows:
- Gemini Pro (2M tokens)
- Claude models with 200k+ tokens
- ChatGPT
- Grok

**Note**: I'm not using this on large projects myself yet - this is inspiration/theory. Your mileage may vary. If you hit snags, have Claude Code update it to work for your specific use case!

## Token Sizing

The number after `-i` is a **maximum target**, not a guaranteed size:

- **Default**: 50k tokens (remembered per project)
- **-i mode range**: 1k to 100k maximum
- **-ic mode range**: 1k to 800k maximum for external AI
- **Actual size**: Often much smaller - only uses what the project needs
- **Compression**: Automatic to fit within limits

Examples:
- Small project with `-i200`: Might only generate 10k tokens
- Large project with `-i50`: Compresses to fit ~50k target
- Huge project with `-ic500`: Allows up to 500k if needed

The tool remembers your last `-i` size per project and targets that amount, but actual size depends on your codebase.

## Language Support

**Full parsing** (extracts functions, classes, methods):
- Python (.py)
- JavaScript/TypeScript (.js, .ts, .jsx, .tsx)
- Shell scripts (.sh, .bash)

**File tracking** (listing only):
- Go, Rust, Java, C/C++, Ruby, PHP, Swift, Kotlin, and 20+ more

## Testing

```bash
# Run full test suite
python3 -m pytest tests/ -v

# Run a single test file
python3 -m pytest tests/test_parsers.py -v

# Run a single test
python3 -m pytest tests/test_parsers.py::test_python_simple_function -v
```

The test suite covers: parser characterization (Python/JS/Shell), flag parsing, compression, security (no hardcoded IPs, validated executables), quality (no bare excepts, no dead code), clipboard transports, atomic writes, and parser registry dispatch.

## Installation Details

- **Location**: `~/.claude-code-project-index/`
- **Hooks configured**:
  - `UserPromptSubmit`: Detects -i flag, validates `.python_cmd`, injects context
  - `Stop`: Smart refresh — checks staleness before regenerating, skips when index is fresh
- **Commands**: `/index` for manual creation/update
- **Agent**: `~/.claude/agents/index-analyzer.md` for deep analysis
- **Python**: Automatically finds newest 3.8+ version

## Fork & Customize

**The whole point of this tool is that Claude Code can unbobble it for you!** When you hit issues, don't wait for me - have Claude fix them immediately. This is a community tool meant to be forked and adapted.

How to customize:
1. Fork the repo or work with the installed version
2. Describe your problem to Claude Code 
3. Let Claude modify it for your exact needs
4. Share your improvements with others

Common customizations:
```bash
cd ~/.claude-code-project-index
# Then ask Claude:
# "The indexer hangs on my 5000 file project - fix it"
# "Add support for Ruby and Go files with full parsing"
# "Skip test files and node_modules even if not in .gitignore"
# "Make it work with my monorepo structure"
# "Change compression to handle my specific project better"
```

Remember: Claude Code can rewrite this entire tool in minutes to match your needs. That's the power you have - use it!

## Known Issues & Quick Fixes

**Large projects (>2000 files)**: May timeout or hang during compression
- Fix: Ask Claude "Rewrite compress_if_needed() to handle my 3000 file project"

**.claude directory**: Already fixed - now excluded from indexing

**Timeouts**: Default is 30 seconds, may be too short for huge projects
- Fix: Ask Claude "Make timeout dynamic based on file count in i_flag_hook.py"

For any issue, just describe it to Claude and let it fix the tool for you!

## Requirements

- Python 3.8 or higher
- Claude Code with hooks support
- macOS or Linux
- git and jq (for installation)

## Troubleshooting

**Index not creating?**
- Check Python: `python3 --version`
- Verify hooks: `cat ~/.claude/settings.json | grep i_flag_hook`
- Manual generation: `python3 ~/.claude-code-project-index/scripts/project_index.py`

**-i flag not working?**
- Run installer again
- Check hooks are configured
- Remove and reinstall if needed

**Clipboard issues?**
- Install pyperclip: `pip install pyperclip`
- SSH users: OSC 52 escape sequence used automatically; content also saved to temp file with restricted permissions
- Local Linux: `xclip` used if available (install with `sudo apt install xclip`)

## Technical Details

**Index format:** Compressed JSON with short keys defined as constants (`KEY_FILES='f'`, `KEY_GRAPH='g'`, `KEY_DOCS='d'`, `KEY_DEPS='deps'`). Function signatures use colon-delimited format: `name:line:signature:calls:docstring`.

**Parser dispatch:** `PARSER_REGISTRY` dict in `index_utils.py` maps file extensions to parser functions. Adding a language: write `extract_X_signatures(content)`, register in `register_parsers()`.

**Clipboard transport:** Strategy pattern via `CLIPBOARD_TRANSPORTS` and `SSH_TRANSPORTS` lists in `i_flag_hook.py`. Transports: `_try_osc52` (SSH), `_try_tmux_buffer` (SSH large), `_try_xclip` (local X11), `_try_pyperclip` (library), `_try_file_fallback` (always works).

**File writes:** Atomic via `tempfile.mkstemp()` + `os.replace()`. Concurrent session safety via `fcntl.flock()` (Linux/WSL2).

**Security:** `.python_cmd` validated before execution (`_validate_python_cmd()`). No hardcoded IPs or author-specific paths. All exception handlers use typed exceptions (no bare `except:`).

## Uninstall

```bash
~/.claude-code-project-index/uninstall.sh
```

---
Created by [Eric Buess](https://github.com/ericbuess)
- 🐦 [Twitter/X](https://x.com/EricBuess)
- 📺 [YouTube](https://www.youtube.com/@EricBuess)
- 💼 [GitHub](https://github.com/ericbuess)