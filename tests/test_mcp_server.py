"""Tests for MCP server graceful degradation."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


def test_find_index_returns_none_when_missing(tmp_path):
    """find_index returns None when no PROJECT_INDEX.json exists."""
    from mcp_server import find_index
    with patch('mcp_server.Path.cwd', return_value=tmp_path):
        result = find_index()
    assert result is None


def test_find_index_returns_path_when_exists(tmp_path):
    """find_index returns the path when PROJECT_INDEX.json exists."""
    index_file = tmp_path / 'PROJECT_INDEX.json'
    index_file.write_text('{}')
    from mcp_server import find_index
    with patch('mcp_server.Path.cwd', return_value=tmp_path):
        result = find_index()
    assert result == index_file


def test_get_engine_returns_none_when_no_index(tmp_path):
    """_get_engine returns None when no index file exists."""
    import mcp_server
    # Reset cache
    mcp_server._engine_cache["engine"] = None
    mcp_server._engine_cache["path"] = None
    with patch('mcp_server.find_index', return_value=None):
        result = mcp_server._get_engine()
    assert result is None


def test_get_engine_returns_engine_when_index_exists(tmp_path):
    """_get_engine returns a QueryEngine when index file exists."""
    import mcp_server
    from query_engine import QueryEngine
    index_file = tmp_path / 'PROJECT_INDEX.json'
    index_file.write_text(json.dumps({'f': {}, 'g': [], 'xg': [], 'deps': {}}))
    # Reset cache
    mcp_server._engine_cache["engine"] = None
    mcp_server._engine_cache["path"] = None
    with patch('mcp_server.find_index', return_value=index_file):
        result = mcp_server._get_engine()
    assert isinstance(result, QueryEngine)


def test_get_engine_caches_result(tmp_path):
    """_get_engine caches the engine and reuses it on subsequent calls."""
    import mcp_server
    index_file = tmp_path / 'PROJECT_INDEX.json'
    index_file.write_text(json.dumps({'f': {}, 'g': [], 'xg': [], 'deps': {}}))
    mcp_server._engine_cache["engine"] = None
    mcp_server._engine_cache["path"] = None
    with patch('mcp_server.find_index', return_value=index_file):
        engine1 = mcp_server._get_engine()
        engine2 = mcp_server._get_engine()
    assert engine1 is engine2


@patch('mcp_server.HAS_FASTMCP', True)
def test_create_mcp_server_succeeds_without_index():
    """create_mcp_server() does NOT crash when no PROJECT_INDEX.json exists."""
    # Mock FastMCP since it may not be installed in test env
    mock_mcp_class = MagicMock()
    mock_mcp_instance = MagicMock()
    mock_mcp_class.return_value = mock_mcp_instance
    # tool() returns a decorator that registers the function
    mock_mcp_instance.tool.return_value = lambda fn: fn

    with patch('mcp_server.FastMCP', mock_mcp_class):
        from mcp_server import create_mcp_server
        server = create_mcp_server()
    # Server created successfully — tools registered
    assert mock_mcp_instance.tool.call_count == 6


def test_no_index_message_is_valid_json():
    """NO_INDEX_MSG is valid JSON with error and hint keys."""
    from mcp_server import NO_INDEX_MSG
    parsed = json.loads(NO_INDEX_MSG)
    assert 'error' in parsed
    assert 'hint' in parsed
    assert '/index' in parsed['hint']


def test_server_instructions_present():
    """SERVER_INSTRUCTIONS is a non-empty string."""
    from mcp_server import SERVER_INSTRUCTIONS
    assert isinstance(SERVER_INSTRUCTIONS, str)
    assert len(SERVER_INSTRUCTIONS) > 50
    assert 'who_calls' in SERVER_INSTRUCTIONS
    assert 'blast_radius' in SERVER_INSTRUCTIONS
