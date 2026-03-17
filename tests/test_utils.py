"""Characterization tests for utility functions in index_utils.py."""

from pathlib import Path

from index_utils import should_index_file, get_language_name


# ---------------------------------------------------------------------------
# should_index_file
# ---------------------------------------------------------------------------

def test_should_index_file_python_returns_true():
    """.py files should be indexed."""
    p = Path("/some/project/module.py")
    assert should_index_file(p) is True


def test_should_index_file_pyc_returns_false():
    """.pyc compiled files should NOT be indexed (not in CODE_EXTENSIONS)."""
    p = Path("/some/project/module.pyc")
    assert should_index_file(p) is False


def test_should_index_file_node_modules_returns_false():
    """Files inside node_modules should be skipped regardless of extension."""
    p = Path("/some/project/node_modules/lodash/index.js")
    assert should_index_file(p) is False


# ---------------------------------------------------------------------------
# get_language_name
# ---------------------------------------------------------------------------

def test_get_language_name_python():
    """.py extension maps to 'python'."""
    assert get_language_name('.py') == 'python'


def test_get_language_name_javascript():
    """.js extension maps to 'javascript'."""
    assert get_language_name('.js') == 'javascript'
