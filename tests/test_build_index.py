"""Integration tests for the build_index() function in project_index.py."""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from project_index import build_index


def _init_git_repo(path):
    """Initialize a git repo and stage all files so git ls-files works."""
    subprocess.run(['git', 'init'], cwd=str(path), capture_output=True)
    subprocess.run(['git', 'add', '.'], cwd=str(path), capture_output=True)


def test_build_index_returns_tuple(tmp_path, monkeypatch):
    """build_index returns a (dict, int) tuple."""
    (tmp_path / 'main.py').write_text('def hello(): pass\n')
    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = build_index(str(tmp_path))

    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], dict)
    assert isinstance(result[1], int)


def test_build_index_indexes_python_file(tmp_path, monkeypatch):
    """A Python file with a function is indexed and its function captured."""
    (tmp_path / 'main.py').write_text('def hello(): pass\n')
    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    index, _ = build_index(str(tmp_path))

    assert 'files' in index
    assert 'main.py' in index['files']
    file_info = index['files']['main.py']
    assert 'functions' in file_info
    assert 'hello' in file_info['functions']


def test_build_index_skips_ignored_dirs(tmp_path, monkeypatch):
    """Files inside node_modules/ are not included in the index."""
    nm = tmp_path / 'node_modules' / 'pkg'
    nm.mkdir(parents=True)
    (nm / 'index.js').write_text('function foo() {}\n')
    # Also add a top-level file so the index isn't empty
    (tmp_path / 'app.py').write_text('x = 1\n')
    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    index, _ = build_index(str(tmp_path))

    for path in index['files']:
        assert 'node_modules' not in path


def test_build_index_stats_counts(tmp_path, monkeypatch):
    """Stats reflect the number of indexed files and parsed languages."""
    (tmp_path / 'a.py').write_text('def fa(): pass\n')
    (tmp_path / 'b.py').write_text('def fb(): pass\n')
    (tmp_path / 'c.js').write_text('function fc() {}\n')
    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    index, _ = build_index(str(tmp_path))

    assert index['stats']['total_files'] >= 3
    assert 'python' in index['stats']['fully_parsed']


def test_build_index_empty_dir(tmp_path, monkeypatch):
    """An empty directory produces an index with total_files == 0."""
    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    index, _ = build_index(str(tmp_path))

    assert index['stats']['total_files'] == 0
