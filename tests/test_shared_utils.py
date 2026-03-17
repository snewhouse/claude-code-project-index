"""Tests for shared utilities in index_utils.py."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


def test_calculate_files_hash_returns_string():
    """calculate_files_hash returns a hex string."""
    from index_utils import calculate_files_hash
    project_root = Path(__file__).parent.parent
    result = calculate_files_hash(project_root)
    assert isinstance(result, str)
    assert len(result) == 16 or result == "unknown"


def test_calculate_files_hash_deterministic():
    """Same project root produces same hash."""
    from index_utils import calculate_files_hash
    project_root = Path(__file__).parent.parent
    hash1 = calculate_files_hash(project_root)
    hash2 = calculate_files_hash(project_root)
    assert hash1 == hash2


def test_calculate_files_hash_nonexistent_returns_unknown(tmp_path):
    """Non-git directory returns unknown or a hash from rglob fallback."""
    from index_utils import calculate_files_hash
    result = calculate_files_hash(tmp_path)
    assert isinstance(result, str)


def test_atomic_write_json_creates_file(tmp_path):
    """atomic_write_json creates a valid JSON file."""
    from index_utils import atomic_write_json
    target = tmp_path / "test.json"
    data = {"key": "value", "number": 42}
    atomic_write_json(target, data)
    assert target.exists()
    loaded = json.loads(target.read_text())
    assert loaded == data


def test_atomic_write_json_minified_by_default(tmp_path):
    """atomic_write_json produces minified JSON by default."""
    from index_utils import atomic_write_json
    target = tmp_path / "test.json"
    atomic_write_json(target, {"a": 1})
    content = target.read_text()
    assert "\n" not in content
    assert " " not in content


def test_atomic_write_json_with_indent(tmp_path):
    """atomic_write_json respects indent parameter."""
    from index_utils import atomic_write_json
    target = tmp_path / "test.json"
    atomic_write_json(target, {"a": 1}, indent=2)
    content = target.read_text()
    assert "\n" in content
