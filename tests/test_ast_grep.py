"""Tests for ast-grep integration (mocked subprocess)."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


def test_sg_not_installed():
    """Returns None when sg is not on PATH."""
    from index_utils import extract_signatures_via_sg
    with patch('shutil.which', return_value=None):
        result = extract_signatures_via_sg('func main() {}', 'go')
        assert result is None


def test_sg_go_function():
    """Extracts Go function with mocked sg output."""
    from index_utils import extract_signatures_via_sg
    mock_output = json.dumps([{
        'metaVariables': {
            'single': {'NAME': {'text': 'main'}},
            'multi': {'PARAMS': ''}
        },
        'range': {'start': {'line': 0}}
    }])
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = mock_output

    with patch('shutil.which', return_value='/usr/bin/sg'), \
         patch('subprocess.run', return_value=mock_proc):
        result = extract_signatures_via_sg('func main() {\n\tfmt.Println("hello")\n}', 'go')
        assert result is not None
        assert 'main' in result['functions']


def test_sg_unsupported_language():
    """Returns None for unsupported language."""
    from index_utils import extract_signatures_via_sg
    with patch('shutil.which', return_value='/usr/bin/sg'):
        result = extract_signatures_via_sg('code here', 'cobol')
        assert result is None


def test_sg_timeout():
    """Returns empty result on timeout."""
    from index_utils import extract_signatures_via_sg
    import subprocess

    with patch('shutil.which', return_value='/usr/bin/sg'), \
         patch('subprocess.run', side_effect=subprocess.TimeoutExpired('sg', 10)):
        result = extract_signatures_via_sg('fn main() {}', 'rust')
        # Should return None (no functions extracted)
        assert result is None


def test_sg_empty_output():
    """Returns None when sg produces no matches."""
    from index_utils import extract_signatures_via_sg
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = '[]'

    with patch('shutil.which', return_value='/usr/bin/sg'), \
         patch('subprocess.run', return_value=mock_proc):
        result = extract_signatures_via_sg('// empty file', 'java')
        assert result is None


def test_registry_includes_sg_when_available():
    """PARSER_REGISTRY includes .go/.rs/.java/.rb when sg is available."""
    from index_utils import PARSER_REGISTRY
    import shutil
    if shutil.which('sg'):
        assert '.go' in PARSER_REGISTRY
        assert '.rs' in PARSER_REGISTRY
    # If sg not installed, these should NOT be in registry
    else:
        assert '.go' not in PARSER_REGISTRY
