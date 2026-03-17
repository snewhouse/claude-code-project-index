"""Tests for _find_matching_brace and _find_matching_brace_char helpers."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from index_utils import _find_matching_brace, _find_matching_brace_char


# --- Line-based _find_matching_brace tests ---

def test_find_matching_brace_simple():
    """Simple case: { ... } on separate lines."""
    lines = [
        "function foo() {",
        "  return 1;",
        "}",
    ]
    # Start on line 0 where the '{' is
    assert _find_matching_brace(lines, 0) == 2


def test_find_matching_brace_nested():
    """Nested braces: { { } }."""
    lines = [
        "function foo() {",
        "  if (true) {",
        "    return 1;",
        "  }",
        "}",
    ]
    assert _find_matching_brace(lines, 0) == 4


def test_find_matching_brace_not_found():
    """Returns last line index when closing brace is missing."""
    lines = [
        "function foo() {",
        "  return 1;",
    ]
    assert _find_matching_brace(lines, 0) == len(lines) - 1


def test_find_matching_brace_start_col():
    """Start column offset skips earlier characters on start_line."""
    lines = [
        "xxxxx { content }",
    ]
    # Start at column 6 where the '{' is
    result = _find_matching_brace(lines, 0, start_col=6)
    assert result == 0  # Closing brace is on same line


def test_find_matching_brace_deeply_nested():
    """Deeply nested braces."""
    lines = [
        "{",
        "  {",
        "    {",
        "    }",
        "  }",
        "}",
    ]
    assert _find_matching_brace(lines, 0) == 5


# --- Character-based _find_matching_brace_char tests ---

def test_find_matching_brace_char_simple():
    """Simple character-based brace matching."""
    text = "{ hello }"
    # start_pos is after the opening brace (position 1)
    assert _find_matching_brace_char(text, 1) == 8


def test_find_matching_brace_char_nested():
    """Nested braces in character mode."""
    text = "{ { inner } outer }"
    assert _find_matching_brace_char(text, 1) == 18


def test_find_matching_brace_char_not_found():
    """Returns start_pos when not found."""
    text = "{ unclosed"
    assert _find_matching_brace_char(text, 1) == 1


def test_find_matching_brace_char_max_scan():
    """Respects max_scan limit."""
    text = "{ " + "x" * 100 + " }"
    # With max_scan=5, won't find the closing brace
    assert _find_matching_brace_char(text, 1, max_scan=5) == 1
    # Without limit, finds it
    assert _find_matching_brace_char(text, 1) == len(text) - 1
