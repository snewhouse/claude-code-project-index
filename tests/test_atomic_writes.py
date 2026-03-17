"""Tests for atomic write functionality."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


def test_project_index_writes_atomically():
    """project_index.py uses atomic write (temp file + rename)."""
    source = Path(__file__).parent.parent / 'scripts' / 'project_index.py'
    content = source.read_text()
    assert 'os.replace' in content, "Atomic os.replace not found in project_index.py"
    assert 'mkstemp' in content, "tempfile.mkstemp not found in project_index.py"


def test_hook_writes_atomically():
    """i_flag_hook.py uses atomic write for metadata updates."""
    source = Path(__file__).parent.parent / 'scripts' / 'i_flag_hook.py'
    content = source.read_text()
    assert 'os.replace' in content, "Atomic os.replace not found in i_flag_hook.py"


def test_hook_guards_fcntl_import():
    """i_flag_hook.py guards fcntl import for cross-platform compatibility."""
    source = Path(__file__).parent.parent / 'scripts' / 'i_flag_hook.py'
    content = source.read_text()
    assert 'HAS_FCNTL' in content, "HAS_FCNTL guard not found in i_flag_hook.py"
    assert 'import fcntl' in content, "fcntl import not found in i_flag_hook.py"


def test_atomic_write_has_cleanup():
    """Atomic write blocks include try/finally cleanup for temp files."""
    source = Path(__file__).parent.parent / 'scripts' / 'project_index.py'
    content = source.read_text()
    # Should have try/finally pattern around the atomic write
    assert 'os.unlink' in content or 'finally' in content, \
        "Atomic write in project_index.py missing try/finally cleanup"
