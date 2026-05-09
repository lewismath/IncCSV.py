# tests/test_summary.py
from __future__ import annotations
import pytest
from inccsv._summary import IncSummary, summarise, print_summary
from inccsv._reader import IncFile


def make_file(metadata: dict, rows: list[dict]) -> IncFile:
    return IncFile(metadata=metadata, rows=rows, path="/data/test.inc")


def test_summarise_row_and_col_counts():
    f = make_file({}, [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}])
    s = summarise(f)
    assert s.n_rows == 2
    assert s.n_cols == 2

def test_summarise_columns():
    f = make_file({}, [{"time": "0", "temp": "21.4"}])
    s = summarise(f)
    assert s.columns == ["time", "temp"]

def test_summarise_empty_rows():
    f = make_file({}, [])
    s = summarise(f)
    assert s.n_rows == 0
    assert s.n_cols == 0
    assert s.columns == []

def test_summarise_metadata_key_count():
    f = make_file({"title": "T", "version": 1}, [{"x": "1"}])
    s = summarise(f)
    assert s.n_metadata_keys == 2

def test_summarise_section_keys_counted():
    f = make_file({"columns": {"time": "seconds", "temp": "Celsius"}}, [{"x": "1"}])
    s = summarise(f)
    assert s.n_metadata_keys == 2  # 2 keys inside the section
    assert s.sections == ["columns"]

def test_summarise_path():
    f = make_file({}, [{"x": "1"}])
    s = summarise(f)
    assert s.path == "/data/test.inc"

def test_summarise_returns_incSummary():
    f = make_file({}, [{"x": "1"}])
    assert isinstance(summarise(f), IncSummary)

def test_print_summary_includes_row_count(capsys):
    f = make_file({"title": "T"}, [{"x": "1"}, {"x": "2"}])
    print_summary(f)
    captured = capsys.readouterr()
    assert "2" in captured.out

def test_print_summary_includes_columns(capsys):
    f = make_file({}, [{"time": "0", "temp": "21.4"}])
    print_summary(f)
    captured = capsys.readouterr()
    assert "time" in captured.out
    assert "temp" in captured.out
