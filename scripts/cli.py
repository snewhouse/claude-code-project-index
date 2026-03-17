#!/usr/bin/env python3
"""CLI interface for querying PROJECT_INDEX.json.

Usage:
    python3 cli.py query who-calls <symbol> [--depth N]
    python3 cli.py query blast-radius <symbol> [--depth N]
    python3 cli.py query dead-code
    python3 cli.py query deps <file> [--depth N]
    python3 cli.py query search <pattern> [--max N]
    python3 cli.py query summary <file>
"""

import argparse
import json
import sys
from pathlib import Path

# Add scripts/ to path
sys.path.insert(0, str(Path(__file__).parent))
from query_engine import QueryEngine


def find_index() -> Path:
    """Find PROJECT_INDEX.json by searching up from CWD."""
    current = Path.cwd()
    while current != current.parent:
        index_path = current / 'PROJECT_INDEX.json'
        if index_path.exists():
            return index_path
        current = current.parent
    # Check CWD last
    fallback = Path.cwd() / 'PROJECT_INDEX.json'
    if fallback.exists():
        return fallback
    print("Error: PROJECT_INDEX.json not found", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='Query PROJECT_INDEX.json')
    subparsers = parser.add_subparsers(dest='command')

    # query subcommand
    query_parser = subparsers.add_parser('query', help='Query the index')
    query_sub = query_parser.add_subparsers(dest='query_type')

    # who-calls
    wc = query_sub.add_parser('who-calls', help='Find callers of a symbol')
    wc.add_argument('symbol', help='Symbol name')
    wc.add_argument('--depth', type=int, default=1, help='Traversal depth')

    # blast-radius
    br = query_sub.add_parser('blast-radius', help='Estimate change impact')
    br.add_argument('symbol', help='Symbol name')
    br.add_argument('--depth', type=int, default=3, help='Max depth')

    # dead-code
    query_sub.add_parser('dead-code', help='Find uncalled functions')

    # deps
    dp = query_sub.add_parser('deps', help='Trace dependencies')
    dp.add_argument('file', help='File path')
    dp.add_argument('--depth', type=int, default=5, help='Max depth')

    # search
    sr = query_sub.add_parser('search', help='Search symbols')
    sr.add_argument('pattern', help='Regex pattern')
    sr.add_argument('--max', type=int, default=50, help='Max results')

    # summary
    sm = query_sub.add_parser('summary', help='Summarize a file')
    sm.add_argument('file', help='File path')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    index_path = find_index()
    qe = QueryEngine.from_file(index_path)

    if args.query_type == 'who-calls':
        result = qe.who_calls(args.symbol, depth=args.depth)
        print(json.dumps(result, indent=2))
    elif args.query_type == 'blast-radius':
        result = qe.blast_radius(args.symbol, max_depth=args.depth)
        print(json.dumps(result, indent=2))
    elif args.query_type == 'dead-code':
        result = qe.dead_code()
        print(json.dumps(result, indent=2))
    elif args.query_type == 'deps':
        result = qe.dependency_chain(args.file, max_depth=args.depth)
        print(json.dumps(result, indent=2))
    elif args.query_type == 'search':
        result = qe.search_symbols(args.pattern, max_results=args.max)
        print(json.dumps(result, indent=2))
    elif args.query_type == 'summary':
        result = qe.file_summary(args.file)
        if result:
            print(json.dumps(result, indent=2))
        else:
            print(f"File not found in index: {args.file}", file=sys.stderr)
            sys.exit(1)
    else:
        query_parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
