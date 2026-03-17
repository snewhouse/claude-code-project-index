#!/usr/bin/env python3
"""SQLite-backed cache for incremental project indexing.

Stores per-file parse results keyed by path, with two-tier dirty detection:
1. Fast path: mtime + file size comparison
2. Accurate path: SHA-256 content hash on mismatch

Cache location: ~/.claude-code-project-index/cache.db
"""

import hashlib
import json
import os
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Version string — bump this to invalidate all caches
CURRENT_TOOL_VERSION = "1.0.0"

# If more than this fraction of files are dirty, do a full rebuild
DIRTY_THRESHOLD = 0.5


def _cache_db_path() -> Path:
    """Return the path to the SQLite cache database."""
    cache_dir = Path.home() / '.claude-code-project-index'
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / 'cache.db'


def open_cache(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Open (or create) the cache database with proper pragmas.

    Uses quick_check (not full integrity_check) for routine opens.
    Falls back to delete-and-recreate on corruption.
    """
    if db_path is None:
        db_path = _cache_db_path()

    def _init_connection(path):
        c = sqlite3.connect(str(path), timeout=5)
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        return c

    try:
        conn = _init_connection(db_path)
        # Quick integrity check
        result = conn.execute("PRAGMA quick_check").fetchone()
        if result[0] != 'ok':
            conn.close()
            os.unlink(str(db_path))
            conn = _init_connection(db_path)
    except sqlite3.DatabaseError:
        try:
            conn.close()
        except Exception:
            pass
        os.unlink(str(db_path))
        conn = _init_connection(db_path)

    # Create tables if needed
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS file_cache (
            path TEXT PRIMARY KEY,
            mtime REAL NOT NULL,
            size INTEGER NOT NULL,
            content_hash TEXT,
            lang TEXT,
            parse_result TEXT NOT NULL,
            tool_version TEXT NOT NULL,
            indexed_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)

    # Check tool version — invalidate on mismatch
    row = conn.execute("SELECT value FROM meta WHERE key='tool_version'").fetchone()
    if row is None or row[0] != CURRENT_TOOL_VERSION:
        conn.execute("DELETE FROM file_cache")
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('tool_version', ?)",
                     (CURRENT_TOOL_VERSION,))
        conn.commit()

    return conn


def compute_content_hash(file_path: Path) -> str:
    """Compute SHA-256 hash of file content."""
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_cached_result(conn: sqlite3.Connection, rel_path: str) -> Optional[Dict]:
    """Get cached parse result for a file, or None if not cached."""
    row = conn.execute(
        "SELECT parse_result FROM file_cache WHERE path=? AND tool_version=?",
        (rel_path, CURRENT_TOOL_VERSION)
    ).fetchone()
    if row:
        return json.loads(row[0])
    return None


def is_file_dirty(conn: sqlite3.Connection, rel_path: str,
                  file_path: Path) -> bool:
    """Check if a file needs re-parsing using two-tier detection.

    Tier 1 (fast): Compare mtime + size
    Tier 2 (accurate): Compare SHA-256 hash on mismatch
    """
    row = conn.execute(
        "SELECT mtime, size, content_hash FROM file_cache WHERE path=?",
        (rel_path,)
    ).fetchone()

    if row is None:
        return True  # Not in cache

    try:
        stat = file_path.stat()
    except OSError:
        return True  # Can't stat, treat as dirty

    cached_mtime, cached_size, cached_hash = row

    # Tier 1: Fast mtime+size check
    if stat.st_mtime == cached_mtime and stat.st_size == cached_size:
        return False  # Not dirty

    # Tier 2: Content hash check (file may have been touched but not changed)
    if cached_hash:
        current_hash = compute_content_hash(file_path)
        if current_hash == cached_hash:
            # Update mtime in cache (file was touched but not changed)
            conn.execute(
                "UPDATE file_cache SET mtime=? WHERE path=?",
                (stat.st_mtime, rel_path)
            )
            return False

    return True


def update_cache(conn: sqlite3.Connection, rel_path: str, file_path: Path,
                 parse_result: Dict, lang: Optional[str] = None) -> None:
    """Store or update a file's parse result in the cache."""
    try:
        stat = file_path.stat()
    except OSError:
        return

    content_hash = compute_content_hash(file_path)

    conn.execute("""
        INSERT OR REPLACE INTO file_cache
        (path, mtime, size, content_hash, lang, parse_result, tool_version, indexed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        rel_path,
        stat.st_mtime,
        stat.st_size,
        content_hash,
        lang,
        json.dumps(parse_result),
        CURRENT_TOOL_VERSION,
        time.time()
    ))


def find_dirty_files(conn: sqlite3.Connection, file_paths: List[Tuple[str, Path]]) -> Tuple[List[Tuple[str, Path]], bool]:
    """Identify which files need re-parsing.

    Args:
        conn: SQLite connection
        file_paths: List of (relative_path, absolute_path) tuples

    Returns:
        Tuple of (dirty_files list, should_full_rebuild bool)
    """
    dirty = []
    for rel_path, abs_path in file_paths:
        if is_file_dirty(conn, rel_path, abs_path):
            dirty.append((rel_path, abs_path))

    # If more than 50% are dirty, recommend full rebuild
    total = len(file_paths)
    should_rebuild = total > 0 and len(dirty) / total > DIRTY_THRESHOLD

    return dirty, should_rebuild


def get_git_changed_files(project_root: Path) -> Optional[Set[str]]:
    """Get files changed since last indexed commit using git diff."""
    try:
        result = subprocess.run(
            ['git', 'diff', '--name-only', 'HEAD'],
            cwd=str(project_root),
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            files = set(result.stdout.strip().split('\n')) if result.stdout.strip() else set()
            # Also get staged changes
            result2 = subprocess.run(
                ['git', 'diff', '--name-only', '--cached'],
                cwd=str(project_root),
                capture_output=True, text=True, timeout=5
            )
            if result2.returncode == 0 and result2.stdout.strip():
                files.update(result2.stdout.strip().split('\n'))
            return files
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def purge_removed_files(conn: sqlite3.Connection,
                        current_files: Set[str]) -> int:
    """Remove cache entries for files that no longer exist.

    Returns number of entries purged.
    """
    cached = set(row[0] for row in conn.execute("SELECT path FROM file_cache").fetchall())
    removed = cached - current_files
    if removed:
        conn.executemany("DELETE FROM file_cache WHERE path=?",
                        [(p,) for p in removed])
    return len(removed)
