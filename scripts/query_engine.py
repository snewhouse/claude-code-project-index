#!/usr/bin/env python3
"""Query engine for PROJECT_INDEX.json.

Provides 6 structural query methods for codebase analysis:
- who_calls: Find all callers of a symbol
- blast_radius: Estimate impact of changing a symbol
- dead_code: Find functions with no callers
- dependency_chain: Trace import dependencies
- search_symbols: Search for symbols by name pattern
- file_summary: Summarize a file's contents
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set


class QueryEngine:
    """Query engine for analyzing PROJECT_INDEX.json."""

    def __init__(self, index: Dict):
        """Initialize with a loaded index dict."""
        self.index = index
        self.files = index.get('f', index.get('files', {}))
        self.call_graph = index.get('g', [])
        self.cross_file_graph = index.get('xg', [])
        self.deps = index.get('deps', index.get('dependency_graph', {}))
        # Build reverse lookup indexes
        self._callers = {}  # symbol -> list of callers
        self._build_caller_index()

    def _build_caller_index(self):
        """Build reverse caller index from call graph edges."""
        # From intra-file call graph (g)
        for edge in self.call_graph:
            if len(edge) >= 2:
                caller, callee = edge[0], edge[1]
                self._callers.setdefault(callee, []).append(caller)
        # From cross-file graph (xg)
        for edge in self.cross_file_graph:
            if len(edge) >= 2:
                caller, callee = edge[0], edge[1]
                self._callers.setdefault(callee, []).append(caller)

    @classmethod
    def from_file(cls, index_path: Path) -> 'QueryEngine':
        """Load index from a JSON file."""
        with open(index_path) as f:
            index = json.load(f)
        return cls(index)

    def who_calls(self, symbol: str, depth: int = 1) -> List[str]:
        """Find all callers of a symbol, optionally with transitive callers.

        Args:
            symbol: Function or method name to search for
            depth: How many levels of callers to traverse (1=direct only)

        Returns:
            List of caller identifiers (e.g., "file.py:func_name")
        """
        result = set()
        current_level = {symbol}

        for _ in range(depth):
            next_level = set()
            for sym in current_level:
                callers = self._callers.get(sym, [])
                for caller in callers:
                    if caller not in result:
                        result.add(caller)
                        next_level.add(caller)
            current_level = next_level
            if not current_level:
                break

        return sorted(result)

    def blast_radius(self, symbol: str, max_depth: int = 3) -> Dict[str, List[str]]:
        """Estimate the impact of changing a symbol.

        Returns a dict with callers at each depth level.
        """
        result = {}
        seen = {symbol}
        current_level = {symbol}

        for depth in range(1, max_depth + 1):
            next_level = set()
            for sym in current_level:
                for caller in self._callers.get(sym, []):
                    if caller not in seen:
                        seen.add(caller)
                        next_level.add(caller)
            if next_level:
                result[f"depth_{depth}"] = sorted(next_level)
            current_level = next_level
            if not current_level:
                break

        return result

    def dead_code(self) -> List[str]:
        """Find functions that are never called by any other function.

        Returns list of "file:function" identifiers with no callers.
        """
        all_called = set()
        for edge in self.call_graph:
            if len(edge) >= 2:
                all_called.add(edge[1])
        for edge in self.cross_file_graph:
            if len(edge) >= 2:
                all_called.add(edge[1])

        dead = []
        for file_path, file_info in self.files.items():
            if not isinstance(file_info, dict):
                # Dense format: file_info is a list [lang, [funcs...], {classes}]
                if isinstance(file_info, list) and len(file_info) > 1:
                    funcs = file_info[1] if isinstance(file_info[1], list) else []
                    for func_str in funcs:
                        # Dense format: "name:line:sig:calls:doc"
                        func_name = func_str.split(':')[0] if isinstance(func_str, str) else ''
                        if func_name and func_name not in all_called:
                            dead.append(f"{file_path}:{func_name}")
                continue

            for func_name in file_info.get('functions', {}):
                if func_name not in all_called:
                    dead.append(f"{file_path}:{func_name}")

        return sorted(dead)

    def dependency_chain(self, file_path: str, max_depth: int = 5) -> Dict[str, List[str]]:
        """Trace import dependencies of a file.

        Returns dict of depth -> list of dependency file paths.
        """
        result = {}
        seen = {file_path}
        current_level = {file_path}

        for depth in range(1, max_depth + 1):
            next_level = set()
            for fp in current_level:
                deps = self.deps.get(fp, [])
                for dep in deps:
                    if dep not in seen:
                        seen.add(dep)
                        next_level.add(dep)
            if next_level:
                result[f"depth_{depth}"] = sorted(next_level)
            current_level = next_level
            if not current_level:
                break

        return result

    def search_symbols(self, pattern: str, max_results: int = 50) -> List[Dict[str, str]]:
        """Search for symbols matching a regex pattern.

        Returns list of {file, name, type, line} dicts.
        """
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            return []

        results = []
        for file_path, file_info in self.files.items():
            if not isinstance(file_info, dict):
                # Dense format
                if isinstance(file_info, list) and len(file_info) > 1:
                    funcs = file_info[1] if isinstance(file_info[1], list) else []
                    for func_str in funcs:
                        if isinstance(func_str, str):
                            parts = func_str.split(':')
                            name = parts[0]
                            if regex.search(name):
                                results.append({
                                    'file': file_path,
                                    'name': name,
                                    'type': 'function',
                                    'line': parts[1] if len(parts) > 1 else '0'
                                })
                continue

            for func_name, func_data in file_info.get('functions', {}).items():
                if regex.search(func_name):
                    line = func_data.get('line', 0) if isinstance(func_data, dict) else 0
                    results.append({
                        'file': file_path,
                        'name': func_name,
                        'type': 'function',
                        'line': str(line)
                    })

            for class_name, class_data in file_info.get('classes', {}).items():
                if regex.search(class_name):
                    line = class_data.get('line', 0) if isinstance(class_data, dict) else 0
                    results.append({
                        'file': file_path,
                        'name': class_name,
                        'type': 'class',
                        'line': str(line)
                    })

            if len(results) >= max_results:
                break

        return results[:max_results]

    def file_summary(self, file_path: str) -> Optional[Dict]:
        """Summarize a file's contents.

        Returns dict with functions, classes, imports, and purpose.
        """
        info = self.files.get(file_path)
        if info is None:
            return None

        if isinstance(info, dict):
            return {
                'language': info.get('language', 'unknown'),
                'functions': list(info.get('functions', {}).keys()),
                'classes': list(info.get('classes', {}).keys()),
                'imports': info.get('imports', []),
                'purpose': info.get('purpose', ''),
                'parsed': info.get('parsed', False)
            }

        # Dense format
        if isinstance(info, list):
            lang = info[0] if info else 'unknown'
            funcs = []
            if len(info) > 1 and isinstance(info[1], list):
                funcs = [f.split(':')[0] for f in info[1] if isinstance(f, str)]
            classes = list(info[2].keys()) if len(info) > 2 and isinstance(info[2], dict) else []
            return {
                'language': lang,
                'functions': funcs,
                'classes': classes,
                'imports': [],
                'purpose': '',
                'parsed': True
            }

        return None
