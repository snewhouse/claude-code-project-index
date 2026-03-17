"""Tests for QueryEngine."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


def _make_test_index():
    """Create a test index for query engine tests."""
    return {
        'files': {
            'main.py': {
                'language': 'python',
                'parsed': True,
                'functions': {
                    'main': {'line': 1, 'signature': '()', 'calls': ['helper', 'process']},
                    'unused_func': {'line': 10, 'signature': '()'},
                },
                'imports': ['utils']
            },
            'utils.py': {
                'language': 'python',
                'parsed': True,
                'functions': {
                    'helper': {'line': 1, 'signature': '(x: int)', 'calls': ['deep_helper']},
                    'process': {'line': 5, 'signature': '(data)'},
                    'deep_helper': {'line': 10, 'signature': '()'},
                },
            },
        },
        'g': [['main', 'helper'], ['main', 'process'], ['helper', 'deep_helper']],
        'xg': [['main.py:main', 'utils.py:helper', 'call']],
        'deps': {'main.py': ['utils']},
    }


def test_who_calls_direct():
    from query_engine import QueryEngine
    qe = QueryEngine(_make_test_index())
    callers = qe.who_calls('helper')
    assert 'main' in callers


def test_who_calls_transitive():
    from query_engine import QueryEngine
    qe = QueryEngine(_make_test_index())
    callers = qe.who_calls('deep_helper', depth=2)
    assert 'helper' in callers
    assert 'main' in callers


def test_blast_radius():
    from query_engine import QueryEngine
    qe = QueryEngine(_make_test_index())
    impact = qe.blast_radius('deep_helper')
    assert 'depth_1' in impact
    assert 'helper' in impact['depth_1']


def test_dead_code():
    from query_engine import QueryEngine
    qe = QueryEngine(_make_test_index())
    dead = qe.dead_code()
    # unused_func and main (no one calls main) should be dead
    dead_names = [d.split(':')[-1] for d in dead]
    assert 'unused_func' in dead_names


def test_dependency_chain():
    from query_engine import QueryEngine
    qe = QueryEngine(_make_test_index())
    chain = qe.dependency_chain('main.py')
    assert 'depth_1' in chain
    assert 'utils' in chain['depth_1']


def test_search_symbols():
    from query_engine import QueryEngine
    qe = QueryEngine(_make_test_index())
    results = qe.search_symbols('help')
    names = [r['name'] for r in results]
    assert 'helper' in names
    assert 'deep_helper' in names


def test_search_symbols_regex():
    from query_engine import QueryEngine
    qe = QueryEngine(_make_test_index())
    results = qe.search_symbols('^main$')
    names = [r['name'] for r in results]
    assert 'main' in names
    assert 'unused_func' not in names


def test_file_summary():
    from query_engine import QueryEngine
    qe = QueryEngine(_make_test_index())
    summary = qe.file_summary('main.py')
    assert summary is not None
    assert 'main' in summary['functions']
    assert summary['language'] == 'python'


def test_file_summary_not_found():
    from query_engine import QueryEngine
    qe = QueryEngine(_make_test_index())
    assert qe.file_summary('nonexistent.py') is None


def test_from_file(tmp_path):
    import json
    from query_engine import QueryEngine
    index_path = tmp_path / 'test_index.json'
    index_path.write_text(json.dumps(_make_test_index()))
    qe = QueryEngine.from_file(index_path)
    assert len(qe.files) == 2
