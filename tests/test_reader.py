# tests/test_reader.py
from __future__ import annotations
import pytest
from inccsv._reader import IncFile, read_inc


def write_file(tmp_path, name: str, content: str) -> str:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


# --- IncFile ---

def test_incfile_metadata_attribute():
    f = IncFile(metadata={"title": "T"}, rows=[{"a": "1"}], path=None)
    assert f.metadata == {"title": "T"}

def test_incfile_rows_attribute():
    f = IncFile(metadata={}, rows=[{"a": "1"}], path=None)
    assert f.rows == [{"a": "1"}]

def test_incfile_to_dataframe_requires_pandas():
    pytest.importorskip("pandas")
    f = IncFile(metadata={}, rows=[{"a": "1", "b": "2"}], path=None)
    df = f.to_dataframe()
    assert list(df.columns) == ["a", "b"]
    assert df.shape == (1, 2)


# --- read_inc plain CSV ---

def test_read_plain_csv(tmp_path):
    path = write_file(tmp_path, "data.csv", "name,score\nAda,10\nBabbage,12\n")
    result = read_inc(path)
    assert result.metadata == {}
    assert result.rows == [{"name": "Ada", "score": "10"}, {"name": "Babbage", "score": "12"}]

def test_read_plain_csv_stores_path(tmp_path):
    path = write_file(tmp_path, "data.csv", "name,score\nAda,10\n")
    result = read_inc(path)
    assert result.path == path


# --- read_inc with metadata ---

def test_read_inc_basic_metadata(tmp_path):
    content = "---\ntitle = My Data\nversion = 1\n---\nname,score\nAda,10\n"
    path = write_file(tmp_path, "data.inc", content)
    result = read_inc(path)
    assert result.metadata["title"] == "My Data"
    assert result.metadata["version"] == 1
    assert result.rows == [{"name": "Ada", "score": "10"}]

def test_read_inc_section_metadata(tmp_path):
    content = "---\n[columns]\ntime = seconds\n---\ntime,temp\n0,21.4\n"
    path = write_file(tmp_path, "data.inc", content)
    result = read_inc(path)
    assert result.metadata["columns"]["time"] == "seconds"


# --- structure section kwargs ---

def test_read_inc_semicolon_delimiter_from_structure(tmp_path):
    content = "---\n[structure]\ndelimiter = ;\n---\nname;score\nAda;10\n"
    path = write_file(tmp_path, "data.inc", content)
    result = read_inc(path)
    assert result.rows == [{"name": "Ada", "score": "10"}]

def test_read_inc_julia_delim_alias(tmp_path):
    # Julia writes `delim` not `delimiter` — we must accept both
    content = "---\n[structure]\ndelim = ;\n---\nname;score\nAda;10\n"
    path = write_file(tmp_path, "data.inc", content)
    result = read_inc(path)
    assert result.rows == [{"name": "Ada", "score": "10"}]

def test_read_inc_delimiter_takes_precedence_over_delim(tmp_path):
    # If both are present, `delimiter` wins
    content = "---\n[structure]\ndelim = ;\ndelimiter = |\n---\nname|score\nAda|10\n"
    path = write_file(tmp_path, "data.inc", content)
    result = read_inc(path)
    assert result.rows == [{"name": "Ada", "score": "10"}]

def test_read_inc_tab_alias(tmp_path):
    # Julia writes `delim = tab` for TSV — Python must translate to \t
    content = "---\n[structure]\ndelim = tab\n---\nname\tscore\nAda\t10\n"
    path = write_file(tmp_path, "data.inc", content)
    result = read_inc(path)
    assert result.rows == [{"name": "Ada", "score": "10"}]

def test_read_inc_space_alias(tmp_path):
    content = "---\n[structure]\ndelim = space\n---\nname score\nAda 10\n"
    path = write_file(tmp_path, "data.inc", content)
    result = read_inc(path)
    assert result.rows == [{"name": "Ada", "score": "10"}]

def test_read_inc_int_as_char(tmp_path):
    # Julia allows `delim = 44` meaning chr(44) = ','
    content = "---\n[structure]\ndelim = 44\n---\nname,score\nAda,10\n"
    path = write_file(tmp_path, "data.inc", content)
    result = read_inc(path)
    assert result.rows == [{"name": "Ada", "score": "10"}]

def test_read_inc_escapechar_from_structure(tmp_path):
    content = "---\n[structure]\nescapechar = |\n---\nname,score\nAda,10\n"
    path = write_file(tmp_path, "data.inc", content)
    result = read_inc(path)
    assert result.rows == [{"name": "Ada", "score": "10"}]

def test_read_inc_unknown_structure_key_raises(tmp_path):
    content = "---\n[structure]\ntypo_key = ;\n---\nname,score\nAda,10\n"
    path = write_file(tmp_path, "data.inc", content)
    with pytest.raises(ValueError, match="unknown key"):
        read_inc(path)

def test_read_inc_julia_only_structure_key_accepted(tmp_path):
    # Julia-only keys (e.g. missingstring) are silently accepted, not applied
    content = "---\n[structure]\nmissingstring = NA\n---\nname,score\nAda,10\n"
    path = write_file(tmp_path, "data.inc", content)
    result = read_inc(path)
    assert result.rows == [{"name": "Ada", "score": "10"}]

def test_read_inc_caller_kwargs_override_structure(tmp_path):
    content = "---\n[structure]\ndelimiter = ;\n---\nname|score\nAda|10\n"
    path = write_file(tmp_path, "data.inc", content)
    # caller says "|", overriding the ";" in [structure]
    result = read_inc(path, delimiter="|")
    assert result.rows == [{"name": "Ada", "score": "10"}]

def test_read_inc_comment_filter(tmp_path):
    content = "---\n[structure]\ncomment = #\n---\nname,score\n# this is a comment\nAda,10\n"
    path = write_file(tmp_path, "data.inc", content)
    result = read_inc(path)
    assert len(result.rows) == 1
    assert result.rows[0]["name"] == "Ada"

def test_read_inc_caller_comment_kwarg(tmp_path):
    content = "---\n---\nname,score\n# comment\nAda,10\n"
    path = write_file(tmp_path, "data.inc", content)
    result = read_inc(path, comment="#")
    assert len(result.rows) == 1


# --- unicode ---

def test_read_inc_unicode_metadata(tmp_path):
    content = "---\ntitle = Données\n---\nnom,valeur\nAlice,42\n"
    path = write_file(tmp_path, "unicode.inc", content)
    result = read_inc(path)
    assert result.metadata["title"] == "Données"
