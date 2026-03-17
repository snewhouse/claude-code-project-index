"""Tests for generate_index_at_size() in i_flag_hook.py."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# conftest.py already adds scripts/ to sys.path
from i_flag_hook import generate_index_at_size


@pytest.fixture
def fake_project(tmp_path, monkeypatch):
    """Set up a fake project dir with a dummy indexer script and PROJECT_INDEX.json."""
    # Create a dummy project_index.py next to the hook so the local_indexer path resolves.
    # generate_index_at_size uses Path(__file__).parent / 'project_index.py'
    scripts_dir = Path(__file__).parent.parent / "scripts"
    # The real project_index.py should already exist; if not, create a stub.
    indexer = scripts_dir / "project_index.py"
    if not indexer.exists():
        indexer.write_text("# stub\n")

    # Pre-seed a minimal PROJECT_INDEX.json in tmp_path
    index_path = tmp_path / "PROJECT_INDEX.json"
    index_path.write_text(json.dumps({"_meta": {}}))

    # Ensure .python_cmd doesn't interfere — remove if present
    python_cmd_file = Path.home() / ".claude-code-project-index" / ".python_cmd"
    if python_cmd_file.exists():
        monkeypatch.setattr(
            "i_flag_hook.Path.home",
            lambda: tmp_path,  # redirect so .python_cmd won't be found
        )

    return tmp_path


def _successful_run(*args, **kwargs):
    """Return a CompletedProcess that looks like a successful subprocess.run."""
    return subprocess.CompletedProcess(
        args=args[0] if args else [],
        returncode=0,
        stdout="",
        stderr="",
    )


def _failed_run(*args, **kwargs):
    """Return a CompletedProcess with non-zero returncode."""
    return subprocess.CompletedProcess(
        args=args[0] if args else [],
        returncode=1,
        stdout="",
        stderr="error",
    )


def test_generate_index_at_size_success(fake_project):
    """Mock subprocess.run to return success; verify function returns True."""
    with patch("i_flag_hook.subprocess.run", side_effect=_successful_run), \
         patch("i_flag_hook.calculate_files_hash", return_value="abc123"):
        result = generate_index_at_size(fake_project, target_size_k=50)

    assert result is True

    # Verify the index was updated with metadata
    index_path = fake_project / "PROJECT_INDEX.json"
    data = json.loads(index_path.read_text())
    assert "target_size_k" in data["_meta"]
    assert data["_meta"]["target_size_k"] == 50
    assert "generated_at" in data["_meta"]
    assert "files_hash" in data["_meta"]


def test_generate_index_at_size_failure(fake_project):
    """Mock subprocess.run to return failure; verify returns False."""
    with patch("i_flag_hook.subprocess.run", side_effect=_failed_run), \
         patch("i_flag_hook.calculate_files_hash", return_value="abc123"):
        result = generate_index_at_size(fake_project, target_size_k=50)

    assert result is False


def test_generate_index_at_size_timeout(fake_project):
    """Mock subprocess.run to raise TimeoutExpired; verify returns False."""
    def _timeout_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="python project_index.py", timeout=30)

    with patch("i_flag_hook.subprocess.run", side_effect=_timeout_run), \
         patch("i_flag_hook.calculate_files_hash", return_value="abc123"):
        result = generate_index_at_size(fake_project, target_size_k=50)

    assert result is False


def test_generate_index_at_size_remembers_size(fake_project):
    """When not clipboard mode, last_interactive_size_k should be written to _meta."""
    with patch("i_flag_hook.subprocess.run", side_effect=_successful_run), \
         patch("i_flag_hook.calculate_files_hash", return_value="abc123"):
        result = generate_index_at_size(
            fake_project, target_size_k=75, is_clipboard_mode=False
        )

    assert result is True

    index_path = fake_project / "PROJECT_INDEX.json"
    data = json.loads(index_path.read_text())
    assert data["_meta"]["last_interactive_size_k"] == 75


def test_generate_index_at_size_clipboard_no_remember(fake_project):
    """When clipboard mode, last_interactive_size_k should NOT be set."""
    with patch("i_flag_hook.subprocess.run", side_effect=_successful_run), \
         patch("i_flag_hook.calculate_files_hash", return_value="abc123"):
        result = generate_index_at_size(
            fake_project, target_size_k=75, is_clipboard_mode=True
        )

    assert result is True

    index_path = fake_project / "PROJECT_INDEX.json"
    data = json.loads(index_path.read_text())
    assert "last_interactive_size_k" not in data["_meta"]
