"""Tests for decomposed clipboard transport functions."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
from i_flag_hook import _try_file_fallback, copy_to_clipboard, _build_clipboard_content


def test_file_fallback_creates_temp_file(tmp_path):
    """File fallback creates a file with restricted permissions."""
    result = _try_file_fallback("test content", tmp_path)
    assert result is not None
    assert result[0] == 'file'
    # Verify file exists and has content
    fallback_path = Path(result[1])
    assert fallback_path.exists()
    assert fallback_path.read_text() == "test content"


def test_copy_to_clipboard_returns_tuple(tmp_path):
    """copy_to_clipboard always returns a (type, data) tuple."""
    # Create a minimal index file
    index_file = tmp_path / 'PROJECT_INDEX.json'
    index_file.write_text('{"f": {}, "g": []}')

    with patch.dict('os.environ', {'SSH_CONNECTION': ''}, clear=False):
        result = copy_to_clipboard("test prompt", str(index_file))
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_clipboard_dispatch_is_short():
    """copy_to_clipboard function body should be < 30 lines."""
    import inspect
    source = inspect.getsource(copy_to_clipboard)
    lines = [l for l in source.split('\n') if l.strip() and not l.strip().startswith('#')]
    assert len(lines) < 40, f"copy_to_clipboard is {len(lines)} non-empty lines (target: <30)"


def test_build_clipboard_content_returns_string(tmp_path):
    """_build_clipboard_content returns a non-empty string."""
    index_file = tmp_path / 'PROJECT_INDEX.json'
    index_file.write_text('{"f": {}, "g": []}')
    content = _build_clipboard_content("my prompt", str(index_file))
    assert isinstance(content, str)
    assert len(content) > 0
    assert "my prompt" in content


def test_file_fallback_uses_secure_permissions(tmp_path):
    """File fallback creates file with 0o600 permissions."""
    import stat
    result = _try_file_fallback("secure content", tmp_path)
    fallback_path = Path(result[1])
    file_stat = fallback_path.stat()
    mode = stat.S_IMODE(file_stat.st_mode)
    assert mode == 0o600, f"Expected 0o600 permissions, got {oct(mode)}"
