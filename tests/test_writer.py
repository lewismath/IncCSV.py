# tests/test_writer.py
from __future__ import annotations
import pytest
from inccsv._writer import write_inc
from inccsv._reader import read_inc


def test_write_basic_roundtrip(tmp_path):
    path = str(tmp_path / "out.inc")
    rows = [{"name": "Ada", "score": "10"}, {"name": "Babbage", "score": "12"}]
    metadata = {"title": "My Data", "version": 1}
    write_inc(path, rows, metadata=metadata)
    result = read_inc(path)
    assert result.metadata["title"] == "My Data"
    assert result.metadata["version"] == 1
    assert result.rows == rows

def test_write_empty_metadata(tmp_path):
    path = str(tmp_path / "out.inc")
    rows = [{"x": "1"}]
    write_inc(path, rows, metadata={})
    result = read_inc(path)
    assert result.metadata == {}
    assert result.rows == [{"x": "1"}]

def test_write_with_section(tmp_path):
    path = str(tmp_path / "out.inc")
    rows = [{"time": "0", "temp": "21.4"}]
    metadata = {"title": "Sensor Data", "columns": {"time": "seconds", "temp": "Celsius"}}
    write_inc(path, rows, metadata=metadata)
    result = read_inc(path)
    assert result.metadata["columns"]["time"] == "seconds"
    assert result.rows == rows

def test_write_string_that_looks_like_int_is_quoted(tmp_path):
    path = str(tmp_path / "out.inc")
    rows = [{"x": "1"}]
    # '42' as a Python str must survive roundtrip as str, not become int 42
    write_inc(path, rows, metadata={"id": "42"})
    result = read_inc(path)
    assert result.metadata["id"] == "42"
    assert isinstance(result.metadata["id"], str)

def test_write_string_with_quotes_escaped(tmp_path):
    path = str(tmp_path / "out.inc")
    rows = [{"x": "1"}]
    write_inc(path, rows, metadata={"note": 'say "hi"'})
    result = read_inc(path)
    assert result.metadata["note"] == 'say "hi"'

def test_write_invalid_float_raises():
    with pytest.raises(ValueError, match="int or str"):
        write_inc("/dev/null", [{"x": "1"}], metadata={"bad": 3.14})

def test_write_invalid_list_raises():
    with pytest.raises(ValueError, match="int or str"):
        write_inc("/dev/null", [{"x": "1"}], metadata={"bad": [1, 2]})

def test_write_empty_section_raises():
    with pytest.raises(ValueError, match="empty"):
        write_inc("/dev/null", [{"x": "1"}], metadata={"columns": {}})

def test_write_newline_in_value_raises():
    with pytest.raises(ValueError, match="newline"):
        write_inc("/dev/null", [{"x": "1"}], metadata={"bad": "line1\nline2"})

def test_write_semicolon_in_value_is_quoted(tmp_path):
    path = str(tmp_path / "out.inc")
    write_inc(path, [], metadata={"sep": "a;b"})
    content = (tmp_path / "out.inc").read_text()
    assert 'sep = "a;b"' in content

def test_write_hash_in_value_is_quoted(tmp_path):
    path = str(tmp_path / "out.inc")
    write_inc(path, [], metadata={"note": "see #3"})
    content = (tmp_path / "out.inc").read_text()
    assert 'note = "see #3"' in content

def test_write_equals_in_value_is_quoted(tmp_path):
    path = str(tmp_path / "out.inc")
    write_inc(path, [], metadata={"expr": "x=y"})
    content = (tmp_path / "out.inc").read_text()
    assert 'expr = "x=y"' in content

def test_write_bracket_in_value_is_quoted(tmp_path):
    path = str(tmp_path / "out.inc")
    write_inc(path, [], metadata={"val": "[foo]"})
    content = (tmp_path / "out.inc").read_text()
    assert 'val = "[foo]"' in content

def test_write_carriage_return_raises(tmp_path):
    path = str(tmp_path / "out.inc")
    with pytest.raises(ValueError, match="newlines"):
        write_inc(path, [], metadata={"key": "a\rb"})

def test_write_custom_delimiter(tmp_path):
    path = str(tmp_path / "out.inc")
    rows = [{"name": "Ada", "score": "10"}]
    write_inc(path, rows, metadata={}, delimiter=";")
    # Read back with explicit delimiter since no [structure] section was written
    result = read_inc(path, delimiter=";")
    assert result.rows == [{"name": "Ada", "score": "10"}]

def test_write_no_rows(tmp_path):
    path = str(tmp_path / "out.inc")
    write_inc(path, [], metadata={"title": "Empty"})
    result = read_inc(path)
    assert result.metadata["title"] == "Empty"
    assert result.rows == []

def test_write_bool_raises():
    with pytest.raises(ValueError, match="int or str"):
        write_inc("/dev/null", [{"x": "1"}], metadata={"flag": True})

def test_write_ragged_rows_raises(tmp_path):
    path = str(tmp_path / "out.inc")
    rows = [{"a": "1", "b": "2"}, {"a": "3", "c": "4"}]  # row 1 has 'c' not 'b'
    with pytest.raises(ValueError, match="Row 1"):
        write_inc(path, rows)
