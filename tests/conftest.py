"""Shared pytest fixtures for characterization tests."""

import sys
from pathlib import Path

# Make scripts/ importable
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

import pytest


@pytest.fixture
def sample_python_source():
    """A Python string with diverse constructs for parser characterization."""
    return '''\
import os
import sys
from pathlib import Path
from typing import Optional, List

MY_CONST = 42
GREETING = "hello"

class Color(str):
    """A simple color class."""

    DEFAULT = "red"

    def __init__(self, value: str):
        """Initialize color."""
        self._value = value

    def describe(self) -> str:
        """Return a description."""
        return f"color is {self._value}"

@staticmethod
def standalone_helper(x: int) -> str:
    """A standalone helper function."""
    return str(x)

async def fetch_data(url: str, timeout: int = 30) -> Optional[str]:
    """Asynchronously fetch data from a URL."""
    return None

@property
def cached_result():
    """A decorated property-like function."""
    return None
'''


@pytest.fixture
def sample_js_source():
    """A JavaScript string with diverse constructs for parser characterization."""
    return """\
import { readFile } from 'fs/promises';
import path from 'path';

const add = (a, b) => a + b;

class Calculator {
    constructor(precision) {
        this.precision = precision;
    }

    multiply(x, y) {
        return x * y;
    }
}

async function fetchJson(url) {
    const resp = await fetch(url);
    return resp.json();
}
"""


@pytest.fixture
def sample_shell_source():
    """A shell script string with diverse constructs for parser characterization."""
    return """\
#!/bin/bash

export APP_NAME=myapp
export VERSION=1.0

# Greet a user by name
greet() {
    echo "hello $1"
}

function cleanup {
    rm -rf "$1"
}

source ./lib/utils.sh
. ./lib/common.sh
"""


@pytest.fixture
def sample_index():
    """A dict mimicking the structure returned by build_index()."""
    return {
        "at": "2026-01-01T00:00:00",
        "root": "/tmp/test_project",
        "tree": ["project/", "├── scripts/", "└── tests/"],
        "f": {
            "s/main.py": ["p", ["main:1:():None:Entry point"], {}],
            "s/utils.py": ["p", ["helper:5:(x: int) -> str:None:A helper"], {}],
        },
        "g": [["main", "helper"]],
        "d": {"README.md": ["# Project", "## Usage"]},
        "deps": {"s/main.py": ["os", "sys"]},
        "_meta": {
            "target_size_k": 50,
            "actual_size_k": 2,
            "files_hash": "abc123",
            "generated_at": "2026-01-01T00:00:00",
        },
    }


@pytest.fixture
def tmp_project_dir(tmp_path):
    """A temporary directory with a minimal project structure."""
    # Create a fake .git directory
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n")

    # Create a sample Python file
    (tmp_path / "main.py").write_text(
        "def hello():\n    return 'world'\n"
    )

    # Create a subdirectory with another file
    src = tmp_path / "src"
    src.mkdir()
    (src / "utils.py").write_text(
        "def add(a, b):\n    return a + b\n"
    )

    return tmp_path
