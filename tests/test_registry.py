"""Tests for parser registry and architecture improvements."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


def test_parser_registry_has_python():
    """Parser registry maps .py to extract_python_signatures."""
    from index_utils import PARSER_REGISTRY
    assert '.py' in PARSER_REGISTRY
    assert PARSER_REGISTRY['.py'].__name__ == 'extract_python_signatures'


def test_parser_registry_has_javascript():
    """Parser registry maps .js and .ts."""
    from index_utils import PARSER_REGISTRY
    assert '.js' in PARSER_REGISTRY
    assert '.ts' in PARSER_REGISTRY


def test_parser_registry_has_shell():
    """Parser registry maps .sh and .bash."""
    from index_utils import PARSER_REGISTRY
    assert '.sh' in PARSER_REGISTRY
    assert '.bash' in PARSER_REGISTRY


def test_parse_file_returns_result_for_python():
    """parse_file() dispatches to correct parser."""
    from index_utils import parse_file
    result = parse_file("def foo(): pass", '.py')
    assert result is not None
    assert 'functions' in result


def test_parse_file_returns_none_for_unknown():
    """parse_file() returns None for unregistered extensions."""
    from index_utils import parse_file
    result = parse_file("some content", '.xyz')
    assert result is None


def test_parse_file_uses_ast_by_default():
    """parse_file uses AST parser for .py when V2_AST_PARSER is not 0."""
    from index_utils import parse_file
    os.environ.pop('V2_AST_PARSER', None)
    result = parse_file("def foo(): pass", '.py')
    assert result is not None
    assert 'functions' in result


def test_dense_format_uses_constants():
    """project_index.py uses KEY_* constants instead of bare strings."""
    source = Path(__file__).parent.parent / 'scripts' / 'project_index.py'
    content = source.read_text()
    assert 'KEY_FILES' in content, "KEY_FILES constant not found"
    assert 'KEY_GRAPH' in content, "KEY_GRAPH constant not found"


def test_smart_stop_hook():
    """stop_hook.py checks staleness before regenerating."""
    source = Path(__file__).parent.parent / 'scripts' / 'stop_hook.py'
    content = source.read_text()
    assert 'should_regenerate' in content, "Smart regeneration check not found"
