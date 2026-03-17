"""Security tests verifying vulnerability fixes from deep dive findings C-1, C-2, H-1, H-2, H-3."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


def test_no_hardcoded_ips():
    """C-1, H-1: No hardcoded IP addresses in source code."""
    source = Path(__file__).parent.parent / 'scripts' / 'i_flag_hook.py'
    content = source.read_text()
    assert '10.211.55' not in content, "Hardcoded Parallels VM IP found"
    assert '192.168.1.1' not in content, "Hardcoded router IP found"


def test_no_author_paths():
    """H-3: No author-specific paths in source code."""
    source = Path(__file__).parent.parent / 'scripts' / 'i_flag_hook.py'
    content = source.read_text()
    assert 'ericbuess' not in content, "Author-specific username found"
    assert 'claude-ericbuess' not in content, "Author-specific directory found"


def test_no_os_chdir():
    """H-2: No os.chdir() calls in stop_hook.py."""
    source = Path(__file__).parent.parent / 'scripts' / 'stop_hook.py'
    content = source.read_text()
    assert 'os.chdir' not in content, "Global CWD mutation found"


def test_validate_python_cmd_rejects_relative():
    """C-2: _validate_python_cmd rejects relative paths."""
    from i_flag_hook import _validate_python_cmd
    assert not _validate_python_cmd('python3')
    assert not _validate_python_cmd('./scripts/run.py')


def test_validate_python_cmd_rejects_non_python():
    """C-2: _validate_python_cmd rejects non-Python executables."""
    from i_flag_hook import _validate_python_cmd
    assert not _validate_python_cmd('/bin/bash')
    assert not _validate_python_cmd('/usr/bin/node')


def test_validate_python_cmd_accepts_valid():
    """C-2: _validate_python_cmd accepts valid Python interpreters."""
    import shutil
    from i_flag_hook import _validate_python_cmd
    python_path = shutil.which('python3')
    if python_path:
        assert _validate_python_cmd(python_path)
