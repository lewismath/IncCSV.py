# tests/test_parser.py
from __future__ import annotations
import pytest
from inccsv._parser import (
    _is_delimiter_line,
    _parse_value,
    split_inc,
    parse_metadata,
)


# --- _is_delimiter_line ---

def test_delimiter_three_hyphens():
    assert _is_delimiter_line("---\n") is True

def test_delimiter_four_hyphens():
    assert _is_delimiter_line("----") is True

def test_delimiter_with_leading_whitespace():
    assert _is_delimiter_line("  ---  \n") is True

def test_delimiter_with_hash_comment():
    assert _is_delimiter_line("--- # end of metadata\n") is True

def test_delimiter_with_semicolon_comment():
    assert _is_delimiter_line("--- ; comment\n") is True

def test_delimiter_unicode_en_dashes():
    assert _is_delimiter_line("–––\n") is True  # en-dashes

def test_delimiter_unicode_em_dashes():
    assert _is_delimiter_line("———\n") is True  # em-dashes

def test_delimiter_too_short():
    assert _is_delimiter_line("--\n") is False

def test_delimiter_not_dashes():
    assert _is_delimiter_line("key = value\n") is False

def test_delimiter_dashes_then_junk():
    assert _is_delimiter_line("--- not a comment marker\n") is False


# --- _parse_value ---

def test_parse_value_int():
    result = _parse_value("42")
    assert result == 42
    assert isinstance(result, int)

def test_parse_value_negative_int():
    assert _parse_value("-5") == -5

def test_parse_value_positive_sign_int():
    assert _parse_value("+7") == 7

def test_parse_value_plain_string():
    assert _parse_value("hello world") == "hello world"
    assert isinstance(_parse_value("hello world"), str)

def test_parse_value_quoted_string():
    result = _parse_value('"hello world"')
    assert result == "hello world"
    assert isinstance(result, str)

def test_parse_value_quoted_integer_stays_string():
    result = _parse_value('"42"')
    assert result == "42"
    assert isinstance(result, str)

def test_parse_value_escape_quote():
    assert _parse_value(r'"say \"hi\""') == 'say "hi"'

def test_parse_value_escape_backslash():
    assert _parse_value(r'"back\\slash"') == "back\\slash"

def test_parse_value_empty_string():
    assert _parse_value("") == ""

def test_parse_value_leading_whitespace_stripped():
    assert _parse_value("  hello  ") == "hello"


# --- split_inc ---

def test_split_inc_plain_csv(tmp_path):
    f = tmp_path / "plain.csv"
    f.write_text("name,score\nAda,10\n", encoding="utf-8")
    lines, start = split_inc(str(f))
    assert lines == []
    assert start == 1

def test_split_inc_with_metadata(tmp_path):
    f = tmp_path / "data.inc"
    f.write_text("---\ntitle = Test\n---\nname,score\nAda,10\n", encoding="utf-8")
    lines, start = split_inc(str(f))
    assert lines == ["title = Test"]
    assert start == 4  # "name,score" is line 4

def test_split_inc_empty_metadata_block(tmp_path):
    f = tmp_path / "empty.inc"
    f.write_text("---\n---\nname,score\nAda,10\n", encoding="utf-8")
    lines, start = split_inc(str(f))
    assert lines == []
    assert start == 3

def test_split_inc_missing_closing_delimiter(tmp_path):
    f = tmp_path / "bad.inc"
    f.write_text("---\ntitle = Test\n", encoding="utf-8")
    with pytest.raises(ValueError, match="closing delimiter"):
        split_inc(str(f))

def test_split_inc_delimiter_comment_ignored(tmp_path):
    f = tmp_path / "data.inc"
    f.write_text("--- # start\ntitle = Test\n--- # end\nname,score\n", encoding="utf-8")
    lines, start = split_inc(str(f))
    assert lines == ["title = Test"]
    assert start == 4


# --- parse_metadata ---

def test_parse_metadata_global_keys():
    result = parse_metadata(["title = My Data", "version = 1"])
    assert result == {"title": "My Data", "version": 1}

def test_parse_metadata_section():
    result = parse_metadata(["[columns]", "time = seconds", "temp = Celsius"])
    assert result == {"columns": {"time": "seconds", "temp": "Celsius"}}

def test_parse_metadata_global_and_section():
    result = parse_metadata(["title = Test", "[columns]", "x = meters"])
    assert result == {"title": "Test", "columns": {"x": "meters"}}

def test_parse_metadata_int_value():
    result = parse_metadata(["version = 42"])
    assert result["version"] == 42
    assert isinstance(result["version"], int)

def test_parse_metadata_quoted_int_stays_string():
    result = parse_metadata(['id = "007"'])
    assert result["id"] == "007"
    assert isinstance(result["id"], str)

def test_parse_metadata_comments_stripped():
    result = parse_metadata(["# full line comment", "title = Test # inline"])
    assert result == {"title": "Test"}

def test_parse_metadata_blank_lines_ignored():
    result = parse_metadata(["", "title = Test", ""])
    assert result == {"title": "Test"}

def test_parse_metadata_whitespace_around_key_value():
    result = parse_metadata(["  title   =   My Data  "])
    assert result == {"title": "My Data"}

def test_parse_metadata_duplicate_global_key_raises():
    with pytest.raises(ValueError, match="duplicate key"):
        parse_metadata(["title = A", "title = B"])

def test_parse_metadata_duplicate_section_raises():
    with pytest.raises(ValueError, match="duplicate section"):
        parse_metadata(["[columns]", "x = 1", "[columns]", "y = 2"])

def test_parse_metadata_duplicate_key_in_section_raises():
    with pytest.raises(ValueError, match="duplicate key"):
        parse_metadata(["[columns]", "time = seconds", "time = minutes"])

def test_parse_metadata_invalid_key_characters_raises():
    with pytest.raises(ValueError, match="invalid characters"):
        parse_metadata(["bad key = value"])

def test_parse_metadata_invalid_section_name_raises():
    with pytest.raises(ValueError, match="invalid characters"):
        parse_metadata(["[bad section]", "x = 1"])

def test_parse_metadata_empty_section_raises():
    with pytest.raises(ValueError, match="empty"):
        parse_metadata(["[columns]", "[structure]", "delimiter = ,"])

def test_parse_metadata_empty_last_section_raises():
    with pytest.raises(ValueError, match="empty"):
        parse_metadata(["[columns]"])

def test_parse_metadata_error_includes_line_number():
    with pytest.raises(ValueError, match="2"):  # line 2
        parse_metadata(["title = A", "title = B"])
