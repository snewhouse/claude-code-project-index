"""Tests for AST-based Python parser."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


def test_ast_simple_function():
    """AST parser extracts a simple function with signature and docstring."""
    from index_utils import extract_python_signatures_ast
    source = 'def foo(x: int) -> str:\n    """Convert."""\n    return str(x)\n'
    result = extract_python_signatures_ast(source)
    assert 'functions' in result
    assert 'foo' in result['functions']
    foo = result['functions']['foo']
    assert '(x: int)' in foo['signature']
    assert '-> str' in foo['signature']
    assert foo['line'] == 1
    assert 'doc' in foo


def test_ast_class_with_methods():
    """AST parser extracts classes and their methods."""
    from index_utils import extract_python_signatures_ast
    source = '''class MyClass:
    """A class."""
    def __init__(self, value: int):
        """Init."""
        self.value = value
    def get_value(self) -> int:
        """Get."""
        return self.value
'''
    result = extract_python_signatures_ast(source)
    assert 'MyClass' in result['classes']
    cls = result['classes']['MyClass']
    assert '__init__' in cls['methods']
    assert 'get_value' in cls['methods']
    assert '-> int' in cls['methods']['get_value']['signature']


def test_ast_async_function():
    """AST parser handles async functions."""
    from index_utils import extract_python_signatures_ast
    source = 'async def fetch(url: str) -> None:\n    """Fetch."""\n    pass\n'
    result = extract_python_signatures_ast(source)
    assert 'fetch' in result['functions']
    assert 'async' in result['functions']['fetch']['signature']


def test_ast_decorated_function():
    """AST parser captures decorators."""
    from index_utils import extract_python_signatures_ast
    source = '@staticmethod\ndef bar(x):\n    """Help."""\n    return x\n'
    result = extract_python_signatures_ast(source)
    assert 'bar' in result['functions']
    assert 'decorators' in result['functions']['bar']
    assert 'staticmethod' in result['functions']['bar']['decorators']


def test_ast_nested_function_ignored():
    """AST parser only captures top-level functions, not nested ones."""
    from index_utils import extract_python_signatures_ast
    source = '''def outer():
    def inner():
        pass
    return inner()
'''
    result = extract_python_signatures_ast(source)
    assert 'outer' in result['functions']
    assert 'inner' not in result['functions']


def test_ast_complex_defaults():
    """AST parser handles complex default values."""
    from index_utils import extract_python_signatures_ast
    source = 'def func(x: int = 42, y: str = "hello", z: list = None) -> bool:\n    pass\n'
    result = extract_python_signatures_ast(source)
    assert 'func' in result['functions']
    assert '(x: int' in result['functions']['func']['signature']


def test_ast_dataclass():
    """AST parser handles dataclass decorators."""
    from index_utils import extract_python_signatures_ast
    source = '''from dataclasses import dataclass

@dataclass
class Point:
    """A point."""
    x: float
    y: float
'''
    result = extract_python_signatures_ast(source)
    assert 'Point' in result['classes']
    assert 'dataclass' in result['classes']['Point'].get('decorators', [])


def test_ast_imports():
    """AST parser extracts imports."""
    from index_utils import extract_python_signatures_ast
    source = '''import os
from pathlib import Path
from typing import Dict, List
'''
    result = extract_python_signatures_ast(source)
    assert 'imports' in result
    assert len(result['imports']) >= 2


def test_ast_constants():
    """AST parser extracts module-level constants."""
    from index_utils import extract_python_signatures_ast
    source = '''MAX_SIZE = 1024
DEFAULT_NAME = "hello"
'''
    result = extract_python_signatures_ast(source)
    assert 'constants' in result
    assert 'MAX_SIZE' in result['constants']


def test_ast_feature_flag_disabled():
    """When V2_AST_PARSER=0, parse_file uses regex parser."""
    from index_utils import parse_file, PARSER_REGISTRY
    os.environ['V2_AST_PARSER'] = '0'
    try:
        result = parse_file("def foo(): pass", '.py')
        assert result is not None
        assert 'functions' in result
    finally:
        os.environ.pop('V2_AST_PARSER', None)


def test_ast_syntax_error_fallback():
    """AST parser falls back to regex on SyntaxError."""
    from index_utils import extract_python_signatures_ast
    # This is valid-ish for regex but not valid Python syntax
    source = 'def foo(x):\n    return x\ndef bar(:\n    pass\n'
    result = extract_python_signatures_ast(source)
    # Should still get results (from regex fallback)
    assert 'functions' in result


def test_ast_inheritance():
    """AST parser captures class inheritance."""
    from index_utils import extract_python_signatures_ast
    source = '''class MyError(Exception):
    """Custom error."""
    pass
'''
    result = extract_python_signatures_ast(source)
    assert 'MyError' in result['classes']
    cls = result['classes']['MyError']
    assert 'inherits' in cls
    assert 'Exception' in cls['inherits']


def test_ast_enum_class():
    """AST parser handles enum classes (moved to enums section)."""
    from index_utils import extract_python_signatures_ast
    source = '''from enum import Enum
class Color(Enum):
    RED = 1
    GREEN = 2
    BLUE = 3
'''
    result = extract_python_signatures_ast(source)
    # Enum classes are moved from 'classes' to 'enums' section (matching regex parser behavior)
    assert 'enums' in result
    assert 'Color' in result['enums']
    assert 'RED' in result['enums']['Color']['values']
