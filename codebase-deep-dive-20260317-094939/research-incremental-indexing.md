# Research: Incremental Indexing, Caching, and Auto-Indexing Strategies

**Date:** 2026-03-17
**Context:** claude-code-project-index — currently does full re-parse on every run (~15–30s for large projects). This research covers strategies for incremental parsing, persistent caching, auto-indexing triggers, and graph invalidation.

---

## 1. Incremental Parsing Strategies

### 1.1 Content Hash vs. mtime: The Core Trade-off

Two signals are commonly used to detect whether a file has changed and needs re-parsing:

| Signal | Speed | Accuracy | False Positives | False Negatives |
|--------|-------|----------|-----------------|-----------------|
| `mtime` only | Very fast (single stat call) | Low — mtime can change without content change (touch, checkout, copy) | Yes — regenerates needlessly | No |
| `size` only | Very fast | Low — size can be identical for different content | Yes | Yes (same-size edits) |
| `mtime + size` | Fast | Medium — catches most real changes cheaply | Fewer | Rare |
| SHA-256 content hash | Slow (reads file) | Perfect | None | None |
| `mtime + size` then SHA-256 on mismatch | Fast path + exact | High | Very few | None |

**Best practice (2025 production systems):** Use a two-tier check:
1. Quick check: compare `(mtime, size)` from a metadata table against current `os.stat()`. If both match, file is clean — skip re-parse (no disk read needed).
2. Slow check: only when `(mtime, size)` differs, read the file and compute SHA-256. If hash also differs, re-parse. Update the cache record regardless.

This is the pattern used by `codebase-memory-mcp` (Go, 64 languages, sub-ms queries): it maintains a metadata table with `{path, mtime, size, content_hash, last_indexed}` and polls for changes using mtime+size as the fast gate.

**Why not hash-first?** For 50k files, SHA-256 on every check requires reading all 50k files — that is I/O-bound and negates the incremental speedup. The mtime+size fast path avoids disk reads for unchanged files.

**Why not mtime-only?** `git checkout`, `rsync`, and many editors reset mtime to a value other than "now". A file that was not really edited gets re-parsed. Worse, some editors (notably Emacs backup files) can change content without updating mtime. The size check catches most of these cheaply.

### 1.2 git-Based Change Detection

For git-tracked projects, `git diff --name-only` is the most precise change signal:

```bash
# Files changed since last indexed commit
git diff --name-only <last_indexed_sha> HEAD

# Files changed vs working tree (includes staged + unstaged)
git diff --name-only HEAD

# Changed files including untracked
git status --porcelain | awk '{print $2}'
```

**Advantages:**
- Zero false positives for committed files — git tracks exact content via object SHA1
- Works at repository level, so renames and deletes are explicitly signaled
- Integrates naturally with post-commit hooks

**Limitations:**
- Only covers tracked files; new/untracked files require `git status` or a separate walk
- If the indexer stores `last_indexed_commit_sha`, it can diff exactly: `git diff --name-only $LAST_SHA HEAD`
- Does not handle working-tree edits between commits (files edited but not yet committed)

**Recommended approach for this project:** Store the git commit SHA at index-generation time in `_meta.indexed_at_commit`. On next run, use `git diff --name-only $LAST_SHA HEAD` for committed changes plus a quick mtime scan of untracked/modified files (`git status --porcelain`).

### 1.3 File Watcher Approaches

#### inotify (Linux)
- Kernel-level event system; zero polling overhead
- Events: `IN_MODIFY`, `IN_CREATE`, `IN_DELETE`, `IN_MOVED_FROM/TO`
- Limitation: inotify watches are per-directory, not recursive by default. For 50k+ files across deep trees, one watch per directory is needed — the kernel default `max_user_watches` is 8192 (tunable via `sysctl fs.inotify.max_user_watches`)
- For WSL2 specifically: inotify works for files inside the WSL2 filesystem but does NOT propagate events from Windows NTFS mounts

#### fsevents (macOS)
- FSEvents API provides recursive directory watches natively at the volume level
- Much more scalable than inotify for large trees; single watch covers entire subtree

#### Facebook Watchman
The production-grade solution for cross-platform file watching at scale:
- Persistent daemon that maintains its own filesystem view
- Uses native OS watchers (inotify/kqueue/FSEvents) under the hood
- Survives restarts — replays missed events from its journal
- Settles events before dispatching (configurable debounce) — critical for editors that do multi-file save sequences
- Query language allows filtering by path pattern, content type, clock position
- Used by React Native, Buck2, Jest (`jest --watch` uses Watchman)
- **Integration:** `watchman-wait`, `watchman-make`, or the Python `pywatchman` client

```python
import pywatchman
client = pywatchman.client()
client.query('watch', '/path/to/project')
result = client.query('subscribe', '/path/to/project', 'my-sub', {
    'expression': ['suffix', ['py', 'js', 'ts']],
    'fields': ['name', 'exists', 'mtime_ms', 'content.sha1hex'],
})
```

#### Python `watchdog` Library
- Pure-Python abstraction over inotify/kqueue/FSEvents/ReadDirectoryChangesW
- Simple `FileSystemEventHandler` subclass pattern
- Events: `FileCreatedEvent`, `FileModifiedEvent`, `FileDeletedEvent`, `FileMovedEvent`
- **Limitation:** polling fallback on systems without native events; on WSL2 with Windows-side files, uses polling
- Good for lightweight daemon; not as robust as Watchman for large repos

**Recommendation for this project:** Watchman if available (best performance at scale); watchdog as fallback for portability.

---

## 2. Caching Architectures

### 2.1 Cache Storage Options

#### JSON Sidecar Files (current approach — `_meta.files_hash`)
- **Pro:** Human-readable, zero dependencies, simple atomic write via `tempfile + os.replace()`
- **Con:** One large JSON blob — must deserialize entire file to check one entry; no query capability; slow for 50k files
- **Current state:** `PROJECT_INDEX.json` stores `_meta.files_hash` (a hash of all file mtimes). This is a single global dirty bit — if any file changes, everything re-parses.

#### Per-File JSON Sidecars
- Store `file.py.cache.json` next to each source file with `{hash, parse_result}`
- **Pro:** Surgical invalidation — only changed files lose their cache
- **Con:** Pollutes the source tree; hard to exclude from git; cache entries scatter across the filesystem

#### SQLite (recommended for 50k+ files)
- Single-file database, zero server process, ACID transactions, concurrent readers (WAL mode)
- Schema:

```sql
CREATE TABLE file_cache (
    path TEXT PRIMARY KEY,
    mtime REAL NOT NULL,
    size INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    lang TEXT,
    parse_result TEXT,  -- JSON blob of signatures/classes
    indexed_at REAL NOT NULL,
    tool_version TEXT NOT NULL   -- invalidate cache on tool upgrade
);

CREATE TABLE graph_edges (
    caller TEXT NOT NULL,
    callee TEXT NOT NULL,
    PRIMARY KEY (caller, callee)
);

CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

- WAL mode enables concurrent reads while writing: `PRAGMA journal_mode=WAL`
- **Query:** `SELECT parse_result FROM file_cache WHERE path = ? AND mtime = ? AND size = ? AND tool_version = ?` — cache hit on single indexed read
- **Performance:** For 50k files, SQLite with a B-tree index on `path` handles cache lookups in O(log n) vs O(n) for JSON scan

#### Binary Serialization Formats (MessagePack, CBOR)
- Faster and more compact than JSON for large result blobs
- MessagePack is ~2x faster to serialize/deserialize than JSON and produces ~30% smaller output
- Drop-in replacement when combined with SQLite BLOB storage
- Avoid Python's `marshal` module for persistent cache — it has no format stability guarantees across Python versions

**Note:** Python's `pickle` module is explicitly NOT recommended for cache storage. It is Python-only, produces output ~2x the size of MessagePack, and deserializing untrusted data from disk opens an arbitrary code execution vector. Use JSON or MessagePack instead.

### 2.2 Cache Versioning and Invalidation on Tool Upgrade

A cache entry from tool version 0.1.x may have different parse fields than 0.2.x. Without versioning, stale results silently corrupt the index.

**Pattern:** Store `tool_version` in every cache entry and in a `meta` table. On startup:

```python
CURRENT_TOOL_VERSION = "0.2.0"

def open_cache(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    _ensure_schema(conn)

    # Check tool version — full invalidation if changed
    row = conn.execute("SELECT value FROM meta WHERE key='tool_version'").fetchone()
    if row is None or row[0] != CURRENT_TOOL_VERSION:
        conn.execute("DELETE FROM file_cache")
        conn.execute("DELETE FROM graph_edges")
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('tool_version', ?)",
                     (CURRENT_TOOL_VERSION,))
        conn.commit()
    return conn
```

**Schema migration:** For non-breaking schema changes (adding columns), use `ALTER TABLE ... ADD COLUMN`. For breaking changes (restructured `parse_result` JSON), bump `tool_version` to force full re-parse.

### 2.3 Cache Corruption Detection and Recovery

**Write-side:** Always use atomic write:
```python
# SQLite handles this via transactions
with conn:
    conn.execute("INSERT OR REPLACE INTO file_cache VALUES (?,?,?,?,?,?,?,?)", row)

# For JSON output (PROJECT_INDEX.json), use tempfile + os.replace():
import tempfile, os
fd, tmp_path = tempfile.mkstemp(dir=output_path.parent, suffix='.tmp')
try:
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f)
    os.replace(tmp_path, output_path)  # atomic on POSIX
except Exception:
    os.unlink(tmp_path)
    raise
```

**Read-side corruption check:** On open, verify the SQLite file is valid:
```python
try:
    conn.execute("PRAGMA integrity_check").fetchone()
except sqlite3.DatabaseError:
    # Cache corrupt — delete and start fresh
    conn.close()
    db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    _ensure_schema(conn)
```

**Checksum guard for JSON:** Store a SHA-256 of the JSON body in `_meta.checksum`. On read, verify before trusting the data.

---

## 3. Auto-Indexing Triggers

### 3.1 git Hooks

The cleanest integration point for "index is always current after a commit":

**`post-commit` hook** (`.git/hooks/post-commit`):
```bash
#!/usr/bin/env bash
# Run indexer in background — don't block the commit
python3 ~/.claude-code-project-index/scripts/project_index.py \
    --incremental \
    --since-commit "$(git rev-parse HEAD~1)" \
    > /dev/null 2>&1 &
```

**Key properties:**
- `post-commit` cannot abort a commit (unlike `pre-commit`) — safe to run here
- Background (`&`) ensures the hook returns immediately; user is not blocked
- `post-merge` hook covers the `git pull` / `git merge` case
- `post-checkout` covers branch switches — file set changes significantly on checkout

**For this project:** The current `stop_hook.py` runs inside Claude Code sessions. A git `post-commit` hook would complement this by keeping the index fresh outside of Claude sessions. Install via `install.sh`.

**`pre-commit` hook alternative:** Run incrementally before commit to capture the exact working-tree state. Drawback: adds latency to the commit UX.

### 3.2 File System Watchers — Daemon Pattern

A background daemon keeps the index perpetually fresh:

```python
# daemon.py — simplified
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import queue, time

class IndexHandler(FileSystemEventHandler):
    def __init__(self, work_queue):
        self.q = work_queue

    def on_modified(self, event):
        if not event.is_directory:
            self.q.put(('modified', event.src_path))

    def on_created(self, event):
        if not event.is_directory:
            self.q.put(('created', event.src_path))

    def on_deleted(self, event):
        if not event.is_directory:
            self.q.put(('deleted', event.src_path))

def debounced_worker(q, cache, debounce_s=0.5):
    """Batch events within debounce window before processing."""
    pending = {}
    while True:
        try:
            event_type, path = q.get(timeout=debounce_s)
            pending[path] = event_type  # last event wins per path
        except queue.Empty:
            if pending:
                process_batch(pending, cache)
                pending.clear()
```

**Debouncing is critical:** Editors emit 3–10 inotify events per save (temp file creation, rename, attribute change). Without debouncing, the same file would be re-parsed up to 10 times per save.

**Adaptive polling interval (codebase-memory-mcp pattern):** Scale polling frequency with repo size:
- Less than 1k files: poll every 1s
- 1k–10k files: poll every 5s
- 10k–50k files: poll every 15–30s
- More than 50k files: use Watchman or inotify directly (no polling)

### 3.3 VS Code Integration via Language Server Protocol

LSP defines three sync modes for document changes:
- `TextDocumentSyncKind.None` — server maintains state independently
- `TextDocumentSyncKind.Full` — full document sent on every change
- `TextDocumentSyncKind.Incremental` — only changed ranges sent (diff chunks)

For a VS Code extension wrapping this indexer:
- Register `onDidSaveTextDocument` (not `onDidChangeTextDocument`) to avoid re-parsing on every keystroke
- Register workspace file watchers via `vscode.workspace.createFileSystemWatcher('**/*.py')` for files not currently open

```typescript
// VS Code extension snippet
const watcher = vscode.workspace.createFileSystemWatcher('**/*.{py,js,ts}');
watcher.onDidChange(uri => triggerIncrementalIndex(uri.fsPath));
watcher.onDidCreate(uri => triggerIncrementalIndex(uri.fsPath));
watcher.onDidDelete(uri => invalidateFromIndex(uri.fsPath));
```

### 3.4 Claude Code Hook Integration Points

The current architecture has two hook integration points:
- `UserPromptSubmit` (`i_flag_hook.py`) — on-demand, triggered by `-i` flag in prompt
- `Stop` (`stop_hook.py`) — end-of-session, regenerates if stale

**Additional hook opportunities:**
- A `PreToolUse` hook could detect `Write`/`Edit` tool calls and flag specific files as dirty in the cache without triggering full re-indexing
- A dedicated `post-commit` git hook (separate from Claude Code hooks) covers changes made outside Claude sessions

### 3.5 Background Daemon vs. On-Demand

| Approach | Latency (first use) | CPU overhead | Complexity | Best for |
|----------|---------------------|-------------|------------|----------|
| Full re-index on demand | 15–30s | Only when needed | Low (current) | Small repos |
| Incremental on demand (git-diff-based) | 1–5s | Only when needed | Medium | Medium repos |
| Background daemon (file watcher) | ~0s (always fresh) | Continuous (low) | High | Large repos, frequent use |
| git hook + incremental | ~0s after commit | Only on commit | Medium | Most projects |

**Recommendation for this project:** Implement git hook + incremental re-parse as the primary strategy. The daemon approach is powerful but adds operational complexity (process management, startup, PID files). The git hook approach is zero-overhead between commits.

---

## 4. Production Tool Performance Benchmarks

### 4.1 rust-analyzer + Salsa Framework

rust-analyzer is the canonical example of incremental analysis done right. Its architecture directly informs what is possible:

**Salsa framework core concepts:**
- All computation is expressed as "queries" (pure functions of their inputs)
- Salsa records which queries were called during each computation, building a dependency graph
- When an input changes, Salsa marks dependent queries as potentially stale
- On next access, a stale query re-runs — but only if its direct inputs actually changed
- **Early cutoff:** If a file changes but its AST is identical (e.g., only whitespace changed), queries dependent only on the AST are not re-run. This is the key optimization.

**Durability tiers:** Salsa divides inputs into durability levels:
- `HIGH` durability: stdlib, rarely-changing dependencies
- `MEDIUM` durability: project files
- `LOW` durability: currently-being-edited file

When a LOW-durability input changes, only LOW-durability queries need re-evaluation. MEDIUM/HIGH queries are untouched unless their inputs actually changed.

**Performance:** rust-analyzer handles multi-million-line Rust codebases with sub-second incremental responses during editing.

**Python analog:** The `salsa` framework is Rust-only, but the pattern is implementable in Python using a dependency graph + version numbers per computation node.

### 4.2 mypy / dmypy Daemon

dmypy is a long-running daemon that keeps the type-checked program state in memory:
- **10x+ speedup** over batch `mypy` for large codebases
- Uses fine-grained dependency tracking: knows exactly which symbols are used where
- Cache stored in `.mypy_cache/` — one JSON file per module
- Remote cache: CI uploads `.mypy_cache/` as an artifact; developers download it before first check
- **Lesson:** Even a simple file-per-module cache scheme beats full re-analysis dramatically

### 4.3 Pyright/Pylance

- In-memory cache shared across all files analyzed in one invocation
- Incremental rechecks: only reanalyzs modified files and files that import them
- **3–5x faster than mypy** for full scans; essentially instant for incremental
- Implemented in TypeScript using the LSP persistent server model — the server process keeps all state in memory, avoiding cold-start costs

**Key insight:** Pyright's speed advantage comes from two things: staying resident (daemon model) and precise import-graph tracking to minimize re-work.

### 4.4 Tree-sitter Incremental Parsing

Tree-sitter is an incremental parsing library used by Neovim, Helix, GitHub, and others:
- Benchmarks (2026): parses a 10,000-line C file in under 100ms on modern hardware
- On edits, only re-parses the affected subtree — unchanged portions of the AST are reused (structural sharing)
- A 1-line edit in a 10,000-line file triggers re-parsing of only the changed function body, not the whole file
- **Performance example:** Helix-Lint processed 1M lines of code in under 10s vs 22s with a traditional parser (55% speedup) with 65% fewer false positives

**Applicability:** This project uses regex-based parsing (not tree-sitter). For the incremental use case, if we cache per-file parse results, we get the same structural benefit without tree-sitter: changed file → re-run regex parser → update cache. This is much simpler than implementing tree-sitter incrementality from scratch.

### 4.5 Sourcegraph SCIP

SCIP (SCIP Code Intelligence Protocol) replaced LSIF:
- Key design decision: human-readable string symbol IDs instead of opaque numeric IDs
- This enables partial index updates: when file A changes, only upload A's index slice
- The backend merges the new A slice with existing data for B, C, D... without full reindex
- **Insight for this project:** Our `PROJECT_INDEX.json` uses abbreviated path strings as keys — this is already SCIP-compatible in spirit. We can update only the changed files' entries and rewrite the output.

---

## 5. Graph Invalidation

### 5.1 What Needs Invalidating When File A Changes

When file `A.py` changes, the following need updating:

1. **A's parse result** — its function signatures, classes, docstrings (direct)
2. **Call graph edges from A** — outgoing calls may have changed (direct)
3. **Call graph edges to A** — only if A's exported function names changed (rare)
4. **Dependency graph entries for A** — A's imports may have changed
5. **Files that import A** — if A's public interface (exported names) changed, files importing A may need re-analysis

Item 5 is the cascading invalidation problem. The Rust compiler calls this "red/green" tracking:
- Mark A as "red" (changed)
- Recompute A's public interface
- If the interface hash is unchanged ("green") — stop. Dependents do not need re-analysis.
- If the interface hash changed ("red") — mark A's importers as dirty; recurse

**For this project's call graph:** Our call graph records `{caller -> callee}` pairs as function name strings. When A changes:
1. Delete all edges where caller's file == A
2. Re-parse A, add new edges from A
3. If A's exported function names changed, scan other files' edges for calls to A's old names — this is O(edges), not O(files)

### 5.2 Dependency Tracking Implementation

Track which files import which modules:

```python
# In SQLite cache:
# CREATE TABLE imports (
#     importer TEXT NOT NULL,  -- file that has the import
#     importee TEXT NOT NULL,  -- module/file being imported
#     PRIMARY KEY (importer, importee)
# );
```

When file A changes:
1. Get `reverse_deps = SELECT importer FROM imports WHERE importee = 'A'`
2. If A's exported names are unchanged: update A's cache only, no cascade
3. If A's exported names changed: add all `reverse_deps` to the dirty queue

**Partial vs. full graph rebuild:**
- **Partial:** Preferred when fewer than 20% of files change. Update only dirty file records + edges.
- **Full:** Preferred when more than 50% of files change (e.g., after `git merge main` with many conflicts) or when `tool_version` changes.

### 5.3 Cascading Invalidation Depth

Without early-cutoff, a change to a widely-imported utility module (e.g., `utils.py`) cascades to every file that imports it. Practical mitigations:

1. **Interface hash:** Cache the hash of exported names for each file. Only propagate invalidation if the hash changes.
2. **Depth limit:** Limit cascade to depth 2 (direct importers + their importers). Beyond depth 2, the marginal benefit of precise invalidation drops below the cost of tracking it.
3. **Batch invalidation:** If cascade would touch more than 30% of files, fall back to full re-index.

---

## 6. Practical Implementation Patterns

### 6.1 SQLite Cache Backend — Full Schema

```sql
PRAGMA journal_mode=WAL;       -- concurrent reads + one writer
PRAGMA synchronous=NORMAL;     -- safe crash behavior, ~3x faster than FULL
PRAGMA cache_size=-65536;      -- 64MB page cache

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS file_cache (
    path TEXT PRIMARY KEY,
    mtime REAL NOT NULL,
    size INTEGER NOT NULL,
    content_hash TEXT,          -- SHA-256, computed lazily
    lang TEXT,
    parse_result TEXT NOT NULL, -- JSON: {functions, classes, calls, imports}
    exported_names_hash TEXT,   -- SHA-256 of sorted exported function/class names
    tool_version TEXT NOT NULL,
    indexed_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS call_graph (
    caller_file TEXT NOT NULL,
    caller_func TEXT NOT NULL,
    callee_name TEXT NOT NULL,
    PRIMARY KEY (caller_file, caller_func, callee_name)
);

CREATE TABLE IF NOT EXISTS imports (
    importer TEXT NOT NULL,
    importee TEXT NOT NULL,
    PRIMARY KEY (importer, importee)
);

CREATE INDEX IF NOT EXISTS idx_imports_importee ON imports(importee);
```

### 6.2 Incremental Update Algorithm

```python
def incremental_update(project_root, cache_db):
    """Run incremental update: only re-parse dirty files."""
    conn = open_cache(cache_db)

    # Step 1: Identify dirty files
    dirty = find_dirty_files(project_root, conn)

    # Step 2: Identify cascade dirty (files that import from dirty files)
    cascade_dirty = find_cascade_dirty(dirty, conn)
    all_dirty = dirty | cascade_dirty

    # Step 3: Check if full rebuild is cheaper
    total_files = get_total_file_count(conn)
    if len(all_dirty) > total_files * 0.5:
        return full_rebuild(project_root, cache_db)

    # Step 4: Re-parse dirty files
    for file_path in all_dirty:
        if file_path.exists():
            result = parse_file(file_path.read_text(), file_path.suffix)
            update_cache(conn, file_path, result)
        else:
            # File deleted — remove from cache and edges
            remove_from_cache(conn, file_path)

    # Step 5: Reconstruct output from cache
    return build_output_from_cache(conn, project_root)

def find_dirty_files(root, conn):
    """Fast dirty detection using mtime+size; verify with hash if uncertain."""
    import hashlib, os
    dirty = set()
    git_files = get_git_files(root)

    # Batch fetch cache records
    cached = {row[0]: row[1:] for row in
              conn.execute("SELECT path, mtime, size, content_hash FROM file_cache")}

    for fp in git_files:
        stat = fp.stat()
        rel = str(fp.relative_to(root))

        if rel not in cached:
            dirty.add(fp)
            continue

        c_mtime, c_size, c_hash = cached[rel]
        if abs(stat.st_mtime - c_mtime) < 0.001 and stat.st_size == c_size:
            continue  # Fast path: clean

        # mtime or size changed — verify with content hash
        h = hashlib.sha256(fp.read_bytes()).hexdigest()
        if h != c_hash:
            dirty.add(fp)

    # Also check for deleted files
    cached_paths = set(cached.keys())
    current_paths = {str(fp.relative_to(root)) for fp in git_files}
    deleted = cached_paths - current_paths
    for d in deleted:
        dirty.add(root / d)  # Will be handled as deletion

    return dirty
```

### 6.3 Lock-Free Concurrent Indexing

For 50k+ files, parallelise parsing across CPU cores using `concurrent.futures`:

```python
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

def parse_batch_parallel(dirty_files, max_workers=None):
    """Parse dirty files in parallel using process pool."""
    if max_workers is None:
        max_workers = max(1, multiprocessing.cpu_count() - 1)

    results = {}
    # Use process pool (not thread pool) — parsing is CPU-bound and GIL-bound
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(parse_one_file, fp): fp for fp in dirty_files}
        for future in as_completed(futures):
            fp = futures[future]
            try:
                results[fp] = future.result()
            except Exception as e:
                results[fp] = {'error': str(e)}
    return results
```

**SQLite and concurrency:** SQLite WAL mode supports one writer + many concurrent readers. With parallel parsing:
- **Read phase** (stat, hash check): fully concurrent, no locks needed
- **Write phase** (update cache): serialize via SQLite's WAL; batch writes in a single transaction for speed

```python
# Batch write — much faster than one transaction per file
with conn:
    conn.executemany(
        "INSERT OR REPLACE INTO file_cache VALUES (?,?,?,?,?,?,?,?,?)",
        rows  # list of tuples built during parallel parse phase
    )
```

### 6.4 Background Process vs. Foreground Hook

| Criterion | Background daemon | Foreground hook (current) |
|-----------|-------------------|---------------------------|
| Index freshness | Always current | Stale until hook fires |
| CPU impact | Continuous (low) | Burst on hook fire |
| Implementation | PID file, startup/shutdown | Simple subprocess |
| Crash behavior | May miss events | Idempotent restart |
| WSL2 compatibility | inotify works for WSL2 files | No issues |
| User visibility | Invisible | User sees "refreshing..." |

**For this project's use case:** The stop hook (`stop_hook.py`) fires after every Claude Code session and is a good compromise. Adding a git `post-commit` hook would cover the "made changes outside Claude" scenario. A full background daemon adds complexity that likely exceeds the benefit for most users.

### 6.5 Adaptive Compression

The current `compress_if_needed()` function does 5-step progressive compression. With incremental updates, we can be smarter:

1. **Skip compression for unchanged sections:** If 90% of files are clean, re-compress only the 10% that changed.
2. **Track compression ratio per file type:** Markdown docs compress differently from Python code.
3. **Store pre-compression data in cache, apply compression only at output time:** Separates the concerns of caching (correctness) from compression (size target).

---

## 7. Recommended Implementation Roadmap

### Phase 1: SQLite Cache + git-diff Dirty Detection (Highest ROI)
**Expected speedup:** Full parse 15–30s → Incremental 0.5–3s (depends on change count)

1. Add SQLite cache backend (`~/.claude-code-project-index/cache.db`)
2. On each run, detect dirty files via `git diff --name-only $LAST_SHA HEAD` + mtime scan of untracked
3. Re-parse only dirty files; read clean file data from cache
4. Store `indexed_at_commit` in `_meta`
5. Cache versioning: invalidate all on `tool_version` change

### Phase 2: Cascade Invalidation
1. Add `imports` table to track inter-file dependencies
2. When file A is dirty, mark A's importers as dirty too (depth-1 cascade)
3. Early cutoff: skip cascade if A's exported names hash is unchanged

### Phase 3: git Hook Auto-indexing
1. Install `post-commit` hook during `install.sh`
2. Hook runs incremental indexer in background
3. Add `post-merge` and `post-checkout` hooks for branch switches

### Phase 4: File Watcher Daemon (Optional)
1. `watchdog`-based daemon for non-git-hook scenarios (editor saves between commits)
2. PID file management, graceful shutdown
3. Watchman integration if available

---

## 8. Key Design Principles (Distilled)

1. **Two-tier dirty detection:** mtime+size as fast gate; SHA-256 only on mismatch. Never hash all files on startup.
2. **SQLite over JSON for 50k+ files:** Single indexed lookup vs. full JSON deserialization.
3. **Cache versioning is non-negotiable:** Every cache entry must carry `tool_version`. Forget this and you will debug ghost bugs for hours.
4. **git is the source of truth for commits:** Use `git diff --name-only` for committed changes; mtime scan only for working-tree edits.
5. **Atomic writes always:** `tempfile.mkstemp` + `os.replace()` for JSON; SQLite transactions for cache DB. Never write-in-place.
6. **Early cutoff on interface change:** Do not cascade invalidation if exported names are unchanged.
7. **Batch process pool for CPU-bound parsing:** Python's GIL makes threading useless for CPU-bound regex parsing; use `ProcessPoolExecutor`.
8. **Debounce file watcher events:** 500ms minimum; editors emit 5–10 events per save.
9. **Fallback to full rebuild when more than 50% dirty:** Incremental overhead exceeds benefit at high dirty ratios.
10. **Integrity check on cache open:** `PRAGMA integrity_check` on SQLite; checksum verify on JSON. Never trust cache blindly.

---

## Sources

- [Salsa Algorithm Explained — Medium](https://medium.com/@eliah.lakhin/salsa-algorithm-explained-c5d6df1dd291)
- [Durable Incrementality — rust-analyzer blog](https://rust-analyzer.github.io/blog/2023/07/24/durable-incrementality.html)
- [rust-analyzer Architecture Overview](https://readmex.com/en-US/rust-lang/rust-analyzer/page-484f201a4-7e5a-4816-ac24-ca2701d64784)
- [rust-analyzer Salsa docs](https://docs.rs/rust-analyzer-salsa/latest/salsa/)
- [Watchman — Facebook file watching service](https://facebook.github.io/watchman/)
- [ELI5: Watchman — Facebook Developers](https://developers.facebook.com/blog/post/2021/03/15/eli5-watchman-watching-changes-build-faster/)
- [GitHub: facebook/watchman](https://github.com/facebook/watchman)
- [Announcing SCIP — Sourcegraph Blog](https://sourcegraph.com/blog/announcing-scip)
- [Writing a SCIP Indexer — Sourcegraph Docs](https://sourcegraph.com/docs/code-search/code-navigation/writing_an_indexer)
- [Tree-sitter: Incremental Parsing](https://tomassetti.me/incremental-parsing-using-tree-sitter/)
- [Incremental Parsing with Tree-sitter (2026)](https://dasroot.net/posts/2026/02/incremental-parsing-tree-sitter-code-analysis/)
- [GitHub: tree-sitter/tree-sitter](https://github.com/tree-sitter/tree-sitter)
- [Mypy Daemon (dmypy) Documentation](https://mypy.readthedocs.io/en/stable/mypy_daemon.html)
- [Persistent pyright server discussion](https://github.com/microsoft/pyright/discussions/5974)
- [GitHub: gorakhargosh/watchdog](https://github.com/gorakhargosh/watchdog)
- [Python Watchdog 101](https://www.pythonsnacks.com/p/python-watchdog-file-directory-updates)
- [Practical Dependency Tracking for Python](https://amakelov.github.io/blog/deps/)
- [Cascading Cache Invalidation — Philip Walton](https://philipwalton.com/articles/cascading-cache-invalidation/)
- [Cache Invalidation and Reactive Systems — Skip Labs](https://skiplabs.io/blog/cache_invalidation)
- [Red/Green Dependency Tracking — Rust Issue #42293](https://github.com/rust-lang/rust/issues/42293)
- [codebase-memory-mcp — GitHub](https://github.com/DeusData/codebase-memory-mcp)
- [Building Fast and Compact SQLite Cache — DEV Community](https://dev.to/sjdonado/building-a-fast-and-compact-sqlite-cache-store-2h9g)
- [Don't Pickle Your Data — Ben Frederickson](https://www.benfrederickson.com/dont-pickle-your-data/)
- [When JSON Sucks — SQLite Enlightenment](https://pl-rants.net/posts/when-not-json/)
- [Atomic File Write Pattern — ActiveState](https://code.activestate.com/recipes/579097-safely-and-atomically-write-to-a-file/)
- [Crash-safe JSON at Scale — DEV Community](https://dev.to/constanta/crash-safe-json-at-scale-atomic-writes-recovery-without-a-db-3aic)
- [VS Code Language Server Extension Guide](https://code.visualstudio.com/api/language-extensions/language-server-extension-guide)
- [LSP Overview — Microsoft Learn](https://learn.microsoft.com/en-us/visualstudio/extensibility/language-server-protocol?view=visualstudio)
- [Parallel Incremental Indexing — Apache Lucene Wiki](https://cwiki.apache.org/confluence/display/lucene/ParallelIncrementalIndexing)
- [CocoIndex: Incremental Indexing for AI Agents — Medium](https://medium.com/@cocoindex.io/building-a-real-time-data-substrate-for-ai-agents-the-architecture-behind-cocoindex-729981f0f3a4)
- [Git Hooks Reference — git-scm.com](https://git-scm.com/docs/githooks)
- [gitflow-incremental-builder — GitHub](https://github.com/gitflow-incremental-builder/gitflow-incremental-builder)
