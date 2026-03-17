"""Characterization tests for compress_if_needed in project_index.py."""

import json
import sys
from pathlib import Path

# project_index.py imports from index_utils using a bare name (not a package),
# so we must add scripts/ to sys.path before importing.
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from project_index import compress_if_needed


def _make_large_dense_index(num_files: int = 200, funcs_per_file: int = 20) -> dict:
    """Build a dense-format index dict large enough to require compression."""
    files = {}
    for i in range(num_files):
        funcs = [
            f"func_{j}:{j}:(arg1: str, arg2: int) -> bool:[]:A longer docstring that takes up space in the index {j}"
            for j in range(funcs_per_file)
        ]
        files[f"s/module_{i}.py"] = ["p", funcs, {}]

    tree = [f"├── module_{i}.py" for i in range(50)]
    doc_map = {f"doc_{i}.md": [f"# Section {j}" for j in range(10)] for i in range(20)}

    return {
        "at": "2026-01-01T00:00:00",
        "root": "/tmp/project",
        "tree": tree,
        "f": files,
        "g": [[f"func_{i}", f"func_{i+1}"] for i in range(100)],
        "d": doc_map,
        "deps": {},
        "_meta": {"target_size_k": 50},
    }


def _json_size(obj: dict) -> int:
    return len(json.dumps(obj, separators=(',', ':')))


def test_compression_reduces_size():
    """When the index exceeds the target, compress_if_needed shrinks it."""
    index = _make_large_dense_index()
    original_size = _json_size(index)

    # Use a target well below the current size to force compression.
    target = original_size // 4
    assert target > 0

    compressed = compress_if_needed(index, target_size=target)
    compressed_size = _json_size(compressed)

    assert compressed_size < original_size, (
        f"Expected compressed size ({compressed_size}) < original ({original_size})"
    )


def test_compression_fits_target():
    """Compressed output fits within the target size."""
    index = _make_large_dense_index()
    original_size = _json_size(index)

    # Set target to ~half the original size
    target = original_size // 2
    assert target > 0

    compressed = compress_if_needed(index, target_size=target)
    compressed_size = _json_size(compressed)

    assert compressed_size <= target, (
        f"Compressed size ({compressed_size}) exceeds target ({target})"
    )


def test_compression_idempotent():
    """When the index already fits within the target, it is returned unchanged."""
    small_index = {
        "at": "2026-01-01T00:00:00",
        "root": "/tmp/project",
        "tree": ["└── main.py"],
        "f": {"s/main.py": ["p", ["hello:1:() -> None:[]:Say hello"], {}]},
        "g": [],
        "d": {},
        "deps": {},
        "_meta": {},
    }

    size = _json_size(small_index)
    # Target is much larger than the index.
    large_target = size * 10

    result = compress_if_needed(small_index, target_size=large_target)
    result_size = _json_size(result)

    assert result_size == size, (
        f"Expected size unchanged ({size}), but got {result_size}"
    )
