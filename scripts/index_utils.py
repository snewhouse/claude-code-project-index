#!/usr/bin/env python3
"""
Shared utilities for project indexing.
Contains common functionality used by both project_index.py and hook scripts.
"""

import ast
import json
import os
import re
import sys
import hashlib
import subprocess
import tempfile
import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


def validate_python_cmd(cmd_path: str) -> bool:
    """Validate that a python command path is safe to execute.

    Accepts: python, python3, python3.12, python3.13
    Rejects: python3-malicious, python3.12.1-extra, relative paths
    """
    path = Path(cmd_path)

    # Must be an absolute path
    if not path.is_absolute():
        return False

    # Must exist and be executable
    if not path.exists() or not os.access(str(path), os.X_OK):
        return False

    # Basename must match strict Python interpreter pattern
    basename = path.name
    if not re.fullmatch(r'python\d*(\.\d+)?', basename):
        return False

    return True


def calculate_files_hash(project_root: Path) -> str:
    """Calculate hash of non-ignored files to detect changes.

    Uses git ls-files with fallback to manual file discovery.
    Returns a 16-char hex digest or 'unknown' on error.
    """
    try:
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


def atomic_write_json(file_path: Path, data: dict, indent: int = None,
                      use_fcntl: bool = False) -> None:
    """Atomically write JSON data to a file using tempfile + os.replace.

    Args:
        file_path: Target file path.
        data: Dictionary to serialize as JSON.
        indent: JSON indent level (None for minified).
        use_fcntl: Whether to use fcntl.flock for advisory locking.
    """
    separators = (',', ':') if indent is None else None
    content = json.dumps(data, indent=indent, separators=separators).encode('utf-8')

    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=str(file_path.parent),
        suffix='.tmp',
        prefix=f'.{file_path.stem}_'
    )
    try:
        if use_fcntl:
            try:
                import fcntl
                fcntl.flock(tmp_fd, fcntl.LOCK_EX)
            except (ImportError, OSError):
                pass
        os.write(tmp_fd, content)
        os.close(tmp_fd)
        os.replace(tmp_path, str(file_path))
    except Exception:
        try:
            os.close(tmp_fd)
        except Exception:
            pass
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


# What to ignore (sensible defaults)
IGNORE_DIRS = {
    '.git', 'node_modules', '__pycache__', '.venv', 'venv', 'env',
    'build', 'dist', '.next', 'target', '.pytest_cache', 'coverage',
    '.idea', '.vscode', '.DS_Store', 'eggs', '.eggs',
    '.claude'  # Exclude Claude configuration directory
}

# Languages we can fully parse (extract functions/classes)
PARSEABLE_LANGUAGES = {
    '.py': 'python',
    '.js': 'javascript', 
    '.ts': 'typescript',
    '.jsx': 'javascript',
    '.tsx': 'typescript',
    '.sh': 'shell',
    '.bash': 'shell'
}

# All code file extensions we recognize
CODE_EXTENSIONS = {
    # Currently parsed
    '.py', '.js', '.ts', '.jsx', '.tsx',
    # Common languages (listed but not parsed yet)
    '.go', '.rs', '.java', '.c', '.cpp', '.cc', '.cxx', 
    '.h', '.hpp', '.rb', '.php', '.swift', '.kt', '.scala', 
    '.cs', '.sh', '.bash', '.sql', '.r', '.R', '.lua', '.m',
    '.ex', '.exs', '.jl', '.dart', '.vue', '.svelte',
    # Configuration and data files
    '.json', '.html', '.css'
}

# Markdown files to analyze
MARKDOWN_EXTENSIONS = {'.md', '.markdown', '.rst'}

# Common directory purposes
DIRECTORY_PURPOSES = {
    'auth': 'Authentication and authorization logic',
    'models': 'Data models and database schemas',
    'views': 'UI views and templates',
    'controllers': 'Request handlers and business logic',
    'services': 'Business logic and external service integrations',
    'utils': 'Shared utility functions and helpers',
    'helpers': 'Helper functions and utilities',
    'tests': 'Test files and test utilities',
    'test': 'Test files and test utilities',
    'spec': 'Test specifications',
    'docs': 'Project documentation',
    'api': 'API endpoints and route handlers',
    'components': 'Reusable UI components',
    'lib': 'Library code and shared modules',
    'src': 'Source code root directory',
    'static': 'Static assets (images, CSS, etc.)',
    'public': 'Publicly accessible files',
    'config': 'Configuration files and settings',
    'scripts': 'Build and utility scripts',
    'middleware': 'Middleware functions and handlers',
    'migrations': 'Database migration files',
    'fixtures': 'Test fixtures and sample data'
}


def extract_function_calls_python(body: str, all_functions: Set[str]) -> List[str]:
    """Extract function calls from Python code body."""
    calls = set()
    
    # Pattern for function calls: word followed by (
    # Excludes: control flow keywords, built-ins we don't care about
    call_pattern = r'\b(\w+)\s*\('
    exclude_keywords = {
        'if', 'elif', 'while', 'for', 'with', 'except', 'def', 'class',
        'return', 'yield', 'raise', 'assert', 'print', 'len', 'str', 
        'int', 'float', 'bool', 'list', 'dict', 'set', 'tuple', 'type',
        'isinstance', 'issubclass', 'super', 'range', 'enumerate', 'zip',
        'map', 'filter', 'sorted', 'reversed', 'open', 'input', 'eval'
    }
    
    for match in re.finditer(call_pattern, body):
        func_name = match.group(1)
        if func_name in all_functions and func_name not in exclude_keywords:
            calls.add(func_name)
    
    # Also catch method calls like self.method() or obj.method()
    method_pattern = r'(?:self|cls|\w+)\.(\w+)\s*\('
    for match in re.finditer(method_pattern, body):
        method_name = match.group(1)
        if method_name in all_functions:
            calls.add(method_name)
    
    return sorted(list(calls))


def extract_function_calls_javascript(body: str, all_functions: Set[str]) -> List[str]:
    """Extract function calls from JavaScript/TypeScript code body."""
    calls = set()
    
    # Pattern for function calls
    call_pattern = r'\b(\w+)\s*\('
    exclude_keywords = {
        'if', 'while', 'for', 'switch', 'catch', 'function', 'class',
        'return', 'throw', 'new', 'typeof', 'instanceof', 'void',
        'console', 'Array', 'Object', 'String', 'Number', 'Boolean',
        'Promise', 'Math', 'Date', 'JSON', 'parseInt', 'parseFloat'
    }
    
    for match in re.finditer(call_pattern, body):
        func_name = match.group(1)
        if func_name in all_functions and func_name not in exclude_keywords:
            calls.add(func_name)
    
    # Method calls: obj.method() or this.method()
    method_pattern = r'(?:this|\w+)\.(\w+)\s*\('
    for match in re.finditer(method_pattern, body):
        method_name = match.group(1)
        if method_name in all_functions:
            calls.add(method_name)
    
    return sorted(list(calls))



def _find_matching_brace(lines: List[str], start_line: int, start_col: int = 0) -> int:
    """Find the line index of the matching closing brace.

    Args:
        lines: Source code lines
        start_line: Line index where opening brace is (or where to start searching)
        start_col: Column offset to start from on start_line

    Returns:
        Line index of the closing brace, or len(lines) - 1 if not found.
    """
    brace_count = 0
    for i in range(start_line, len(lines)):
        line = lines[i]
        col_start = start_col if i == start_line else 0
        for col in range(col_start, len(line)):
            ch = line[col]
            if ch == '{':
                brace_count += 1
            elif ch == '}':
                brace_count -= 1
                if brace_count == 0:
                    return i
    return len(lines) - 1


def _find_matching_brace_char(text: str, start_pos: int, max_scan: int = 0) -> int:
    """Find the position of the matching closing brace in a string.

    Starts counting from start_pos (which should be just after the opening brace).
    The opening brace itself should already be accounted for (brace_count starts at 1).

    Args:
        text: Source text to scan
        start_pos: Position to start scanning (after the opening brace)
        max_scan: Maximum number of characters to scan (0 = no limit)

    Returns:
        Position of the closing brace, or start_pos if not found.
    """
    brace_count = 1
    end = min(len(text), start_pos + max_scan) if max_scan > 0 else len(text)
    for i in range(start_pos, end):
        if text[i] == '{':
            brace_count += 1
        elif text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                return i
    return start_pos


def _infer_const_type(value: str) -> str:
    """Infer the type category of a constant from its string value.

    Returns one of: 'collection', 'str', 'number', 'value'.
    """
    if value.startswith(('{', '[')):
        return 'collection'
    if value.startswith(("'", '"', '`')):
        return 'str'
    if value.replace('.', '').replace('-', '').isdigit():
        return 'number'
    return 'value'


def _parse_python_imports(lines: List[str]) -> List[str]:
    """Extract import statements from Python source lines.

    Parses both 'import X' and 'from X import Y' styles.

    Returns:
        List of imported module/package names.
    """
    import_pattern = r'^(?:from\s+([^\s]+)\s+)?import\s+(.+)$'
    imports = []
    for line in lines:
        import_match = re.match(import_pattern, line.strip())
        if import_match:
            module, items = import_match.groups()
            if module:
                # from X import Y style
                imports.append(module)
            else:
                # import X style
                for item in items.split(','):
                    item = item.strip().split(' as ')[0]  # Remove aliases
                    imports.append(item)
    return imports


def _extract_python_func_body(
    lines: List[str], start_idx: int, indent_level: int, all_function_names: Set[str],
    docstring_pattern: str
) -> Tuple[Optional[str], List[str], int]:
    """Extract a Python function's docstring and calls from its body.

    Scans lines after the def statement to collect the body based on indentation,
    then extracts the docstring and function calls.

    Args:
        lines: All source lines
        start_idx: Line index right after the def statement (the first body line)
        indent_level: Indentation level of the def keyword
        all_function_names: Set of known function names for call detection
        docstring_pattern: Regex pattern for single-line docstrings

    Returns:
        Tuple of (docstring_or_None, calls_list, end_line_idx).
    """
    # Extract docstring from first body line
    doc = None
    if start_idx < len(lines):
        doc_match = re.match(docstring_pattern, lines[start_idx])
        if doc_match:
            _, doc_content = doc_match.groups()
            doc = doc_content.strip()

    # Collect function body lines - everything indented more than the def line
    func_body_lines = []
    body_idx = start_idx
    while body_idx < len(lines):
        body_line = lines[body_idx]

        # Skip empty lines
        if not body_line.strip():
            func_body_lines.append(body_line)
            body_idx += 1
            continue

        # Check indentation to see if we're still in the function
        line_indent = len(body_line) - len(body_line.lstrip())

        # If we hit a line that's not indented more than the function def, we're done
        if line_indent <= indent_level and body_line.strip():
            break

        func_body_lines.append(body_line)
        body_idx += 1

    # Extract calls from the body
    calls = []
    if func_body_lines:
        func_body = '\n'.join(func_body_lines)
        calls = extract_function_calls_python(func_body, all_function_names)

    return doc, calls, body_idx


def _handle_python_class_def(
    class_match, i: int, lines: List[str], result: Dict,
    pending_decorators: List[str], class_stack: List, docstring_pattern: str
) -> Tuple[Optional[str], int]:
    """Handle a Python class definition line.

    Returns (current_class_name_or_None, class_indent) to update caller state.
    """
    indent, name, bases = class_match.groups()
    indent_level = len(indent)

    # Handle nested classes - pop from stack if dedented
    while class_stack and indent_level <= class_stack[-1][1]:
        class_stack.pop()

    current_class = None
    current_class_indent = -1

    # Only process top-level classes for the index
    if indent_level == 0:
        class_info = {'methods': {}, 'class_constants': {}}

        if pending_decorators:
            class_info['decorators'] = pending_decorators.copy()
            pending_decorators.clear()

        if bases:
            base_list = [b.strip() for b in bases.split(',') if b.strip()]
            if base_list:
                class_info['inherits'] = base_list
                base_names_lower = [b.lower() for b in base_list]
                if 'enum' in base_names_lower or any('enum' in b for b in base_names_lower):
                    class_info['type'] = 'enum'
                elif 'exception' in base_names_lower or 'error' in base_names_lower or any('exception' in b or 'error' in b for b in base_names_lower):
                    class_info['type'] = 'exception'
                elif 'abc' in base_names_lower or 'protocol' in base_names_lower:
                    class_info['abstract'] = True

        if i + 1 < len(lines):
            doc_match = re.match(docstring_pattern, lines[i + 1])
            if doc_match:
                _, doc_content = doc_match.groups()
                class_info['doc'] = doc_content.strip()

        class_info['line'] = i + 1
        result['classes'][name] = class_info
        current_class = name
        current_class_indent = indent_level

    class_stack.append((name, indent_level))
    return current_class, current_class_indent


def _handle_python_func_def(
    line: str, i: int, lines: List[str], result: Dict,
    func_pattern: str, skip_dunder: Set[str], pending_decorators: List[str],
    all_function_names: Set[str], docstring_pattern: str,
    current_class: Optional[str], current_class_indent: int
) -> int:
    """Handle a Python function/method definition.

    Returns the updated line index i.
    """
    func_start_match = re.match(r'^([ \t]*)(async\s+)?def\s+(\w+)\s*\(', line)
    if not func_start_match:
        return i

    indent, is_async, name = func_start_match.groups()
    indent_level = len(indent)

    # Collect the full signature across multiple lines
    full_sig = line.rstrip()
    j = i
    while j < len(lines) and not re.search(r'\).*:', lines[j]):
        j += 1
        if j < len(lines):
            full_sig += ' ' + lines[j].strip()

    if j >= len(lines):
        return i

    complete_match = re.match(func_pattern, full_sig)
    if not complete_match:
        return i

    indent, is_async, name, params, return_type = complete_match.groups()
    i = j

    params = re.sub(r'\s+', ' ', params).strip()

    if name in skip_dunder and name != '__init__':
        return i

    func_info = {'line': i + 1}
    signature = f"({params})"
    if return_type:
        signature += f" -> {return_type.strip()}"
    if is_async:
        signature = "async " + signature

    if pending_decorators:
        func_info['decorators'] = pending_decorators.copy()
        if 'abstractmethod' in pending_decorators and current_class:
            result['classes'][current_class]['abstract'] = True
        pending_decorators.clear()

    func_indent = len(indent) if indent else 0
    doc, calls, _ = _extract_python_func_body(
        lines, i + 1, func_indent, all_function_names, docstring_pattern
    )
    if doc:
        func_info['doc'] = doc
    if calls:
        func_info['calls'] = calls
    func_info['signature'] = signature

    if current_class and indent_level > current_class_indent:
        result['classes'][current_class]['methods'][name] = func_info
    elif indent_level == 0:
        result['functions'][name] = func_info

    return i


# Compiled patterns used by extract_python_signatures
_PY_PATTERNS = None


def _get_py_patterns():
    """Lazily compile and cache regex patterns for Python parsing."""
    global _PY_PATTERNS
    if _PY_PATTERNS is None:
        _PY_PATTERNS = {
            'class': r'^([ \t]*)class\s+(\w+)(?:\s*\((.*?)\))?:',
            'func': r'^([ \t]*)(async\s+)?def\s+(\w+)\s*\((.*?)\)(?:\s*->\s*([^:]+))?:',
            'property': r'^([ \t]*)(\w+)\s*:\s*([^=\n]+)',
            'module_const': r'^([A-Z_][A-Z0-9_]*)\s*=\s*(.+)$',
            'module_var': r'^(\w+)\s*:\s*([^=]+)\s*=',
            'class_const': r'^([ \t]+)([A-Z_][A-Z0-9_]*)\s*=\s*(.+)$',
            'type_alias': r'^(\w+)\s*=\s*(?:Union|Optional|List|Dict|Tuple|Set|Type|Callable|Literal|TypeVar|NewType|TypedDict|Protocol)\[.+\]$',
            'decorator': r'^([ \t]*)@(\w+)(?:\(.*\))?$',
            'docstring': r'^([ \t]*)(?:\'\'\'|""")(.+?)(?:\'\'\'|""")',
            'enum_val': r'^([ \t]+)([A-Z_][A-Z0-9_]*)\s*(?:=\s*(.+))?$',
        }
    return _PY_PATTERNS


def _parse_python_module_level(line: str, result: Dict, pat: Dict) -> bool:
    """Handle module-level type aliases, constants, and typed variables. Returns True if handled."""
    tam = re.match(pat['type_alias'], line)
    if tam:
        result['type_aliases'][tam.group(1)] = line.split('=', 1)[1].strip()
        return True
    cm = re.match(pat['module_const'], line)
    if cm:
        result['constants'][cm.group(1)] = _infer_const_type(cm.group(2).split('#')[0].strip())
        return True
    vm = re.match(pat['module_var'], line)
    if vm and vm.group(1) not in result['variables'] and not vm.group(1).startswith('_'):
        result['variables'].append(vm.group(1))
        return True
    return False


def _parse_python_class_body(line: str, result: Dict, pat: Dict,
                             current_class: str, current_class_indent: int) -> bool:
    """Handle class-level enum values, constants, and properties. Returns True if handled."""
    if result['classes'][current_class].get('type') == 'enum':
        em = re.match(pat['enum_val'], line)
        if em and len(em.group(1)) > current_class_indent:
            result['classes'][current_class].setdefault('values', []).append(em.group(2))
            return True
    ccm = re.match(pat['class_const'], line)
    if ccm and len(ccm.group(1)) > current_class_indent:
        result['classes'][current_class]['class_constants'][ccm.group(2)] = _infer_const_type(ccm.group(3).split('#')[0].strip())
        return True
    pm = re.match(pat['property'], line)
    if pm and len(pm.group(1)) > current_class_indent and not pm.group(2).startswith('_'):
        result['classes'][current_class].setdefault('properties', []).append(pm.group(2))
    return False


_SKIP_DUNDER = {'__repr__', '__str__', '__hash__', '__eq__', '__ne__',
                '__lt__', '__le__', '__gt__', '__ge__', '__bool__'}


def extract_python_signatures_ast(content: str) -> Dict[str, Dict]:
    """Extract Python function and class signatures using the ast module.

    Uses Python's ast module for accurate parsing. Falls back to the regex-based
    extract_python_signatures() on SyntaxError.

    Returns the same dict format as extract_python_signatures():
        {imports, functions, classes, constants, variables, type_aliases, enums}
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return extract_python_signatures(content)

    result: Dict[str, Any] = {
        'imports': [],
        'functions': {},
        'classes': {},
        'constants': {},
        'variables': [],
        'type_aliases': {},
        'enums': {},
    }

    def _unparse_safe(node) -> str:
        """Safely unparse an AST node to source string."""
        try:
            return ast.unparse(node)
        except Exception:
            return ''

    def _get_decorator_names(decorator_list) -> List[str]:
        """Extract decorator names from a list of decorator nodes."""
        names = []
        for dec in decorator_list:
            if isinstance(dec, ast.Name):
                names.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                names.append(_unparse_safe(dec))
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name):
                    names.append(dec.func.id)
                elif isinstance(dec.func, ast.Attribute):
                    names.append(_unparse_safe(dec.func))
        return names

    def _build_signature(node) -> str:
        """Build a function signature string from an ast.FunctionDef node."""
        params = []
        args = node.args

        # Calculate offset for defaults alignment
        # positional args: defaults align to the end of args.args
        num_args = len(args.args)
        num_defaults = len(args.defaults)
        default_offset = num_args - num_defaults

        for idx, arg in enumerate(args.args):
            param = arg.arg
            if param == 'self' or param == 'cls':
                continue
            if arg.annotation:
                param += ': ' + _unparse_safe(arg.annotation)
            di = idx - default_offset
            if di >= 0 and di < len(args.defaults):
                param += ' = ' + _unparse_safe(args.defaults[di])
            params.append(param)

        # *args
        if args.vararg:
            p = '*' + args.vararg.arg
            if args.vararg.annotation:
                p += ': ' + _unparse_safe(args.vararg.annotation)
            params.append(p)

        # keyword-only args
        for idx, arg in enumerate(args.kwonlyargs):
            param = arg.arg
            if arg.annotation:
                param += ': ' + _unparse_safe(arg.annotation)
            if idx < len(args.kw_defaults) and args.kw_defaults[idx] is not None:
                param += ' = ' + _unparse_safe(args.kw_defaults[idx])
            params.append(param)

        # **kwargs
        if args.kwarg:
            p = '**' + args.kwarg.arg
            if args.kwarg.annotation:
                p += ': ' + _unparse_safe(args.kwarg.annotation)
            params.append(p)

        sig = '(' + ', '.join(params) + ')'
        if node.returns:
            sig += ' -> ' + _unparse_safe(node.returns)

        # Prefix async
        if isinstance(node, ast.AsyncFunctionDef):
            sig = 'async ' + sig

        return sig

    def _extract_calls(body_nodes, all_func_names: Set[str]) -> List[str]:
        """Extract function call names from AST body nodes."""
        calls = set()
        exclude = {
            'print', 'len', 'str', 'int', 'float', 'bool', 'list', 'dict',
            'set', 'tuple', 'type', 'isinstance', 'issubclass', 'super',
            'range', 'enumerate', 'zip', 'map', 'filter', 'sorted',
            'reversed', 'open', 'input', 'eval',
        }
        for node in ast.walk(ast.Module(body=body_nodes, type_ignores=[])):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                    if name in all_func_names and name not in exclude:
                        calls.add(name)
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                    if name in all_func_names:
                        calls.add(name)
        return sorted(calls)

    def _process_function(node, all_func_names: Set[str]) -> Dict:
        """Process a FunctionDef/AsyncFunctionDef node into a result dict."""
        info: Dict[str, Any] = {
            'signature': _build_signature(node),
            'line': node.lineno,
        }
        doc = ast.get_docstring(node)
        if doc:
            # Truncate long docstrings to first line
            first_line = doc.split('\n')[0].strip()
            info['doc'] = first_line

        decorators = _get_decorator_names(node.decorator_list)
        if decorators:
            info['decorators'] = decorators

        calls = _extract_calls(node.body, all_func_names)
        if calls:
            info['calls'] = calls

        return info

    # First pass: collect all function names for call graph resolution
    all_function_names: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            all_function_names.add(node.name)

    # Second pass: extract structure from top-level nodes only
    for node in tree.body:
        # Imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                result['imports'].append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                result['imports'].append(node.module)

        # Top-level functions (not nested)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result['functions'][node.name] = _process_function(node, all_function_names)

        # Classes
        elif isinstance(node, ast.ClassDef):
            cls_info: Dict[str, Any] = {
                'methods': {},
                'line': node.lineno,
            }
            doc = ast.get_docstring(node)
            if doc:
                cls_info['doc'] = doc.split('\n')[0].strip()

            # Inheritance
            bases = [_unparse_safe(b) for b in node.bases if _unparse_safe(b)]
            if bases:
                cls_info['inherits'] = bases

            # Decorators
            decorators = _get_decorator_names(node.decorator_list)
            if decorators:
                cls_info['decorators'] = decorators

            # Detect enum
            is_enum = any(b in ('Enum', 'IntEnum', 'StrEnum', 'Flag', 'IntFlag')
                          for b in bases)
            if is_enum:
                cls_info['type'] = 'enum'

            # Class body
            class_constants: Dict[str, str] = {}
            properties: List[str] = []
            enum_values: List[str] = []

            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    cls_info['methods'][item.name] = _process_function(item, all_function_names)
                elif isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name):
                            name = target.id
                            if is_enum and not name.startswith('_'):
                                enum_values.append(name)
                            elif name.isupper():
                                class_constants[name] = _infer_const_type(_unparse_safe(item.value))
                            elif not name.startswith('_'):
                                properties.append(name)
                elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    name = item.target.id
                    if not name.startswith('_'):
                        properties.append(name)

            if class_constants:
                cls_info['class_constants'] = class_constants
            if properties:
                cls_info['properties'] = properties
            if enum_values:
                cls_info['values'] = enum_values

            result['classes'][node.name] = cls_info

        # Module-level constants and variables
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    name = target.id
                    if name.isupper():
                        result['constants'][name] = _infer_const_type(_unparse_safe(node.value))
                    elif not name.startswith('_'):
                        result['variables'].append(name)

        # Type aliases (Python 3.12 style or simple assignments)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
            if name.isupper():
                result['constants'][name] = _infer_const_type(
                    _unparse_safe(node.value) if node.value else 'value')
            elif not name.startswith('_'):
                result['variables'].append(name)

    # Cleanup: remove empty collections (match regex parser output format)
    if not result['constants']:
        del result['constants']
    if not result['variables']:
        del result['variables']
    if not result['type_aliases']:
        del result['type_aliases']
    if not result['enums']:
        del result['enums']
    if not result['imports']:
        del result['imports']

    # Move enum classes to enums section
    enums_to_move = {}
    for class_name, class_info in list(result['classes'].items()):
        if class_info.get('type') == 'enum':
            enums_to_move[class_name] = {
                'values': class_info.get('values', []),
                'doc': class_info.get('doc', '')
            }
            del result['classes'][class_name]
    if enums_to_move:
        result['enums'] = enums_to_move

    return result


def extract_python_signatures(content: str) -> Dict[str, Dict]:
    """Extract Python function and class signatures with full details for all files."""
    result = {'imports': [], 'functions': {}, 'classes': {}, 'constants': {},
              'variables': [], 'type_aliases': {}, 'enums': {}}
    lines = content.split('\n')
    pat = _get_py_patterns()

    current_class = None
    current_class_indent = -1
    class_stack: List = []
    all_function_names = {m.group(2) for line in lines
                         for m in [re.match(r'^(?:[ \t]*)(async\s+)?def\s+(\w+)\s*\(', line)] if m}
    result['imports'] = _parse_python_imports(lines)
    pending_decorators: List[str] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''"):
            i += 1
            continue
        dec_match = re.match(pat['decorator'], line)
        if dec_match:
            pending_decorators.append(dec_match.group(2))
            i += 1
            continue
        if not current_class and _parse_python_module_level(line, result, pat):
            i += 1
            continue
        class_match = re.match(pat['class'], line)
        if class_match:
            cls_name, cls_indent = _handle_python_class_def(
                class_match, i, lines, result, pending_decorators, class_stack, pat['docstring'])
            if cls_name is not None:
                current_class, current_class_indent = cls_name, cls_indent
            i += 1
            continue
        if current_class and stripped and len(line) - len(line.lstrip()) <= current_class_indent:
            if not stripped.startswith('#'):
                current_class, current_class_indent = None, -1
        if current_class and _parse_python_class_body(line, result, pat, current_class, current_class_indent):
            i += 1
            continue
        if re.match(r'^([ \t]*)(async\s+)?def\s+(\w+)\s*\(', line):
            i = _handle_python_func_def(line, i, lines, result, pat['func'], _SKIP_DUNDER,
                                        pending_decorators, all_function_names, pat['docstring'],
                                        current_class, current_class_indent)
        i += 1

    _cleanup_python_result(result)
    return result


def _cleanup_python_result(result: Dict) -> None:
    """Post-process Python extraction result: remove empties and relocate enums.

    Modifies result dict in-place.
    """
    # Remove empty collections from classes
    for class_name, class_info in result['classes'].items():
        if 'properties' in class_info and not class_info['properties']:
            del class_info['properties']
        if 'class_constants' in class_info and not class_info['class_constants']:
            del class_info['class_constants']
        if 'decorators' in class_info and not class_info['decorators']:
            del class_info['decorators']
        if 'values' in class_info and not class_info['values']:
            del class_info['values']

    # Remove empty module-level collections
    if not result['constants']:
        del result['constants']
    if not result['variables']:
        del result['variables']
    if not result['type_aliases']:
        del result['type_aliases']
    if not result['enums']:
        del result['enums']
    if not result['imports']:
        del result['imports']

    # Move enum classes to enums section
    enums_to_move = {}
    for class_name, class_info in list(result['classes'].items()):
        if class_info.get('type') == 'enum':
            enums_to_move[class_name] = {
                'values': class_info.get('values', []),
                'doc': class_info.get('doc', '')
            }
            del result['classes'][class_name]

    if enums_to_move:
        result['enums'] = enums_to_move


def _parse_js_imports(content: str) -> List[str]:
    """Extract import statements from JavaScript/TypeScript source.

    Handles ES6 import syntax and CommonJS require() calls.

    Returns:
        List of imported module paths.
    """
    imports = []
    # import X from 'Y', import {X} from 'Y', import * as X from 'Y'
    import_pattern = r'import\s+(?:([^{}\s]+)|{([^}]+)}|\*\s+as\s+(\w+))\s+from\s+[\'"]([^\'"]+)[\'"]'
    for match in re.finditer(import_pattern, content):
        default_import, named_imports, namespace_import, module = match.groups()
        if module:
            imports.append(module)

    # require() style imports
    require_pattern = r'(?:const|let|var)\s+(?:{[^}]+}|\w+)\s*=\s*require\s*\([\'"]([^\'"]+)[\'"]\)'
    for match in re.finditer(require_pattern, content):
        imports.append(match.group(1))

    return imports


def _extract_js_function_body_calls(
    text: str, func_match_end: int, all_function_names: Set[str], max_scan: int = 5000
) -> List[str]:
    """Extract function calls from a JS/TS function body.

    Finds the opening brace after the match end, then uses _find_matching_brace_char
    to locate the body, and extracts calls.

    Args:
        text: Source text containing the function
        func_match_end: Position after the regex match for the function signature
        all_function_names: Set of known function names for call detection
        max_scan: Maximum characters to scan for the closing brace

    Returns:
        List of called function names, or empty list.
    """
    brace_pos = text.find('{', func_match_end)
    if brace_pos == -1 or brace_pos - func_match_end >= 100:
        return []

    body_start = brace_pos + 1
    body_end = _find_matching_brace_char(text, body_start, max_scan=max_scan)

    if body_end > body_start:
        func_body = text[body_start:body_end]
        return extract_function_calls_javascript(func_body, all_function_names)
    return []


def _collect_js_function_names(content: str) -> Set[str]:
    """Collect all function names from JS/TS content for call detection."""
    names = set()
    for match in re.finditer(r'(?:async\s+)?function\s+(\w+)', content):
        names.add(match.group(1))
    for match in re.finditer(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(', content):
        names.add(match.group(1))
    for match in re.finditer(r'(\w+)\s*\([^)]*\)\s*{', content):
        names.add(match.group(1))
    return names


def _parse_js_type_aliases(content: str) -> Dict[str, str]:
    """Extract TypeScript type aliases from content."""
    aliases = {}
    pattern = r'(?:export\s+)?type\s+(\w+)\s*=\s*(.+?)(?:;[\s]*(?:(?:export\s+)?(?:type|const|let|var|function|class|interface|enum)\s+|\/\/|$))'
    for match in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
        alias_name, alias_type = match.groups()
        clean_type = ' '.join(alias_type.strip().split())
        if clean_type.startswith('{') and clean_type.count('{') > clean_type.count('}'):
            start_pos = match.start(2)
            brace_count = 0
            end_pos = start_pos
            for i, char in enumerate(content[start_pos:]):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_pos = start_pos + i + 1
                        break
            if end_pos > start_pos:
                clean_type = ' '.join(content[start_pos:end_pos].strip().split())
        aliases[alias_name] = clean_type
    return aliases


def _parse_js_interfaces(content: str) -> Dict[str, Dict]:
    """Extract TypeScript interfaces from content."""
    interfaces = {}
    pattern = r'(?:export\s+)?interface\s+(\w+)(?:\s+extends\s+([^{]+))?\s*{'
    for match in re.finditer(pattern, content):
        interface_name, extends = match.groups()
        info = {}
        if extends:
            info['extends'] = [e.strip() for e in extends.split(',')]
        jsdoc_match = re.search(r'/\*\*\s*\n?\s*\*?\s*([^@\n]+)', content[:match.start()])
        if jsdoc_match:
            info['doc'] = jsdoc_match.group(1).strip()
        interfaces[interface_name] = info
    return interfaces


def _parse_js_enums(content: str) -> Dict[str, Dict]:
    """Extract TypeScript enums from content."""
    enums = {}
    pattern = r'(?:export\s+)?enum\s+(\w+)\s*{'
    for match in re.finditer(pattern, content):
        enum_name = match.group(1)
        start_pos = match.end()
        end_pos = _find_matching_brace_char(content, start_pos)
        enum_body = content[start_pos:end_pos]
        values = re.findall(r'(\w+)\s*(?:=\s*[^,\n]+)?', enum_body)
        enums[enum_name] = {'values': values}
    return enums


def _parse_js_constants_and_vars(content: str) -> Tuple[Dict[str, str], List[str]]:
    """Extract module-level constants and variables from JS/TS content."""
    constants = {}
    variables = []
    const_pattern = r'(?:export\s+)?const\s+([A-Z_][A-Z0-9_]*)\s*=\s*([^;]+)'
    for match in re.finditer(const_pattern, content):
        const_name, const_value = match.groups()
        constants[const_name] = _infer_const_type(const_value.strip())
    var_pattern = r'(?:export\s+)?(?:let|const)\s+([a-z]\w*)\s*(?::\s*\w+)?\s*='
    for match in re.finditer(var_pattern, content):
        var_name = match.group(1)
        if var_name not in variables:
            variables.append(var_name)
    return constants, variables


def _parse_js_classes(
    content: str, pos_to_line, all_function_names: Set[str]
) -> Tuple[Dict[str, Dict], Dict[str, Tuple[int, int]]]:
    """Parse all JS/TS class declarations, methods, and static constants.

    Returns:
        Tuple of (classes dict, class_positions dict).
    """
    class_pattern = r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?'
    class_positions = {}
    classes = {}

    for match in re.finditer(class_pattern, content):
        class_name, extends = match.groups()
        start_pos = match.start()
        brace_count = 0
        in_class = False
        end_pos = start_pos
        for i in range(match.end(), len(content)):
            if content[i] == '{':
                if not in_class:
                    in_class = True
                brace_count += 1
            elif content[i] == '}':
                brace_count -= 1
                if brace_count == 0 and in_class:
                    end_pos = i
                    break
        class_positions[class_name] = (start_pos, end_pos)
        class_info = {'line': pos_to_line(start_pos), 'methods': {}, 'static_constants': {}}
        if extends:
            class_info['extends'] = extends
            if extends.lower() in ['error', 'exception'] or 'error' in extends.lower():
                class_info['type'] = 'exception'
        jsdoc_match = re.search(r'/\*\*\s*\n?\s*\*?\s*([^@\n]+)', content[:start_pos])
        if jsdoc_match:
            class_info['doc'] = jsdoc_match.group(1).strip()
        classes[class_name] = class_info

    # Extract methods and static constants from each class
    method_patterns = [
        r'^\s*(async\s+)?(\w+)\s*\((.*?)\)\s*(?::\s*([^{]+))?\s*{',
        r'^\s*(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*(?::\s*([^=]+))?\s*=>',
        r'^\s*(constructor)\s*\(([^)]*)\)\s*{',
    ]
    for class_name, (start, end) in class_positions.items():
        class_content = content[start:end]
        for pattern in method_patterns:
            for match in re.finditer(pattern, class_content, re.MULTILINE):
                if 'constructor' in pattern:
                    method_name, params, return_type = '__init__', match.group(2), None
                elif '=' in pattern:
                    method_name, params, return_type = match.group(1), match.group(2), match.group(3)
                else:
                    method_name, params, return_type = match.group(2), match.group(3), match.group(4)
                if method_name in ['get', 'set', 'if', 'for', 'while', 'switch', 'catch', 'try']:
                    continue
                method_info = {'line': pos_to_line(start + match.start())}
                params = re.sub(r'\s+', ' ', params).strip()
                signature = f"({params})"
                if return_type:
                    signature += f": {return_type.strip()}"
                if 'async' in str(match.group(0)):
                    signature = "async " + signature
                calls = _extract_js_function_body_calls(class_content, match.end(), all_function_names, max_scan=3000)
                if calls:
                    method_info['calls'] = calls
                method_info['signature'] = signature
                classes[class_name]['methods'][method_name] = method_info
        static_const_pattern = r'static\s+([A-Z_][A-Z0-9_]*)\s*=\s*([^;]+)'
        for match in re.finditer(static_const_pattern, class_content):
            const_name, const_value = match.groups()
            classes[class_name]['static_constants'][const_name] = _infer_const_type(const_value.strip())

    return classes, class_positions


def _parse_js_standalone_functions(
    content: str, class_positions: Dict[str, Tuple[int, int]],
    pos_to_line, all_function_names: Set[str]
) -> Dict[str, Any]:
    """Parse standalone (non-class) JS/TS function declarations and arrow functions."""
    functions = {}
    func_patterns = [
        r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*(?:<[^>]+>)?\s*\(([^)]*)\)(?:\s*:\s*([^{]+))?',
        r'(?:export\s+)?const\s+(\w+)\s*(?::\s*[^=]+)?\s*=\s*(?:async\s+)?\(([^)]*)\)\s*(?::\s*([^=]+))?\s*=>',
    ]
    for pattern in func_patterns:
        for match in re.finditer(pattern, content):
            func_name = match.group(1)
            params = match.group(2) if match.lastindex >= 2 else ''
            return_type = match.group(3) if match.lastindex >= 3 else None
            func_pos = match.start()
            inside_class = any(s <= func_pos <= e for _, (s, e) in class_positions.items())
            if not inside_class:
                func_info = {'line': pos_to_line(func_pos)}
                params = re.sub(r'\s+', ' ', params).strip()
                signature = f"({params})"
                if return_type:
                    signature += f": {return_type.strip()}"
                if 'async' in match.group(0):
                    signature = "async " + signature
                calls = _extract_js_function_body_calls(content, match.end(), all_function_names, max_scan=5000)
                if calls:
                    func_info['calls'] = calls
                func_info['signature'] = signature
                functions[func_name] = func_info
    return functions


def extract_javascript_signatures(content: str) -> Dict[str, Any]:
    """Extract JavaScript/TypeScript function and class signatures with full details."""
    result = {
        'imports': [],
        'functions': {},
        'classes': {},
        'constants': {},
        'variables': [],
        'type_aliases': {},
        'interfaces': {},
        'enums': {},
    }

    def pos_to_line(pos: int) -> int:
        return content[:pos].count('\n') + 1

    all_function_names = _collect_js_function_names(content)
    result['imports'] = _parse_js_imports(content)
    result['type_aliases'] = _parse_js_type_aliases(content)
    result['interfaces'] = _parse_js_interfaces(content)
    result['enums'] = _parse_js_enums(content)
    result['constants'], result['variables'] = _parse_js_constants_and_vars(content)
    result['classes'], class_positions = _parse_js_classes(content, pos_to_line, all_function_names)
    result['functions'] = _parse_js_standalone_functions(
        content, class_positions, pos_to_line, all_function_names
    )

    _cleanup_js_result(result)
    return result


def _cleanup_js_result(result: Dict) -> None:
    """Post-process JavaScript extraction result: remove empty collections.

    Modifies result dict in-place.
    """
    for class_name, class_info in result['classes'].items():
        if 'static_constants' in class_info and not class_info['static_constants']:
            del class_info['static_constants']

    if not result['constants']:
        del result['constants']
    if not result['variables']:
        del result['variables']
    if not result['imports']:
        del result['imports']
    if not result['type_aliases']:
        del result['type_aliases']
    if not result['interfaces']:
        del result['interfaces']
    if not result['enums']:
        del result['enums']


def extract_function_calls_shell(body: str, all_functions: Set[str]) -> List[str]:
    """Extract function calls from shell script body."""
    calls = set()
    
    # In shell, functions are called just by name (no parentheses)
    # We need to be careful to avoid false positives
    for func_name in all_functions:
        # Look for function name at start of line or after common shell operators
        patterns = [
            rf'^\s*{func_name}\b',  # Start of line
            rf'[;&|]\s*{func_name}\b',  # After operators
            rf'\$\({func_name}\b',  # Command substitution
            rf'`{func_name}\b',  # Backtick substitution
        ]
        for pattern in patterns:
            if re.search(pattern, body, re.MULTILINE):
                calls.add(func_name)
                break
    
    return sorted(list(calls))


def _parse_shell_function(func_name: str, doc: Optional[str], lines: List[str], start_line_idx: int, all_function_names: Set[str]) -> Any:
    """Parse a shell function body, extracting params, calls, and signature.

    Shared implementation for both 'name() {' and 'function name {' styles.
    """
    # Try to find parameters from the function body
    params = []
    brace_count = 0
    in_func_body = False

    # Look for $1, $2, etc. usage in the function body only
    for j in range(start_line_idx + 1, min(start_line_idx + 20, len(lines))):
        line_content = lines[j].strip()

        if '{' in line_content:
            brace_count += line_content.count('{')
            in_func_body = True
        if '}' in line_content:
            brace_count -= line_content.count('}')
            if brace_count <= 0:
                break

        if in_func_body:
            param_matches = re.findall(r'\$(\d+)', lines[j])
            for p in param_matches:
                param_num = int(p)
                if param_num > 0 and param_num not in params:
                    params.append(param_num)

    # Build signature
    if params:
        max_param = max(params)
        param_list = ' '.join(f'$1' if j == 1 else f'${{{j}}}' for j in range(1, max_param + 1))
        signature = f"({param_list})"
    else:
        signature = "()"

    # Extract function body for call analysis
    func_body_lines = []
    brace_count = 0
    in_func_body = False
    for j in range(start_line_idx + 1, len(lines)):
        line_content = lines[j]
        if '{' in line_content:
            brace_count += line_content.count('{')
            in_func_body = True
        if in_func_body:
            func_body_lines.append(line_content)
        if '}' in line_content:
            brace_count -= line_content.count('}')
            if brace_count <= 0:
                break

    func_info = {}
    if func_body_lines:
        func_body = '\n'.join(func_body_lines)
        calls = extract_function_calls_shell(func_body, all_function_names)
        if calls:
            func_info['calls'] = calls

    if doc:
        func_info['doc'] = doc

    if func_info:
        func_info['signature'] = signature
    else:
        func_info = signature

    return func_info


def _collect_shell_function_names(lines: List[str]) -> Set[str]:
    """Collect all function names from shell script lines."""
    names = set()
    for line in lines:
        match1 = re.match(r'^(\w+)\s*\(\)\s*\{?', line)
        if match1:
            names.add(match1.group(1))
        match2 = re.match(r'^function\s+(\w+)\s*\{?', line)
        if match2:
            names.add(match2.group(1))
    return names


def _parse_shell_source_line(stripped: str, sources: List[str]) -> bool:
    """Try to parse a source/dot include from a shell line. Returns True if matched."""
    source_patterns = [
        r'^(?:source|\.)\s+([\'"])([^\'"]+)\1',
        r'^(?:source|\.)\s+(\$\([^)]+\)[^\s]*)',
        r'^(?:source|\.)\s+([^\s]+)',
    ]
    for pattern in source_patterns:
        match = re.match(pattern, stripped)
        if match:
            sourced_file = match.group(2) if len(match.groups()) == 2 else match.group(1)
            sourced_file = sourced_file.strip()
            if sourced_file and sourced_file not in sources:
                sources.append(sourced_file)
            return True
    return False


def extract_shell_signatures(content: str) -> Dict[str, Any]:
    """Extract shell script function signatures and structure."""
    result = {'functions': {}, 'variables': [], 'exports': {}, 'sources': []}
    lines = content.split('\n')
    all_function_names = _collect_shell_function_names(lines)

    func_pattern1 = r'^(\w+)\s*\(\)\s*\{?'
    func_pattern2 = r'^function\s+(\w+)\s*\{?'
    export_pattern = r'^export\s+([A-Z_][A-Z0-9_]*)(=(.*))?'
    var_pattern = r'^([A-Z_][A-Z0-9_]*)=(.+)$'

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith('#!'):
            continue

        # Check for function definition
        match = re.match(func_pattern1, stripped) or re.match(func_pattern2, stripped)
        if match:
            func_name = match.group(1)
            doc = None
            if i > 0 and lines[i-1].strip().startswith('#'):
                doc = lines[i-1].strip()[1:].strip()
            result['functions'][func_name] = _parse_shell_function(
                func_name, doc, lines, i, all_function_names
            )
            continue

        # Check for exports
        match = re.match(export_pattern, stripped)
        if match:
            var_name = match.group(1)
            var_value = match.group(3) if match.group(3) else None
            if var_value:
                if var_value.startswith(("'", '"')):
                    var_type = 'str'
                elif var_value.isdigit():
                    var_type = 'number'
                else:
                    var_type = 'value'
                result['exports'][var_name] = var_type
            continue

        # Check for regular variables (uppercase)
        match = re.match(var_pattern, stripped)
        if match:
            var_name = match.group(1)
            if var_name not in result['exports'] and var_name not in result['variables']:
                result['variables'].append(var_name)
            continue

        # Check for source/dot includes
        _parse_shell_source_line(stripped, result['sources'])

    # Clean up empty collections
    if not result['variables']:
        del result['variables']
    if not result['exports']:
        del result['exports']
    if not result['sources']:
        del result['sources']

    return result


def extract_markdown_structure(file_path: Path) -> Dict[str, List[str]]:
    """Extract headers and architectural hints from markdown files."""
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
    except (OSError, UnicodeDecodeError):
        return {'sections': [], 'architecture_hints': []}
    
    # Extract headers (up to level 3)
    headers = re.findall(r'^#{1,3}\s+(.+)$', content[:5000], re.MULTILINE)  # Only scan first 5KB
    
    # Look for architectural hints
    arch_patterns = [
        r'(?:located?|found?|stored?)\s+in\s+`?([\w\-\./]+)`?',
        r'`?([\w\-\./]+)`?\s+(?:contains?|houses?|holds?)',
        r'(?:see|check|look)\s+(?:in\s+)?`?([\w\-\./]+)`?\s+for',
        r'(?:file|module|component)\s+`?([\w\-\./]+)`?',
    ]
    
    hints = set()
    for pattern in arch_patterns:
        matches = re.findall(pattern, content[:5000], re.IGNORECASE)
        for match in matches:
            if '/' in match and not match.startswith('http'):
                hints.add(match)
    
    return {
        'sections': headers[:10],  # Limit to prevent bloat
        'architecture_hints': list(hints)[:5]
    }


def infer_file_purpose(file_path: Path) -> Optional[str]:
    """Infer the purpose of a file from its name and location."""
    name = file_path.stem.lower()
    
    # Common file purposes
    if name in ['index', 'main', 'app']:
        return 'Application entry point'
    elif 'test' in name or 'spec' in name:
        return 'Test file'
    elif 'config' in name or 'settings' in name:
        return 'Configuration'
    elif 'route' in name:
        return 'Route definitions'
    elif 'model' in name:
        return 'Data model'
    elif 'util' in name or 'helper' in name:
        return 'Utility functions'
    elif 'middleware' in name:
        return 'Middleware'
    
    return None


def infer_directory_purpose(path: Path, files_within: List[str]) -> Optional[str]:
    """Infer directory purpose from naming patterns and contents."""
    dir_name = path.name.lower()
    
    # Check exact matches first
    if dir_name in DIRECTORY_PURPOSES:
        return DIRECTORY_PURPOSES[dir_name]
    
    # Check if directory name contains key patterns
    for pattern, purpose in DIRECTORY_PURPOSES.items():
        if pattern in dir_name:
            return purpose
    
    # Infer from contents
    if files_within:
        # Check for test files
        if any('test' in f.lower() or 'spec' in f.lower() for f in files_within):
            return 'Test files and test utilities'
        
        # Check for specific file patterns
        if any('model' in f.lower() for f in files_within):
            return 'Data models and schemas'
        elif any('route' in f.lower() or 'endpoint' in f.lower() for f in files_within):
            return 'API routes and endpoints'
        elif any('component' in f.lower() for f in files_within):
            return 'UI components'
    
    return None


def get_language_name(extension: str) -> str:
    """Get readable language name from extension."""
    if extension in PARSEABLE_LANGUAGES:
        return PARSEABLE_LANGUAGES[extension]
    return extension[1:] if extension else 'unknown'


def build_import_map(project_root: Path) -> Dict[str, str]:
    """Build a map from Python dotted module names to relative file paths.

    Scans the project for .py files and maps:
    - 'pkg.module' -> 'pkg/module.py'
    - 'pkg' -> 'pkg/__init__.py' (if exists)

    Only handles static, deterministic mappings. Does NOT handle:
    - Dynamic imports (importlib)
    - Runtime sys.path manipulation
    - Namespace packages without __init__.py

    Args:
        project_root: Absolute path to project root.

    Returns:
        Dict mapping dotted module names to relative file paths.
    """
    import_map: Dict[str, str] = {}
    project_root = Path(project_root)

    # Try git ls-files first, fall back to rglob
    git_files = get_git_files(project_root)
    if git_files is not None:
        py_files = [f for f in git_files if f.suffix == '.py']
    else:
        py_files = list(project_root.rglob('*.py'))

    for py_file in py_files:
        try:
            rel = py_file.relative_to(project_root)
        except ValueError:
            continue

        rel_str = str(rel).replace(os.sep, '/')

        # Convert path to dotted module name: src/utils/helpers.py -> src.utils.helpers
        dotted = rel_str.replace('/', '.').removesuffix('.py')

        import_map[dotted] = rel_str

        # For __init__.py, also map the package name (without .__init__)
        if rel.name == '__init__.py':
            pkg_dotted = dotted.removesuffix('.__init__')
            if pkg_dotted:
                import_map[pkg_dotted] = rel_str

    return import_map


def resolve_cross_file_edges(index: Dict, import_map: Dict[str, str]) -> List[List[str]]:
    """Resolve cross-file call edges using the import map.

    For each file in the index, checks its imports against the import map.
    When an import resolves to another indexed file, creates cross-file edges
    by matching function calls against the target file's exported functions.

    Args:
        index: The full project index dict (with 'files' key).
        import_map: Output of build_import_map().

    Returns:
        List of [source, target, relation_type] triples.
        Example: [["src/a.py:func_x", "src/b.py:func_y", "call"]]
    """
    edges: List[List[str]] = []
    files = index.get('files', {})

    # Pre-build a map of target_file -> set of function names for fast lookup
    file_functions: Dict[str, Set[str]] = {}
    for fpath, finfo in files.items():
        if not isinstance(finfo, dict):
            continue
        func_names: Set[str] = set()
        for fname in finfo.get('functions', {}):
            func_names.add(fname)
        for cname, cdata in finfo.get('classes', {}).items():
            if isinstance(cdata, dict):
                for mname in cdata.get('methods', {}):
                    func_names.add(mname)
        if func_names:
            file_functions[fpath] = func_names

    for source_path, source_info in files.items():
        if not isinstance(source_info, dict):
            continue

        source_imports = source_info.get('imports', [])
        if not source_imports:
            continue

        # Resolve each import to a target file
        resolved_targets: Set[str] = set()
        for imp in source_imports:
            # Try direct match in import_map
            target = import_map.get(imp)
            if target and target in files and target != source_path:
                resolved_targets.add(target)

        if not resolved_targets:
            continue

        # Collect all calls from this file's functions and methods
        caller_calls: List[Tuple[str, List[str]]] = []

        for fname, fdata in source_info.get('functions', {}).items():
            if isinstance(fdata, dict) and fdata.get('calls'):
                caller_calls.append((f"{source_path}:{fname}", fdata['calls']))

        for cname, cdata in source_info.get('classes', {}).items():
            if isinstance(cdata, dict):
                for mname, mdata in cdata.get('methods', {}).items():
                    if isinstance(mdata, dict) and mdata.get('calls'):
                        caller_calls.append(
                            (f"{source_path}:{cname}.{mname}", mdata['calls'])
                        )

        # Match calls against target file functions
        for caller_id, calls in caller_calls:
            for target_path in resolved_targets:
                target_funcs = file_functions.get(target_path, set())
                for call_name in calls:
                    if call_name in target_funcs:
                        edges.append([caller_id, f"{target_path}:{call_name}", "call"])

    return edges


# Parser registry: maps file extensions to parser functions
# Populated after parser function definitions via register_parsers()
PARSER_REGISTRY: Dict[str, any] = {}


def register_parsers() -> None:
    """Register all parser functions. Called at module load time."""
    global PARSER_REGISTRY
    PARSER_REGISTRY = {
        '.py': extract_python_signatures,
        '.js': extract_javascript_signatures,
        '.jsx': extract_javascript_signatures,
        '.ts': extract_javascript_signatures,
        '.tsx': extract_javascript_signatures,
        '.sh': extract_shell_signatures,
        '.bash': extract_shell_signatures,
    }


def parse_file(content: str, extension: str) -> Optional[Dict]:
    """Parse a file using the registered parser for its extension.

    Returns parsed result dict or None if no parser registered.
    For Python files, uses AST parser by default (controlled by V2_AST_PARSER env var).
    """
    parser = PARSER_REGISTRY.get(extension)
    if parser is None:
        return None
    # Feature flag: V2_AST_PARSER controls Python parser selection at call time
    if extension == '.py' and os.environ.get('V2_AST_PARSER', '1') != '0':
        return extract_python_signatures_ast(content)
    return parser(content)


# Global cache for gitignore patterns
_gitignore_cache = {}


def parse_gitignore(gitignore_path: Path) -> List[str]:
    """Parse a .gitignore file and return list of patterns."""
    if not gitignore_path.exists():
        return []
    
    patterns = []
    try:
        with open(gitignore_path, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                patterns.append(line)
    except (OSError, UnicodeDecodeError):
        pass

    return patterns


def load_gitignore_patterns(root_path: Path) -> Set[str]:
    """Load all gitignore patterns from project root and merge with defaults."""
    # Use cached patterns if available
    cache_key = str(root_path)
    if cache_key in _gitignore_cache:
        return _gitignore_cache[cache_key]
    
    # Start with default ignore patterns
    patterns = set(IGNORE_DIRS)
    
    # Add patterns from .gitignore in project root
    gitignore_path = root_path / '.gitignore'
    if gitignore_path.exists():
        for pattern in parse_gitignore(gitignore_path):
            # Handle negations (!) later if needed
            if not pattern.startswith('!'):
                patterns.add(pattern)
    
    # Cache the patterns
    _gitignore_cache[cache_key] = patterns
    return patterns


def matches_gitignore_pattern(path: Path, patterns: Set[str], root_path: Path) -> bool:
    """Check if a path matches any gitignore pattern."""
    # Get relative path from root
    try:
        rel_path = path.relative_to(root_path)
    except ValueError:
        # Path is not relative to root
        return False
    
    # Convert to string for pattern matching
    path_str = str(rel_path)
    path_parts = rel_path.parts
    
    for pattern in patterns:
        # Check if any parent directory matches the pattern
        # Strip trailing slash for directory patterns
        clean_pattern = pattern.rstrip('/')
        for part in path_parts:
            if part == clean_pattern or fnmatch.fnmatch(part, clean_pattern):
                return True
        
        # Check full path patterns
        if '/' in pattern:
            # Pattern includes directory separator
            if fnmatch.fnmatch(path_str, pattern):
                return True
            # Also check without leading slash
            if pattern.startswith('/') and fnmatch.fnmatch(path_str, pattern[1:]):
                return True
        else:
            # Pattern is just a filename/directory name
            # Check if the filename matches
            if fnmatch.fnmatch(path.name, pattern):
                return True
            # Check if it matches the full relative path
            if fnmatch.fnmatch(path_str, pattern):
                return True
            # Check with wildcards
            if fnmatch.fnmatch(path_str, f'**/{pattern}'):
                return True
    
    return False


def should_index_file(path: Path, root_path: Path = None) -> bool:
    """Check if we should index this file."""
    # Must be a code or markdown file
    if not (path.suffix in CODE_EXTENSIONS or path.suffix in MARKDOWN_EXTENSIONS):
        return False
    
    # Skip if in hardcoded ignored directory (for safety)
    for part in path.parts:
        if part in IGNORE_DIRS:
            return False
    
    # If root_path provided, check gitignore patterns
    if root_path:
        patterns = load_gitignore_patterns(root_path)
        if matches_gitignore_pattern(path, patterns, root_path):
            return False
    
    return True


def get_git_files(root_path: Path) -> Optional[List[Path]]:
    """Get list of files tracked by git (respects .gitignore).
    Returns None if not a git repository or git command fails."""
    try:
        import subprocess
        
        # Run git ls-files to get tracked and untracked files that aren't ignored
        result = subprocess.run(
            ['git', 'ls-files', '--cached', '--others', '--exclude-standard'],
            cwd=str(root_path),
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            files = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    file_path = root_path / line
                    # Only include actual files (not directories)
                    if file_path.is_file():
                        files.append(file_path)
            return files
        else:
            return None
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        # Git not available or command failed
        return None


# Populate the parser registry at module load time (after all parsers are defined)
register_parsers()