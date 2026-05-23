# tests/test_fixtures.py
from __future__ import annotations

import pytest
from pathlib import Path

from inccsv._reader import read_inc
from inccsv._schema import read_schema, validate_schema
from inccsv._writer import write_inc

FIXTURES = Path(__file__).parent / "fixtures"


# --- Positive: files that must parse without error ---

@pytest.mark.parametrize("filename", [
    "basic.inc",
    "escapechar_structure.inc",
    "header_footerskip_structure.inc",
    "metadata_edge_cases.inc",
    "plain.csv",
    "quotechar_structure.inc",
    "semicolon_structure.inc",
    "tab_structure.inc",
    "unicode.inc",
])
def test_positive_fixture_parses(filename):
    read_inc(str(FIXTURES / "positive" / filename))


def test_positive_schema_fixture_reads():
    read_schema(str(FIXTURES / "positive" / "schema.inc"))


def test_positive_schema_target_validates():
    schema = read_schema(str(FIXTURES / "positive" / "schema.inc"))
    target = read_inc(str(FIXTURES / "positive" / "schema_target_valid.inc"))
    result = validate_schema(target, schema)
    assert result.valid is True


# --- Negative: files that must raise ValueError ---

@pytest.mark.parametrize("filename", [
    "empty_section.inc",
    "invalid_key.inc",
    "invalid_section_key.inc",
    "invalid_structure_char.inc",
    "invalid_structure_int.inc",
    "missing_closing_delimiter.inc",
    "repeated_key.inc",
    "unsupported_structure_key.inc",
])
def test_negative_fixture_raises(filename):
    with pytest.raises(ValueError):
        read_inc(str(FIXTURES / "negative" / filename))


@pytest.mark.parametrize("filename", [
    "schema_deep_path.inc",
    "schema_duplicate_requirement.inc",
])
def test_negative_schema_fixture_raises(filename):
    with pytest.raises(ValueError):
        read_schema(str(FIXTURES / "negative" / filename))


# --- Roundtrip: read then write must reproduce expected output ---

def test_roundtrip_basic(tmp_path):
    fixture = FIXTURES / "roundtrip" / "basic_expected.inc"
    inc = read_inc(str(fixture))
    out = tmp_path / "out.inc"
    write_inc(str(out), inc.rows, metadata=inc.metadata)
    assert out.read_text() == fixture.read_text()


def test_roundtrip_escaped(tmp_path):
    fixture = FIXTURES / "roundtrip" / "escaped_expected.inc"
    inc = read_inc(str(fixture))
    out = tmp_path / "out.inc"
    write_inc(str(out), inc.rows, metadata=inc.metadata)
    assert out.read_text() == fixture.read_text()
