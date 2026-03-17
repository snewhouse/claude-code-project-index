"""Characterization tests for parse_index_flag in i_flag_hook.py.

Note: parse_index_flag returns (size_k, clipboard_mode, cleaned_prompt).
When no flag is present, it returns (None, None, original_prompt).
"""

import pytest
from unittest.mock import patch

from i_flag_hook import parse_index_flag, DEFAULT_SIZE_K


def test_parse_i_flag():
    """Plain -i flag: clipboard_mode=False, size falls back to DEFAULT_SIZE_K."""
    # get_last_interactive_size reads from disk; patch it to avoid side effects.
    with patch('i_flag_hook.get_last_interactive_size', return_value=DEFAULT_SIZE_K):
        size_k, clipboard_mode, cleaned = parse_index_flag("fix bug -i")

    assert clipboard_mode is False
    assert size_k == DEFAULT_SIZE_K
    assert cleaned == "fix bug"


def test_parse_i_with_size():
    """'-i50' flag: clipboard_mode=False, size_k=50, prompt stripped."""
    size_k, clipboard_mode, cleaned = parse_index_flag("fix bug -i50")

    assert clipboard_mode is False
    assert size_k == 50
    assert cleaned == "fix bug"


def test_parse_ic_flag():
    """'-ic200' flag: clipboard_mode=True, size_k=200, prompt stripped."""
    size_k, clipboard_mode, cleaned = parse_index_flag("fix bug -ic200")

    assert clipboard_mode is True
    assert size_k == 200
    assert cleaned == "fix bug"


def test_no_flag():
    """No flag: returns (None, None, original_prompt)."""
    size_k, clipboard_mode, cleaned = parse_index_flag("fix bug")

    assert size_k is None
    assert clipboard_mode is None
    assert cleaned == "fix bug"
