"""Quality tests verifying fixes from deep dive findings M-2, Q-1, Q-2."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


def test_no_bare_excepts():
    """M-2: No bare except: blocks in any Python source file."""
    import re
    scripts_dir = Path(__file__).parent.parent / 'scripts'
    for py_file in scripts_dir.glob('*.py'):
        content = py_file.read_text()
        # Find bare 'except:' that is NOT 'except Something:' or 'except (A, B):'
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped == 'except:':
                assert False, f"Bare except: found in {py_file.name}:{i}"


def test_no_dead_build_call_graph():
    """Q-1: build_call_graph function removed from index_utils.py."""
    source = Path(__file__).parent.parent / 'scripts' / 'index_utils.py'
    content = source.read_text()
    assert 'def build_call_graph' not in content, "Dead function still present"


def test_no_vestigial_call_graph_key():
    """Q-1: call_graph key removed from parser return dicts."""
    source = Path(__file__).parent.parent / 'scripts' / 'index_utils.py'
    content = source.read_text()
    assert "'call_graph'" not in content, "Vestigial call_graph key still present"
    assert '"call_graph"' not in content, "Vestigial call_graph key still present"


def test_shell_parser_not_duplicated():
    """Q-2: Shell parser uses shared _parse_shell_function helper."""
    source = Path(__file__).parent.parent / 'scripts' / 'index_utils.py'
    content = source.read_text()
    assert 'def _parse_shell_function' in content, "Shared helper not found"
    # The two original blocks each had their own brace_count = 0 init
    # After dedup, there should be only ONE brace counting section (inside the helper)
    # Count occurrences of the characteristic duplicated pattern
    param_list_count = content.count("param_list = ' '.join")
    assert param_list_count == 1, f"Expected 1 param_list construction, found {param_list_count} (duplication remains)"


def test_shell_parser_still_works():
    """Q-2: Shell parser still produces correct output after deduplication."""
    from index_utils import extract_shell_signatures

    source = '''#!/bin/bash
# Greet the user
greet() {
    echo "Hello $1"
}

function cleanup {
    rm -rf "$1"
}
'''
    result = extract_shell_signatures(source)
    funcs = result.get('functions', {})
    assert 'greet' in funcs, f"greet not found in {list(funcs)}"
    assert 'cleanup' in funcs, f"cleanup not found in {list(funcs)}"
