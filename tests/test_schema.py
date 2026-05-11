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
    assert s.must_not == {}


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

def test_validate_section_names_not_counted_as_extra():
    """Section names are never extra; only undeclared dotted children are."""
    schema = IncSchema(must={"title": "String"}, maybe={}, allow_extra=False)
    f = make_file({"title": "Test", "columns": {"time": "seconds"}})
    result = validate_schema(f, schema)
    assert "columns" not in result.extra
    assert "columns.time" in result.extra
    assert result.valid is False


# --- must_not field ---

def test_incschema_must_not_default():
    s = IncSchema(must={}, maybe={})
    assert s.must_not == {}

def test_schema_validation_forbidden_field_default():
    schema = IncSchema(must={"title": "String"}, maybe={})
    f = make_file({"title": "Test"})
    result = validate_schema(f, schema)
    assert result.forbidden == []

def test_read_schema_must_not_section(tmp_path):
    content = "---\n[MUST_NOT]\ninternal_id = String\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.must_not == {"internal_id": "String"}

def test_read_schema_shall_not_alias(tmp_path):
    content = "---\n[SHALL_NOT]\nfoo = String\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.must_not == {"foo": "String"}

def test_read_schema_shall_alias(tmp_path):
    content = "---\n[SHALL]\ntitle = String\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.must == {"title": "String"}

def test_read_schema_may_alias(tmp_path):
    content = "---\n[MAY]\nauthor = String\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.maybe == {"author": "String"}

# --- section.child path validation ---

def test_validate_section_child_in_must_passes():
    schema = IncSchema(must={"title": "String", "columns.score": "String"}, maybe={})
    f = make_file({"title": "Test", "columns": {"score": "Float"}})
    result = validate_schema(f, schema)
    assert result.valid is True
    assert result.missing == []

def test_validate_missing_section_child_path():
    schema = IncSchema(must={"columns.score": "String"}, maybe={})
    f = make_file({"title": "Test"})
    result = validate_schema(f, schema)
    assert result.valid is False
    assert "columns.score" in result.missing

def test_validate_section_child_extra_when_allow_extra_false():
    schema = IncSchema(must={"title": "String"}, maybe={}, allow_extra=False)
    f = make_file({"title": "Test", "columns": {"score": "Float"}})
    result = validate_schema(f, schema)
    assert result.valid is False
    assert "columns.score" in result.extra

def test_validate_section_child_not_extra_when_declared():
    schema = IncSchema(
        must={"title": "String", "columns.score": "String"}, maybe={}, allow_extra=False
    )
    f = make_file({"title": "Test", "columns": {"score": "Float"}})
    result = validate_schema(f, schema)
    assert result.valid is True
    assert result.extra == []

def test_validate_section_child_in_maybe_not_extra():
    schema = IncSchema(must={}, maybe={"columns.score": "String"})
    f = make_file({"columns": {"score": "Float"}})
    result = validate_schema(f, schema)
    assert result.valid is True
    assert result.extra == []

# --- MUST_NOT validation ---

def test_validate_must_not_field_present_is_invalid():
    schema = IncSchema(must={}, maybe={}, must_not={"internal_id": "String"})
    f = make_file({"internal_id": "secret"})
    result = validate_schema(f, schema)
    assert result.valid is False
    assert "internal_id" in result.forbidden

def test_validate_must_not_field_absent_is_valid():
    schema = IncSchema(must={"title": "String"}, maybe={}, must_not={"internal_id": "String"})
    f = make_file({"title": "Test"})
    result = validate_schema(f, schema)
    assert result.valid is True
    assert result.forbidden == []

def test_validate_must_not_section_child():
    schema = IncSchema(must={}, maybe={}, must_not={"private.key": "String"})
    f = make_file({"private": {"key": "secret"}})
    result = validate_schema(f, schema)
    assert result.valid is False
    assert "private.key" in result.forbidden

# --- read_schema input guards ---

def test_read_schema_deep_path_raises(tmp_path):
    content = "---\n[MUST]\na.b.c = String\n---\n"
    path = make_schema_file(tmp_path, content)
    with pytest.raises(ValueError, match="more than one level"):
        read_schema(path)

def test_read_schema_duplicate_must_maybe_raises(tmp_path):
    content = "---\n[MUST]\ntitle = String\n[MAYBE]\ntitle = String\n---\n"
    path = make_schema_file(tmp_path, content)
    with pytest.raises(ValueError, match="declared in both"):
        read_schema(path)

def test_read_schema_duplicate_must_must_not_raises(tmp_path):
    content = "---\n[MUST]\ntitle = String\n[MUST_NOT]\ntitle = String\n---\n"
    path = make_schema_file(tmp_path, content)
    with pytest.raises(ValueError, match="declared in both"):
        read_schema(path)

def test_read_schema_single_dot_path_valid(tmp_path):
    content = "---\n[MUST]\ncolumns.score = String\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.must == {"columns.score": "String"}

def test_read_schema_top_level_path_valid(tmp_path):
    content = "---\n[MUST]\ntitle = String\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.must == {"title": "String"}
