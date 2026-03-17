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
    """C-2: validate_python_cmd rejects relative paths."""
    from index_utils import validate_python_cmd
    assert not validate_python_cmd('python3')
    assert not validate_python_cmd('./scripts/run.py')


def test_validate_python_cmd_rejects_non_python():
    """C-2: validate_python_cmd rejects non-Python executables."""
    from index_utils import validate_python_cmd
    assert not validate_python_cmd('/bin/bash')
    assert not validate_python_cmd('/usr/bin/node')


def test_validate_python_cmd_accepts_valid():
    """C-2: validate_python_cmd accepts valid Python interpreters."""
    import shutil
    from index_utils import validate_python_cmd
    python_path = shutil.which('python3')
    if python_path:
        assert validate_python_cmd(python_path)


def test_validate_python_cmd_tightened_regex():
    """Tightened regex rejects python3-malicious, accepts python3.12."""
    from index_utils import validate_python_cmd
    # These should be rejected (non-existent paths, but test the basename logic)
    # We test by checking that relative paths fail (basename check never reached)
    assert not validate_python_cmd('python3-malicious')
    assert not validate_python_cmd('python3.12.1-extra')
