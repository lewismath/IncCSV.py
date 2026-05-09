# tests/test_integration.py
from __future__ import annotations
import pytest
import inccsv


# --- Public API surface ---

def test_public_exports():
    assert hasattr(inccsv, 'read_inc')
    assert hasattr(inccsv, 'write_inc')
    assert hasattr(inccsv, 'read_schema')
    assert hasattr(inccsv, 'validate_schema')
    assert hasattr(inccsv, 'summarise')
    assert hasattr(inccsv, 'print_summary')
    assert hasattr(inccsv, 'IncFile')
    assert hasattr(inccsv, 'IncSchema')
    assert hasattr(inccsv, 'SchemaValidation')
    assert hasattr(inccsv, 'IncSummary')


# --- Full roundtrip ---

def test_full_roundtrip(tmp_path):
    original_rows = [
        {"time": "0.000", "customers": "1", "event": "Arrival"},
        {"time": "0.203", "customers": "2", "event": "Arrival"},
        {"time": "0.431", "customers": "1", "event": "Departure"},
    ]
    original_metadata = {
        "filename": "simulation_1.inc",
        "source": "simulation",
        "version": 1,
        "parameters": {"seed": 100, "lambda": 2},
        "columns": {"time": "seconds", "customers": "count", "event": "type"},
    }
    path = str(tmp_path / "sim.inc")
    inccsv.write_inc(path, original_rows, metadata=original_metadata)
    result = inccsv.read_inc(path)

    assert result.metadata["filename"] == "simulation_1.inc"
    assert result.metadata["source"] == "simulation"
    assert result.metadata["version"] == 1
    assert result.metadata["parameters"]["seed"] == 100
    assert result.metadata["columns"]["time"] == "seconds"
    assert result.rows == original_rows


# --- Schema validation roundtrip ---

def test_schema_validation_roundtrip(tmp_path):
    schema_content = (
        "---\n"
        "[schema]\n"
        "allow_extra = false\n"
        "[MUST]\n"
        "title = String\n"
        "version = Int\n"
        "[MAYBE]\n"
        "author = String\n"
        "---\n"
    )
    schema_path = str(tmp_path / "schema.inc")
    (tmp_path / "schema.inc").write_text(schema_content, encoding="utf-8")
    schema = inccsv.read_schema(schema_path)

    # Valid file
    f_valid = inccsv.IncFile(
        metadata={"title": "Test", "version": 1}, rows=[], path=None
    )
    result = inccsv.validate_schema(f_valid, schema)
    assert result.valid is True

    # Missing required field
    f_missing = inccsv.IncFile(metadata={"title": "Test"}, rows=[], path=None)
    result = inccsv.validate_schema(f_missing, schema)
    assert result.valid is False
    assert "version" in result.missing

    # Extra field rejected
    f_extra = inccsv.IncFile(
        metadata={"title": "Test", "version": 1, "extra": "x"}, rows=[], path=None
    )
    result = inccsv.validate_schema(f_extra, schema)
    assert result.valid is False
    assert "extra" in result.extra


# --- Summary integration ---

def test_summarise_via_public_api(tmp_path):
    path = str(tmp_path / "data.inc")
    (tmp_path / "data.inc").write_text(
        "---\ntitle = Test\n[columns]\ntime = seconds\n---\ntime,temp\n0,21\n1,22\n",
        encoding="utf-8",
    )
    f = inccsv.read_inc(path)
    s = inccsv.summarise(f)
    assert s.n_rows == 2
    assert s.n_cols == 2
    assert s.n_metadata_keys == 2  # 1 global + 1 in [columns]
    assert "columns" in s.sections


# --- pandas integration ---

def test_to_dataframe(tmp_path):
    pd = pytest.importorskip("pandas")
    path = str(tmp_path / "data.inc")
    (tmp_path / "data.inc").write_text(
        "---\ntitle = Test\n---\nname,score\nAda,10\nBabbage,12\n",
        encoding="utf-8",
    )
    f = inccsv.read_inc(path)
    df = f.to_dataframe()
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["name", "score"]
    assert len(df) == 2
    assert df.iloc[0]["name"] == "Ada"


# --- backward compat: plain CSV readable ---

def test_plain_csv_readable(tmp_path):
    path = str(tmp_path / "plain.csv")
    (tmp_path / "plain.csv").write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    f = inccsv.read_inc(path)
    assert f.metadata == {}
    assert len(f.rows) == 2


# --- unicode ---

def test_unicode_metadata_and_data_roundtrip(tmp_path):
    path = str(tmp_path / "unicode.inc")
    rows = [{"nom": "Élise", "valeur": "42"}]
    metadata = {"titre": "Données expérimentales", "auteur": "Müller"}
    inccsv.write_inc(path, rows, metadata=metadata)
    result = inccsv.read_inc(path)
    assert result.metadata["titre"] == "Données expérimentales"
    assert result.rows[0]["nom"] == "Élise"
