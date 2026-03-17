"""Tests for atomic write functionality."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


def test_atomic_write_json_in_index_utils():
    """atomic_write_json uses atomic write (temp file + rename) in index_utils.py."""
    source = Path(__file__).parent.parent / 'scripts' / 'index_utils.py'
    content = source.read_text()
    assert 'os.replace' in content, "Atomic os.replace not found in index_utils.py"
    assert 'mkstemp' in content, "tempfile.mkstemp not found in index_utils.py"


def test_project_index_uses_atomic_write_json():
    """project_index.py uses the shared atomic_write_json utility."""
    source = Path(__file__).parent.parent / 'scripts' / 'project_index.py'
    content = source.read_text()
    assert 'atomic_write_json' in content, "atomic_write_json not imported in project_index.py"


def test_hook_uses_atomic_write_json():
    """i_flag_hook.py uses the shared atomic_write_json utility."""
    source = Path(__file__).parent.parent / 'scripts' / 'i_flag_hook.py'
    content = source.read_text()
    assert 'atomic_write_json' in content, "atomic_write_json not imported in i_flag_hook.py"


def test_hook_guards_fcntl_import():
    """i_flag_hook.py guards fcntl import for cross-platform compatibility."""
    source = Path(__file__).parent.parent / 'scripts' / 'i_flag_hook.py'
    content = source.read_text()
    assert 'HAS_FCNTL' in content, "HAS_FCNTL guard not found in i_flag_hook.py"
    assert 'import fcntl' in content, "fcntl import not found in i_flag_hook.py"


def test_atomic_write_has_cleanup():
    """atomic_write_json in index_utils.py includes try/except cleanup for temp files."""
    source = Path(__file__).parent.parent / 'scripts' / 'index_utils.py'
    content = source.read_text()
    assert 'os.unlink' in content, "Atomic write missing cleanup (os.unlink)"
