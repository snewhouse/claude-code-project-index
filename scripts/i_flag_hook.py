#!/usr/bin/env python3
"""
UserPromptSubmit hook for intelligent PROJECT_INDEX.json analysis.
Detects -i[number] and -ic[number] flags for dynamic index generation.
"""

import json
import sys
import os
import re
import subprocess
import hashlib
import tempfile
import time
from pathlib import Path
from datetime import datetime

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

# Constants
DEFAULT_SIZE_K = 50  # Default 50k tokens
MIN_SIZE_K = 1       # Minimum 1k tokens
CLAUDE_MAX_K = 100   # Max 100k for Claude (leaves room for reasoning)
EXTERNAL_MAX_K = 800 # Max 800k for external AI


def _validate_python_cmd(cmd_path: str) -> bool:
    """Validate that a python command path is safe to execute."""
    import os
    from pathlib import Path

    path = Path(cmd_path)

    # Must be an absolute path
    if not path.is_absolute():
        return False

    # Must exist and be executable
    if not path.exists() or not os.access(str(path), os.X_OK):
        return False

    # Basename must look like a Python interpreter
    basename = path.name
    if not (basename.startswith('python') or basename == 'python3'):
        return False

    return True


def find_project_root():
    """Find project root by looking for .git or common project markers."""
    current = Path.cwd()
    
    # First check current directory for project markers
    if (current / '.git').exists():
        return current
    
    # Check for other project markers
    project_markers = ['package.json', 'pyproject.toml', 'setup.py', 'Cargo.toml', 'go.mod']
    for marker in project_markers:
        if (current / marker).exists():
            return current
        
    # Search up the tree for .git
    for parent in current.parents:
        if (parent / '.git').exists():
            return parent
            
    # Default to current directory
    return current

def get_last_interactive_size():
    """Get the last remembered -i size from the index."""
    try:
        project_root = find_project_root()
        index_path = project_root / 'PROJECT_INDEX.json'
        
        if index_path.exists():
            with open(index_path, 'r') as f:
                index = json.load(f)
                meta = index.get('_meta', {})
                last_size = meta.get('last_interactive_size_k')
                
                if last_size:
                    print(f"📝 Using remembered size: {last_size}k", file=sys.stderr)
                    return last_size
    except Exception:
        pass

    # Fall back to default
    return DEFAULT_SIZE_K

def parse_index_flag(prompt):
    """Parse -i or -ic flag with optional size."""
    # Pattern matches -i[number] or -ic[number]
    match = re.search(r'-i(c?)(\d+)?(?:\s|$)', prompt)
    
    if not match:
        return None, None, prompt
    
    clipboard_mode = match.group(1) == 'c'
    
    # If no explicit size provided, check for remembered size
    if match.group(2):
        size_k = int(match.group(2))
    else:
        # For -i without size, try to use last remembered size
        if not clipboard_mode:
            size_k = get_last_interactive_size()
        else:
            # For -ic, always use default
            size_k = DEFAULT_SIZE_K
    
    # Validate size limits
    if size_k < MIN_SIZE_K:
        print(f"⚠️ Minimum size is {MIN_SIZE_K}k, using {MIN_SIZE_K}k", file=sys.stderr)
        size_k = MIN_SIZE_K
    
    if not clipboard_mode and size_k > CLAUDE_MAX_K:
        print(f"⚠️ Claude max is {CLAUDE_MAX_K}k (need buffer for reasoning), using {CLAUDE_MAX_K}k", file=sys.stderr)
        size_k = CLAUDE_MAX_K
    elif clipboard_mode and size_k > EXTERNAL_MAX_K:
        print(f"⚠️ Maximum size is {EXTERNAL_MAX_K}k, using {EXTERNAL_MAX_K}k", file=sys.stderr)
        size_k = EXTERNAL_MAX_K
    
    # Clean prompt (remove flag)
    cleaned_prompt = re.sub(r'-ic?\d*\s*', '', prompt).strip()
    
    return size_k, clipboard_mode, cleaned_prompt

def calculate_files_hash(project_root):
    """Calculate hash of non-ignored files to detect changes."""
    try:
        # Use git ls-files to get non-ignored files
        result = subprocess.run(
            ['git', 'ls-files', '--cached', '--others', '--exclude-standard'],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            files = result.stdout.strip().split('\n') if result.stdout.strip() else []
        else:
            # Fallback to manual file discovery
            files = []
            for file_path in project_root.rglob('*'):
                if file_path.is_file() and not any(part.startswith('.') for part in file_path.parts):
                    files.append(str(file_path.relative_to(project_root)))
        
        # Hash file paths and modification times
        hasher = hashlib.sha256()
        for file_path in sorted(files):
            full_path = project_root / file_path
            if full_path.exists():
                try:
                    mtime = str(full_path.stat().st_mtime)
                    hasher.update(f"{file_path}:{mtime}".encode())
                except (OSError, ValueError):
                    pass
        
        return hasher.hexdigest()[:16]
    except Exception as e:
        print(f"Warning: Could not calculate files hash: {e}", file=sys.stderr)
        return "unknown"

def should_regenerate_index(project_root, index_path, requested_size_k):
    """Determine if index needs regeneration."""
    if not index_path.exists():
        return True, "No index exists"
    
    try:
        # Read metadata
        with open(index_path, 'r') as f:
            index = json.load(f)
            meta = index.get('_meta', {})
        
        # Get last generation info
        last_target = meta.get('target_size_k', 0)
        last_files_hash = meta.get('files_hash', '')
        
        # Check if files changed
        current_files_hash = calculate_files_hash(project_root)
        if current_files_hash != last_files_hash and current_files_hash != "unknown":
            return True, f"Files changed since last index"
        
        # Check if different size requested
        if abs(requested_size_k - last_target) > 2:  # Allow 2k tolerance
            return True, f"Different size requested ({requested_size_k}k vs {last_target}k)"
        
        # Use existing index
        actual_k = meta.get('actual_size_k', last_target)
        return False, f"Using cached index ({actual_k}k actual, {last_target}k target)"
    
    except Exception as e:
        print(f"Warning: Could not read index metadata: {e}", file=sys.stderr)
        return True, "Could not read index metadata"

def generate_index_at_size(project_root, target_size_k, is_clipboard_mode=False):
    """Generate index at specific token size."""
    print(f"🎯 Generating {target_size_k}k token index...", file=sys.stderr)
    
    # Find indexer script
    local_indexer = Path(__file__).parent / 'project_index.py'
    system_indexer = Path.home() / '.claude-code-project-index' / 'scripts' / 'project_index.py'
    
    indexer_path = local_indexer if local_indexer.exists() else system_indexer
    
    if not indexer_path.exists():
        print("⚠️ PROJECT_INDEX.json indexer not found", file=sys.stderr)
        return False
    
    try:
        # Find Python command
        python_cmd_file = Path.home() / '.claude-code-project-index' / '.python_cmd'
        if python_cmd_file.exists():
            python_cmd = python_cmd_file.read_text().strip()
            if not _validate_python_cmd(python_cmd):
                print(f"⚠️ Invalid Python command in .python_cmd: {python_cmd}", file=sys.stderr)
                python_cmd = sys.executable  # Fallback to current interpreter
        else:
            python_cmd = sys.executable
        
        # Pass target size as environment variable
        env = os.environ.copy()
        env['INDEX_TARGET_SIZE_K'] = str(target_size_k)
        
        result = subprocess.run(
            [python_cmd, str(indexer_path)],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=30,  # 30 seconds should be plenty for most projects
            env=env
        )
        
        if result.returncode == 0:
            # Update metadata with target size and hash
            index_path = project_root / 'PROJECT_INDEX.json'
            if index_path.exists():
                with open(index_path, 'r') as f:
                    index = json.load(f)
                
                # Measure actual size
                index_str = json.dumps(index, indent=2)
                actual_tokens = len(index_str) // 4  # Rough estimate: 4 chars = 1 token
                actual_size_k = actual_tokens // 1000
                
                # Add/update metadata
                if '_meta' not in index:
                    index['_meta'] = {}
                
                metadata_update = {
                    'generated_at': time.time(),
                    'target_size_k': target_size_k,
                    'actual_size_k': actual_size_k,
                    'files_hash': calculate_files_hash(project_root),
                    'compression_ratio': f"{(actual_size_k/target_size_k)*100:.1f}%" if target_size_k > 0 else "N/A"
                }
                
                # Remember -i size for next time (but not -ic)
                if not is_clipboard_mode:
                    metadata_update['last_interactive_size_k'] = target_size_k
                    print(f"💾 Remembering size {target_size_k}k for next -i", file=sys.stderr)
                
                index['_meta'].update(metadata_update)
                
                # Atomic write with optional locking
                index_data = json.dumps(index, indent=2).encode('utf-8')
                tmp_fd, tmp_path = tempfile.mkstemp(
                    dir=str(index_path.parent),
                    suffix='.tmp',
                    prefix='.PROJECT_INDEX_'
                )
                try:
                    if HAS_FCNTL:
                        fcntl.flock(tmp_fd, fcntl.LOCK_EX)
                    os.write(tmp_fd, index_data)
                    os.close(tmp_fd)
                    os.replace(tmp_path, str(index_path))
                except Exception:
                    try:
                        os.close(tmp_fd)
                    except Exception:
                        pass
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                    raise
                
                print(f"✅ Created PROJECT_INDEX.json ({actual_size_k}k actual, {target_size_k}k target)", file=sys.stderr)
                return True
            else:
                print("⚠️ Index file not created", file=sys.stderr)
                return False
        else:
            print(f"⚠️ Failed to create index: {result.stderr}", file=sys.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print("⚠️ Index creation timed out", file=sys.stderr)
        return False
    except Exception as e:
        print(f"⚠️ Error creating index: {e}", file=sys.stderr)
        return False

_CLIPBOARD_INSTRUCTIONS = """You are analyzing a codebase index to help identify relevant files and code sections.

## YOUR TASK
Analyze the PROJECT_INDEX.json below to identify the most relevant code sections for the user's request.
The index contains file structures, function signatures, call graphs, and dependencies.

## WHAT TO LOOK FOR
- Identify specific files and functions related to the request
- Trace call graphs to understand code flow
- Note dependencies and relationships
- Consider architectural patterns

## IMPORTANT: RESPONSE FORMAT
Your response will be copied and pasted to Claude Code. Format your response as:

### 📍 RELEVANT CODE LOCATIONS

**Primary Files to Examine:**
- `path/to/file.py` - [Why relevant]
  - `function_name()` (line X) - [What it does]
  - Called by: [list any callers]
  - Calls: [list what it calls]

**Related Files:**
- `path/to/related.py` - [Connection to task]

### 🔍 KEY INSIGHTS
- [Architectural patterns observed]
- [Dependencies to consider]
- [Potential challenges or gotchas]

### 💡 RECOMMENDATIONS
- Start by examining: [specific file]
- Focus on: [specific functions/classes]
- Consider: [any special considerations]

Do NOT include the original user prompt in your response.
Focus on providing actionable file locations and insights."""


def _build_clipboard_content(prompt, index_path):
    """Build the full clipboard string: instructions + index."""
    with open(index_path, 'r') as f:
        index = json.load(f)
    return (
        f"# Codebase Analysis Request\n\n"
        f"## Task for You\n{prompt}\n\n"
        f"## Instructions\n{_CLIPBOARD_INSTRUCTIONS}\n\n"
        f"## PROJECT_INDEX.json\n{json.dumps(index, indent=2)}\n"
    )


def _try_osc52(content):
    """Try OSC 52 clipboard escape sequence (SSH sessions, small content)."""
    import base64
    mosh_limit = 11000
    content_size = len(content)
    if content_size > mosh_limit:
        print(f"📋 Content exceeds mosh/tmux 12KB limit ({content_size} chars)", file=sys.stderr)
        return None

    b64 = base64.b64encode(content.encode('utf-8')).decode('ascii')
    is_tmux = os.environ.get('TMUX')
    if is_tmux:
        try:
            r = subprocess.run(['tmux', 'display-message', '-p', '#{client_tty}'],
                               capture_output=True, text=True, check=True)
            tty_device = r.stdout.strip()
        except (subprocess.SubprocessError, OSError):
            tty_device = "/dev/tty"
        sequence = f"\033Ptmux;\033\033]52;c;{b64}\007\033\\"
    else:
        tty_device = "/dev/tty"
        sequence = f"\033]52;c;{b64}\007"

    try:
        with open(tty_device, 'w') as tty:
            tty.write(sequence)
            tty.flush()
    except PermissionError:
        sys.stderr.write(sequence)
        sys.stderr.flush()

    print(f"✅ Sent to clipboard via OSC 52 ({content_size} chars)", file=sys.stderr)
    return ('ssh_clipboard', None)


def _try_tmux_buffer(content):
    """Try tmux load-buffer (SSH sessions, large content fallback)."""
    proc = subprocess.Popen(
        ['tmux', 'load-buffer', '-'],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    proc.communicate(content.encode('utf-8'))
    if proc.returncode == 0:
        print(f"✅ Loaded into tmux buffer (use prefix + ] to paste)", file=sys.stderr)
        return ('ssh_clipboard', None)
    return None


def _try_xclip(content):
    """Try xclip clipboard (local Linux with X11)."""
    result = subprocess.run(['which', 'xclip'], capture_output=True)
    if result.returncode != 0:
        return None
    env = os.environ.copy()
    if not env.get('DISPLAY'):
        return None
    proc = subprocess.Popen(
        ['xclip', '-selection', 'clipboard'],
        stdin=subprocess.PIPE, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    proc.communicate(content.encode('utf-8'))
    if proc.returncode == 0:
        print(f"✅ Copied to clipboard via xclip: {len(content)} chars", file=sys.stderr)
        print(f"📋 Ready to paste into Gemini, Claude.ai, ChatGPT, or other AI", file=sys.stderr)
        return ('clipboard', len(content))
    return None


def _try_pyperclip(content):
    """Try pyperclip library fallback."""
    import pyperclip
    pyperclip.copy(content)
    print(f"✅ Copied to clipboard via pyperclip: {len(content)} chars", file=sys.stderr)
    print(f"📋 Ready to paste into Gemini, Claude.ai, ChatGPT, or other AI", file=sys.stderr)
    return ('clipboard', len(content))


def _try_file_fallback(content, cwd):
    """Write content to a temp file as last resort."""
    fd, path_str = tempfile.mkstemp(
        prefix='.clipboard_content_', suffix='.txt', dir=str(cwd)
    )
    try:
        os.write(fd, content.encode('utf-8'))
        os.fchmod(fd, 0o600)
    finally:
        os.close(fd)
    print(f"✅ Saved to {path_str} (copy manually)", file=sys.stderr)
    return ('file', path_str)


CLIPBOARD_TRANSPORTS = [_try_xclip, _try_pyperclip]
SSH_TRANSPORTS = [_try_osc52, _try_tmux_buffer]


def copy_to_clipboard(prompt, index_path):
    """Copy content to clipboard using first available transport."""
    clipboard_content = _build_clipboard_content(prompt, index_path)
    is_ssh = os.environ.get('SSH_CONNECTION') or os.environ.get('SSH_CLIENT')

    transports = SSH_TRANSPORTS if is_ssh else CLIPBOARD_TRANSPORTS
    for transport in transports:
        try:
            result = transport(clipboard_content)
            if result is not None:
                if is_ssh and result[1] is None:
                    fallback = _try_file_fallback(clipboard_content, Path.cwd())
                    print(f"📁 Full content saved to {fallback[1]}", file=sys.stderr)
                    return (result[0], fallback[1])
                return result
        except Exception:
            continue

    return _try_file_fallback(clipboard_content, Path.cwd())


_CRITICAL_STOP = (
    "**CRITICAL INSTRUCTION FOR CLAUDE**: STOP! Do NOT proceed with the original request. "
    "The user wants to use an external AI for analysis. You should:\n"
    "1. ONLY acknowledge that the content was copied to clipboard\n"
    "2. WAIT for the user to paste the external AI's response\n"
    '3. DO NOT attempt to answer or work on: "{prompt}"\n\n'
    'Simply respond with something like: "✅ Index copied to clipboard for external AI analysis. '
    'Please paste the response here when ready."\n\n'
    "User's request (DO NOT ANSWER): {prompt}"
)


def _build_hook_output(copy_result, cleaned_prompt, size_k):
    """Build hookSpecificOutput dict from copy_to_clipboard result."""
    transport_type, data = copy_result
    stop_msg = _CRITICAL_STOP.format(prompt=cleaned_prompt)

    if transport_type == 'clipboard':
        header = f"📋 Clipboard Mode Activated\n\nIndex and instructions copied to clipboard ({size_k}k tokens, {data} chars).\nPaste into external AI (Gemini, Claude.ai, ChatGPT) for analysis."
    elif transport_type == 'ssh_clipboard':
        header = f"📋 Clipboard Mode - Clipboard Success!\n\n✅ Index sent to clipboard via OSC 52 ({size_k}k tokens).\n📁 Also saved to: {data}\n\nPaste directly into external AI (Gemini, Claude.ai, ChatGPT) for analysis."
    elif transport_type == 'ssh_file_large':
        header = (
            f"📋 Clipboard Mode - Content Too Large for Auto-Copy\n\n"
            f"Index saved to: {data} ({size_k}k tokens).\n"
            f"⚠️ Content exceeds mosh/OSC 52 limit for automatic clipboard.\n\n"
            f"Copy the file manually: cat {data} | pbcopy  # macOS\n"
            f"                         cat {data} | xclip   # Linux\n\n"
            f"Then paste into external AI (Gemini, Claude.ai, ChatGPT) for analysis."
        )
    elif transport_type == 'file':
        header = (
            f"📁 Clipboard Mode (File Fallback)\n\n"
            f"Index and instructions saved to: {data} ({size_k}k tokens).\n"
            f"⚠️ No clipboard method available - content saved to file instead.\n\n"
            f"To copy: cat {data} | pbcopy  # macOS\n"
            f"         cat {data} | xclip   # Linux\n\n"
            f"Then paste into external AI (Gemini, Claude.ai, ChatGPT) for analysis."
        )
    else:
        header = f"❌ Clipboard Mode Failed\n\nError: {data}\n\nPlease check the error and try again."

    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": f"\n{header}\n\n{stop_msg}\n"
        }
    }


def main():
    """Process UserPromptSubmit hook for -i and -ic flag detection."""
    try:
        # Read hook input
        input_data = json.load(sys.stdin)
        prompt = input_data.get('prompt', '')
        
        # Parse flag
        size_k, clipboard_mode, cleaned_prompt = parse_index_flag(prompt)
        
        if size_k is None:
            # No index flag, let prompt proceed normally
            sys.exit(0)
        
        # Find project root
        project_root = find_project_root()
        index_path = project_root / 'PROJECT_INDEX.json'
        
        # Check if regeneration needed
        should_regen, reason = should_regenerate_index(project_root, index_path, size_k)
        
        if should_regen:
            print(f"🔄 Regenerating index: {reason}", file=sys.stderr)
            if not generate_index_at_size(project_root, size_k, clipboard_mode):
                print("⚠️ Proceeding without PROJECT_INDEX.json", file=sys.stderr)
                sys.exit(0)
        else:
            print(f"✅ {reason}", file=sys.stderr)
        
        # Handle clipboard mode
        if clipboard_mode:
            copy_result = copy_to_clipboard(cleaned_prompt, index_path)
            output = _build_hook_output(copy_result, cleaned_prompt, size_k)
        else:
            # Standard mode - prepare for subagent
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": f"""
## 🎯 Index-Aware Mode Activated

Generated/loaded {size_k}k token index.

**IMPORTANT**: You MUST use the index-analyzer subagent to analyze the codebase structure before proceeding with the request.

Use it like this:
"I'll analyze the codebase structure to understand the relevant code sections for your request."

Then explicitly invoke: "Using the index-analyzer subagent to analyze PROJECT_INDEX.json..."

The subagent will provide deep code intelligence including:
- Essential code paths and dependencies
- Call graphs and impact analysis
- Architectural insights and patterns
- Strategic recommendations

Original request (without -i flag): {cleaned_prompt}

PROJECT_INDEX.json location: {index_path}
"""
                }
            }
        
        print(json.dumps(output))
        sys.exit(0)
        
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Hook error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()