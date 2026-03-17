"""Tests for cross-file import resolution."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


def test_build_import_map_simple(tmp_path):
    """build_import_map maps dotted names to file paths."""
    from index_utils import build_import_map
    # Create a simple package structure
    (tmp_path / 'pkg').mkdir()
    (tmp_path / 'pkg' / '__init__.py').write_text('')
    (tmp_path / 'pkg' / 'utils.py').write_text('def helper(): pass')
    (tmp_path / 'main.py').write_text('from pkg.utils import helper')

    import_map = build_import_map(tmp_path)
    assert 'pkg.utils' in import_map
    assert import_map['pkg.utils'] == 'pkg/utils.py'
    assert 'pkg' in import_map  # package __init__.py
    assert 'main' in import_map


def test_build_import_map_nested(tmp_path):
    """build_import_map handles nested packages."""
    from index_utils import build_import_map
    (tmp_path / 'a').mkdir()
    (tmp_path / 'a' / '__init__.py').write_text('')
    (tmp_path / 'a' / 'b').mkdir()
    (tmp_path / 'a' / 'b' / '__init__.py').write_text('')
    (tmp_path / 'a' / 'b' / 'c.py').write_text('def deep(): pass')

    import_map = build_import_map(tmp_path)
    assert 'a.b.c' in import_map
    assert import_map['a.b.c'] == 'a/b/c.py'


def test_build_import_map_no_py_files(tmp_path):
    """build_import_map returns empty dict when no .py files exist."""
    from index_utils import build_import_map
    (tmp_path / 'readme.txt').write_text('hello')
    import_map = build_import_map(tmp_path)
    assert import_map == {}


def test_resolve_cross_file_edges_simple():
    """resolve_cross_file_edges creates edges when calls match imports."""
    from index_utils import resolve_cross_file_edges
    index = {
        'files': {
            'main.py': {
                'language': 'python',
                'parsed': True,
                'imports': ['utils'],
                'functions': {
                    'run': {
                        'line': 3,
                        'signature': '()',
                        'calls': ['helper']
                    }
                }
            },
            'utils.py': {
                'language': 'python',
                'parsed': True,
                'functions': {
                    'helper': {
                        'line': 1,
                        'signature': '()',
                    }
                }
            }
        }
    }
    import_map = {'utils': 'utils.py', 'main': 'main.py'}
    edges = resolve_cross_file_edges(index, import_map)
    assert len(edges) >= 1
    # Should have an edge from main.py:run -> utils.py:helper
    edge_strs = [f"{e[0]}->{e[1]}" for e in edges]
    assert any('main.py:run' in s and 'utils.py:helper' in s for s in edge_strs)


def test_resolve_cross_file_edges_no_match():
    """No edges when calls don't match any imported file's functions."""
    from index_utils import resolve_cross_file_edges
    index = {
        'files': {
            'main.py': {
                'language': 'python',
                'parsed': True,
                'imports': ['os'],
                'functions': {
                    'run': {'line': 1, 'signature': '()', 'calls': ['getcwd']}
                }
            }
        }
    }
    import_map = {'main': 'main.py'}
    edges = resolve_cross_file_edges(index, import_map)
    assert len(edges) == 0


def test_resolve_cross_file_edges_class_methods():
    """Cross-file edges work with class methods as callers."""
    from index_utils import resolve_cross_file_edges
    index = {
        'files': {
            'app.py': {
                'language': 'python',
                'parsed': True,
                'imports': ['db'],
                'functions': {},
                'classes': {
                    'App': {
                        'line': 1,
                        'methods': {
                            'start': {
                                'line': 2,
                                'signature': '(self)',
                                'calls': ['connect']
                            }
                        }
                    }
                }
            },
            'db.py': {
                'language': 'python',
                'parsed': True,
                'functions': {
                    'connect': {'line': 1, 'signature': '()'}
                }
            }
        }
    }
    import_map = {'app': 'app.py', 'db': 'db.py'}
    edges = resolve_cross_file_edges(index, import_map)
    assert len(edges) == 1
    assert edges[0] == ['app.py:App.start', 'db.py:connect', 'call']


def test_resolve_cross_file_edges_no_self_edges():
    """A file importing itself should not create edges."""
    from index_utils import resolve_cross_file_edges
    index = {
        'files': {
            'mod.py': {
                'language': 'python',
                'parsed': True,
                'imports': ['mod'],
                'functions': {
                    'a': {'line': 1, 'signature': '()', 'calls': ['b']},
                    'b': {'line': 5, 'signature': '()'}
                }
            }
        }
    }
    import_map = {'mod': 'mod.py'}
    edges = resolve_cross_file_edges(index, import_map)
    assert len(edges) == 0


def test_resolve_cross_file_edges_missing_keys():
    """Gracefully handles files without imports or functions."""
    from index_utils import resolve_cross_file_edges
    index = {
        'files': {
            'empty.py': {
                'language': 'python',
                'parsed': True,
            },
            'no_funcs.py': {
                'language': 'python',
                'parsed': True,
                'imports': ['empty'],
            }
        }
    }
    import_map = {'empty': 'empty.py', 'no_funcs': 'no_funcs.py'}
    edges = resolve_cross_file_edges(index, import_map)
    assert len(edges) == 0


def test_schema_backward_compatible():
    """xg key is additive - doesn't replace existing g key."""
    from index_utils import resolve_cross_file_edges
    index = {
        'files': {
            'a.py': {
                'language': 'python',
                'parsed': True,
                'imports': ['b'],
                'functions': {'f': {'line': 1, 'signature': '()', 'calls': ['g']}}
            },
            'b.py': {
                'language': 'python',
                'parsed': True,
                'functions': {'g': {'line': 1, 'signature': '()'}}
            }
        }
    }
    import_map = {'a': 'a.py', 'b': 'b.py'}
    edges = resolve_cross_file_edges(index, import_map)
    # Returns list of edges, doesn't modify index
    assert isinstance(edges, list)
    for edge in edges:
        assert len(edge) == 3  # [source, target, relation_type]
        assert edge[2] == 'call'
