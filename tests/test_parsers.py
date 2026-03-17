"""Characterization tests for parser functions in index_utils.py.

These tests capture CURRENT behavior of the parsers. They are not
aspirational — they assert what the code actually does today.
"""

from index_utils import (
    extract_python_signatures,
    extract_javascript_signatures,
    extract_shell_signatures,
)


# ---------------------------------------------------------------------------
# Python parser
# ---------------------------------------------------------------------------

def test_python_simple_function():
    """A plain function definition is captured with name, line, and signature."""
    source = '''\
def foo(x: int) -> str:
    """Convert int to str."""
    return str(x)
'''
    result = extract_python_signatures(source)
    funcs = result['functions']

    assert 'foo' in funcs, f"Expected 'foo' in functions, got: {list(funcs)}"
    foo = funcs['foo']
    assert isinstance(foo, dict)
    assert 'line' in foo
    assert foo['line'] == 1
    assert '(x: int)' in foo['signature']
    assert '-> str' in foo['signature']
    # Docstring should be captured
    assert 'doc' in foo
    assert 'Convert' in foo['doc']


def test_python_class_with_methods():
    """A class with __init__ and a method is captured correctly."""
    source = '''\
class MyClass:
    """A simple class."""

    def __init__(self, value: int):
        """Initialize with value."""
        self.value = value

    def get_value(self) -> int:
        """Return the value."""
        return self.value
'''
    result = extract_python_signatures(source)
    classes = result['classes']

    assert 'MyClass' in classes, f"Expected 'MyClass' in classes, got: {list(classes)}"
    cls = classes['MyClass']
    assert isinstance(cls, dict)
    assert 'methods' in cls

    methods = cls['methods']
    assert '__init__' in methods, f"Expected '__init__' in methods, got: {list(methods)}"
    assert 'get_value' in methods, f"Expected 'get_value' in methods, got: {list(methods)}"

    get_value = methods['get_value']
    assert isinstance(get_value, dict)
    assert '-> int' in get_value['signature']


def test_python_async_function():
    """An async function is captured and its signature indicates async."""
    source = '''\
async def fetch(url: str) -> None:
    """Fetch a URL."""
    pass
'''
    result = extract_python_signatures(source)
    funcs = result['functions']

    assert 'fetch' in funcs, f"Expected 'fetch' in functions, got: {list(funcs)}"
    fetch = funcs['fetch']
    assert 'async' in fetch['signature']


def test_python_decorated_function():
    """A decorated function captures the decorator in func_info."""
    source = '''\
@staticmethod
def bar(x):
    """A static-style helper."""
    return x
'''
    result = extract_python_signatures(source)
    funcs = result['functions']

    assert 'bar' in funcs, f"Expected 'bar' in functions, got: {list(funcs)}"
    bar = funcs['bar']
    assert isinstance(bar, dict)
    assert 'decorators' in bar
    assert 'staticmethod' in bar['decorators']


# ---------------------------------------------------------------------------
# JavaScript parser
# ---------------------------------------------------------------------------

def test_js_arrow_function():
    """A const arrow function is captured in the functions dict."""
    source = "const add = (a, b) => a + b;\n"
    result = extract_javascript_signatures(source)
    funcs = result['functions']

    assert 'add' in funcs, f"Expected 'add' in functions, got: {list(funcs)}"
    add = funcs['add']
    # May be stored as a signature string or a dict
    if isinstance(add, dict):
        sig = add.get('signature', '')
    else:
        sig = add
    assert isinstance(sig, str)


def test_js_class():
    """A JS class with constructor and method is captured."""
    source = '''\
class MyClass {
    constructor(value) {
        this.value = value;
    }
    greet() {
        return 'hello';
    }
}
'''
    result = extract_javascript_signatures(source)
    classes = result['classes']

    assert 'MyClass' in classes, f"Expected 'MyClass' in classes, got: {list(classes)}"
    cls = classes['MyClass']
    assert isinstance(cls, dict)
    assert 'methods' in cls
    methods = cls['methods']
    # constructor and greet should be present
    assert len(methods) >= 1, f"Expected at least 1 method, got: {list(methods)}"


# ---------------------------------------------------------------------------
# Shell parser
# ---------------------------------------------------------------------------

def test_shell_style1():
    """A style-1 shell function (name() {}) is captured.

    Characterization note: the parser detects parameters by scanning body lines
    for $N usage AFTER an opening brace. When '{' appears on the same line as
    the function definition, the brace-tracking loop starts at i+1 and never
    sees the opening brace, so params remains empty and signature is '()'.
    """
    source = '''\
greet() {
    echo "hello $1"
}
'''
    result = extract_shell_signatures(source)
    funcs = result['functions']

    assert 'greet' in funcs, f"Expected 'greet' in functions, got: {list(funcs)}"
    greet = funcs['greet']

    # May be a dict (with signature key) or a plain string
    if isinstance(greet, dict):
        sig = greet.get('signature', '')
    else:
        sig = greet

    assert isinstance(sig, str)
    # Current behavior: opening brace on same line means params are not detected.
    assert sig == '()', f"Expected '()' (current behavior), got: {sig!r}"


def test_shell_style2():
    """A style-2 shell function (function name {}) is captured.

    Characterization note: same brace-detection issue as style-1 — when '{' is
    on the definition line, param scanning sees no brace in body lines, so
    params remain empty and signature is '()'.
    """
    source = '''\
function cleanup {
    rm -rf "$1"
}
'''
    result = extract_shell_signatures(source)
    funcs = result['functions']

    assert 'cleanup' in funcs, f"Expected 'cleanup' in functions, got: {list(funcs)}"
    cleanup = funcs['cleanup']

    if isinstance(cleanup, dict):
        sig = cleanup.get('signature', '')
    else:
        sig = cleanup

    assert isinstance(sig, str)
    # Current behavior: opening brace on same line means params are not detected.
    assert sig == '()', f"Expected '()' (current behavior), got: {sig!r}"
