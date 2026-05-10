# tests/test_schema.py
from __future__ import annotations
import pytest
from inccsv._schema import IncSchema, SchemaValidation, read_schema, validate_schema
from inccsv._reader import IncFile


def make_schema_file(tmp_path, content: str) -> str:
    p = tmp_path / "schema.inc"
    p.write_text(content, encoding="utf-8")
    return str(p)


# --- IncSchema ---

def test_incschema_defaults():
    s = IncSchema(must={}, maybe={})
    assert s.allow_extra is True
    assert s.description == {}


# --- read_schema ---

def test_read_schema_must_fields(tmp_path):
    content = "---\n[MUST]\ntitle = String\nversion = Int\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.must == {"title": "String", "version": "Int"}

def test_read_schema_maybe_fields(tmp_path):
    content = "---\n[MAYBE]\nauthor = String\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.maybe == {"author": "String"}

def test_read_schema_allow_extra_false(tmp_path):
    content = "---\n[schema]\nallow_extra = false\n[MUST]\ntitle = String\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.allow_extra is False

def test_read_schema_allow_extra_true_by_default(tmp_path):
    content = "---\n[MUST]\ntitle = String\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.allow_extra is True

def test_read_schema_description(tmp_path):
    content = "---\n[MUST]\ntitle = String\n[description]\ntitle = The dataset title\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.description == {"title": "The dataset title"}

def test_read_schema_empty_schema_file(tmp_path):
    content = "---\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.must == {}
    assert schema.maybe == {}
    assert schema.allow_extra is True

def test_read_schema_lowercase_section_names(tmp_path):
    # Julia accepts [must] and [maybe] (lowercase)
    content = "---\n[must]\ntitle = String\n[maybe]\nauthor = String\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.must == {"title": "String"}
    assert schema.maybe == {"author": "String"}

def test_read_schema_required_alias(tmp_path):
    content = "---\n[required]\ntitle = String\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.must == {"title": "String"}

def test_read_schema_optional_alias(tmp_path):
    content = "---\n[optional]\nauthor = String\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.maybe == {"author": "String"}

def test_read_schema_options_alias_for_schema(tmp_path):
    content = "---\n[options]\nallow_extra = false\n[MUST]\ntitle = String\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.allow_extra is False

def test_read_schema_allow_extra_deny(tmp_path):
    content = "---\n[schema]\nallow_extra = deny\n[MUST]\ntitle = String\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.allow_extra is False

def test_read_schema_allow_extra_closed(tmp_path):
    content = "---\n[schema]\nallow_extra = closed\n[MUST]\ntitle = String\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.allow_extra is False

def test_read_schema_allow_extra_no(tmp_path):
    content = "---\n[schema]\nallow_extra = no\n[MUST]\ntitle = String\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.allow_extra is False

def test_read_schema_descriptions_alias(tmp_path):
    content = "---\n[MUST]\ntitle = String\n[descriptions]\ntitle = The dataset title\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.description == {"title": "The dataset title"}


# --- validate_schema ---

def make_file(metadata: dict) -> IncFile:
    return IncFile(metadata=metadata, rows=[], path=None)

def test_validate_all_must_present():
    schema = IncSchema(must={"title": "String", "version": "Int"}, maybe={})
    f = make_file({"title": "Test", "version": 1})
    result = validate_schema(f, schema)
    assert result.valid is True
    assert result.missing == []
    assert result.extra == []

def test_validate_missing_required_field():
    schema = IncSchema(must={"title": "String", "version": "Int"}, maybe={})
    f = make_file({"title": "Test"})
    result = validate_schema(f, schema)
    assert result.valid is False
    assert "version" in result.missing

def test_validate_extra_field_allowed_by_default():
    schema = IncSchema(must={"title": "String"}, maybe={})
    f = make_file({"title": "Test", "extra_key": "value"})
    result = validate_schema(f, schema)
    assert result.valid is True
    assert "extra_key" in result.extra

def test_validate_extra_field_rejected_when_not_allowed():
    schema = IncSchema(must={"title": "String"}, maybe={}, allow_extra=False)
    f = make_file({"title": "Test", "extra_key": "value"})
    result = validate_schema(f, schema)
    assert result.valid is False
    assert "extra_key" in result.extra

def test_validate_maybe_field_not_required():
    schema = IncSchema(must={"title": "String"}, maybe={"author": "String"})
    f = make_file({"title": "Test"})  # author missing but it's MAYBE
    result = validate_schema(f, schema)
    assert result.valid is True
    assert result.missing == []

def test_validate_maybe_field_not_counted_as_extra():
    schema = IncSchema(must={}, maybe={"author": "String"})
    f = make_file({"author": "Ada"})
    result = validate_schema(f, schema)
    assert result.valid is True
    assert result.extra == []

def test_validate_empty_file_against_must_schema():
    schema = IncSchema(must={"title": "String"}, maybe={})
    f = make_file({})
    result = validate_schema(f, schema)
    assert result.valid is False
    assert "title" in result.missing

def test_validate_schema_ignores_section_keys():
    """Section contents are not checked against the schema — only global keys."""
    schema = IncSchema(must={"title": "String"}, maybe={}, allow_extra=False)
    f = make_file({"title": "Test", "columns": {"time": "seconds"}})
    result = validate_schema(f, schema)
    # "columns" section should not be counted as an "extra" global key
    assert result.valid is True
