"""Tests for PageRank symbol importance."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


def test_pagerank_empty():
    """Empty edges returns empty scores."""
    from pagerank import compute_pagerank
    assert compute_pagerank([]) == {}


def test_pagerank_simple_chain():
    """A->B->C: C should have highest score (most incoming via chain)."""
    from pagerank import compute_pagerank
    edges = [['A', 'B'], ['B', 'C']]
    scores = compute_pagerank(edges)
    assert len(scores) == 3
    # All should be between 0.0 and 1.0
    for name, score in scores.items():
        assert 0.0 <= score <= 1.0


def test_pagerank_hub():
    """Hub pattern: A calls B,C,D — B,C,D all called by A."""
    from pagerank import compute_pagerank
    edges = [['A', 'B'], ['A', 'C'], ['A', 'D']]
    scores = compute_pagerank(edges)
    assert len(scores) == 4
    # A has no incoming, so its score should be lower
    # B, C, D have incoming from A, so their scores should be higher
    assert scores['B'] > 0
    assert scores['C'] > 0
    assert scores['D'] > 0


def test_pagerank_cycle():
    """Cycle: A->B->A should converge without infinite loop."""
    from pagerank import compute_pagerank
    edges = [['A', 'B'], ['B', 'A']]
    scores = compute_pagerank(edges)
    assert len(scores) == 2
    # Both should have similar scores due to symmetry
    assert abs(scores['A'] - scores['B']) < 0.1


def test_pagerank_normalized():
    """All scores are in 0.0-1.0 range, max is 1.0."""
    from pagerank import compute_pagerank
    edges = [['A', 'B'], ['A', 'C'], ['B', 'C'], ['C', 'A']]
    scores = compute_pagerank(edges)
    max_score = max(scores.values())
    assert abs(max_score - 1.0) < 0.01  # Max should be ~1.0 after normalization
    for score in scores.values():
        assert 0.0 <= score <= 1.0


def test_pagerank_single_edge():
    """Single edge A->B."""
    from pagerank import compute_pagerank
    scores = compute_pagerank([['A', 'B']])
    assert 'A' in scores
    assert 'B' in scores
    assert scores['B'] > 0


def test_pagerank_convergence():
    """Larger graph should converge within 20 iterations."""
    from pagerank import compute_pagerank
    edges = [[f'n{i}', f'n{(i+1) % 10}'] for i in range(10)]
    edges += [['n0', 'n5'], ['n3', 'n7']]
    scores = compute_pagerank(edges, iterations=20)
    assert len(scores) == 10
