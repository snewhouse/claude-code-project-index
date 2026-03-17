"""Tests for SQLite cache backend."""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


def test_open_cache_creates_tables(tmp_path):
    """open_cache creates the expected tables."""
    from cache_db import open_cache
    db_path = tmp_path / 'test.db'
    conn = open_cache(db_path)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert 'file_cache' in tables
    assert 'meta' in tables
    conn.close()


def test_open_cache_sets_version(tmp_path):
    """open_cache stores the tool version."""
    from cache_db import open_cache, CURRENT_TOOL_VERSION
    db_path = tmp_path / 'test.db'
    conn = open_cache(db_path)
    row = conn.execute("SELECT value FROM meta WHERE key='tool_version'").fetchone()
    assert row[0] == CURRENT_TOOL_VERSION
    conn.close()


def test_cache_version_invalidation(tmp_path):
    """Changing tool version invalidates cache."""
    from cache_db import open_cache, CURRENT_TOOL_VERSION
    import cache_db
    db_path = tmp_path / 'test.db'
    conn = open_cache(db_path)
    # Insert a fake entry
    conn.execute("""INSERT INTO file_cache
        (path, mtime, size, content_hash, lang, parse_result, tool_version, indexed_at)
        VALUES ('test.py', 1.0, 100, 'abc', 'python', '{}', ?, 1.0)""",
        (CURRENT_TOOL_VERSION,))
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM file_cache").fetchone()[0] == 1
    conn.close()

    # Change version and reopen
    old_version = cache_db.CURRENT_TOOL_VERSION
    cache_db.CURRENT_TOOL_VERSION = "999.0.0"
    try:
        conn2 = open_cache(db_path)
        count = conn2.execute("SELECT COUNT(*) FROM file_cache").fetchone()[0]
        assert count == 0, "Cache should be invalidated on version change"
        conn2.close()
    finally:
        cache_db.CURRENT_TOOL_VERSION = old_version


def test_is_file_dirty_not_cached(tmp_path):
    """Uncached files are dirty."""
    from cache_db import open_cache, is_file_dirty
    db_path = tmp_path / 'test.db'
    conn = open_cache(db_path)
    test_file = tmp_path / 'test.py'
    test_file.write_text('pass')
    assert is_file_dirty(conn, 'test.py', test_file) is True
    conn.close()


def test_is_file_dirty_cached_unchanged(tmp_path):
    """Cached file with matching mtime+size is clean."""
    from cache_db import open_cache, update_cache, is_file_dirty
    db_path = tmp_path / 'test.db'
    conn = open_cache(db_path)
    test_file = tmp_path / 'test.py'
    test_file.write_text('pass')
    update_cache(conn, 'test.py', test_file, {'functions': {}})
    conn.commit()
    assert is_file_dirty(conn, 'test.py', test_file) is False
    conn.close()


def test_is_file_dirty_content_changed(tmp_path):
    """File with different content is dirty."""
    from cache_db import open_cache, update_cache, is_file_dirty
    import time
    db_path = tmp_path / 'test.db'
    conn = open_cache(db_path)
    test_file = tmp_path / 'test.py'
    test_file.write_text('pass')
    update_cache(conn, 'test.py', test_file, {'functions': {}})
    conn.commit()
    time.sleep(0.01)  # Ensure mtime changes
    test_file.write_text('def foo(): pass')
    assert is_file_dirty(conn, 'test.py', test_file) is True
    conn.close()


def test_find_dirty_files_threshold(tmp_path):
    """find_dirty_files recommends full rebuild when >50% dirty."""
    from cache_db import open_cache, find_dirty_files
    db_path = tmp_path / 'test.db'
    conn = open_cache(db_path)
    # Create 4 files, all uncached (100% dirty)
    files = []
    for i in range(4):
        f = tmp_path / f'file{i}.py'
        f.write_text(f'x = {i}')
        files.append((f'file{i}.py', f))
    dirty, should_rebuild = find_dirty_files(conn, files)
    assert len(dirty) == 4
    assert should_rebuild is True
    conn.close()


def test_purge_removed_files(tmp_path):
    """purge_removed_files removes entries for deleted files."""
    from cache_db import open_cache, update_cache, purge_removed_files
    db_path = tmp_path / 'test.db'
    conn = open_cache(db_path)
    test_file = tmp_path / 'test.py'
    test_file.write_text('pass')
    update_cache(conn, 'test.py', test_file, {'functions': {}})
    update_cache(conn, 'deleted.py', test_file, {'functions': {}})
    conn.commit()
    purged = purge_removed_files(conn, {'test.py'})
    conn.commit()
    assert purged == 1
    assert conn.execute("SELECT COUNT(*) FROM file_cache").fetchone()[0] == 1
    conn.close()


def test_get_cached_result(tmp_path):
    """get_cached_result retrieves stored parse results."""
    from cache_db import open_cache, update_cache, get_cached_result
    db_path = tmp_path / 'test.db'
    conn = open_cache(db_path)
    test_file = tmp_path / 'test.py'
    test_file.write_text('def foo(): pass')
    result = {'functions': {'foo': {'line': 1}}}
    update_cache(conn, 'test.py', test_file, result)
    conn.commit()
    cached = get_cached_result(conn, 'test.py')
    assert cached == result
    conn.close()


def test_corrupt_db_recovery(tmp_path):
    """open_cache recovers from corrupt database."""
    from cache_db import open_cache
    db_path = tmp_path / 'test.db'
    db_path.write_bytes(b'not a sqlite database at all!!')
    conn = open_cache(db_path)
    # Should have recreated the database
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert 'file_cache' in tables
    conn.close()
