#!/usr/bin/env python3
"""PageRank-based symbol importance scoring.

Computes importance scores for functions/symbols based on their position
in the call graph. Uses power iteration (no external dependencies).

Scores are normalized 0.0-1.0 where 1.0 is the most important symbol.
"""

from typing import Dict, List, Tuple


def compute_pagerank(
    edges: List[List[str]],
    damping: float = 0.85,
    iterations: int = 20,
    tolerance: float = 1e-6
) -> Dict[str, float]:
    """Compute PageRank scores for symbols in a call graph.

    Args:
        edges: List of [caller, callee] pairs (from g and xg keys)
        damping: Damping factor (probability of following a link vs random jump)
        iterations: Maximum number of power iterations
        tolerance: Convergence threshold (stop early if max change < tolerance)

    Returns:
        Dict mapping symbol names to normalized importance scores (0.0-1.0).
        Empty dict if no edges provided.
    """
    if not edges:
        return {}

    # Build adjacency: outgoing links from each node
    nodes = set()
    outgoing = {}  # node -> set of targets
    incoming = {}  # node -> set of sources

    for edge in edges:
        if len(edge) < 2:
            continue
        src, dst = edge[0], edge[1]
        nodes.add(src)
        nodes.add(dst)
        outgoing.setdefault(src, set()).add(dst)
        incoming.setdefault(dst, set()).add(src)

    if not nodes:
        return {}

    n = len(nodes)
    node_list = sorted(nodes)  # Deterministic ordering
    node_idx = {name: i for i, name in enumerate(node_list)}

    # Initialize uniform scores
    scores = [1.0 / n] * n

    # Power iteration
    for _ in range(iterations):
        new_scores = [(1.0 - damping) / n] * n

        for i, node in enumerate(node_list):
            # Distribute this node's score to its outgoing links
            out_links = outgoing.get(node, set())
            if out_links:
                share = damping * scores[i] / len(out_links)
                for target in out_links:
                    j = node_idx[target]
                    new_scores[j] += share
            else:
                # Dangling node: distribute evenly
                share = damping * scores[i] / n
                for j in range(n):
                    new_scores[j] += share

        # Check convergence
        max_diff = max(abs(new_scores[i] - scores[i]) for i in range(n))
        scores = new_scores
        if max_diff < tolerance:
            break

    # Normalize to 0.0-1.0 range
    max_score = max(scores) if scores else 1.0
    if max_score > 0:
        normalized = {node_list[i]: scores[i] / max_score for i in range(n)}
    else:
        normalized = {node: 0.0 for node in node_list}

    return normalized
