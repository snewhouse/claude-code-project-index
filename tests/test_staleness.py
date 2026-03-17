"""Tests for should_regenerate() staleness detection in stop_hook.py."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from stop_hook import should_regenerate


def test_should_regenerate_no_index(tmp_path):
    """Returns True when the index file does not exist."""
    index_path = tmp_path / "PROJECT_INDEX.json"
    assert should_regenerate(tmp_path, index_path) is True


def test_should_regenerate_matching_hash(tmp_path):
    """Returns False when the stored hash matches the current hash."""
    index_path = tmp_path / "PROJECT_INDEX.json"
    index_path.write_text(json.dumps({"_meta": {"files_hash": "abc123"}}))

    with patch('stop_hook.calculate_files_hash', return_value='abc123'):
        assert should_regenerate(tmp_path, index_path) is False


def test_should_regenerate_different_hash(tmp_path):
    """Returns True when the stored hash differs from the current hash."""
    index_path = tmp_path / "PROJECT_INDEX.json"
    index_path.write_text(json.dumps({"_meta": {"files_hash": "abc123"}}))

    with patch('stop_hook.calculate_files_hash', return_value='def456'):
        assert should_regenerate(tmp_path, index_path) is True


def test_should_regenerate_unknown_hash(tmp_path):
    """Returns True when calculate_files_hash returns 'unknown'."""
    index_path = tmp_path / "PROJECT_INDEX.json"
    index_path.write_text(json.dumps({"_meta": {"files_hash": "abc123"}}))

    with patch('stop_hook.calculate_files_hash', return_value='unknown'):
        assert should_regenerate(tmp_path, index_path) is True


def test_should_regenerate_corrupt_json(tmp_path):
    """Returns True when the index file contains invalid JSON."""
    index_path = tmp_path / "PROJECT_INDEX.json"
    index_path.write_text("not valid json {{{")

    with patch('stop_hook.calculate_files_hash', return_value='abc123'):
        assert should_regenerate(tmp_path, index_path) is True
