# inccsv/_summary.py
from __future__ import annotations

from dataclasses import dataclass

from ._reader import IncFile


@dataclass
class IncSummary:
    path: str | None
    n_rows: int
    n_cols: int
    columns: list[str]
    n_metadata_keys: int
    sections: list[str]


def summarise(file: IncFile) -> IncSummary:
    """Generate a summary of an IncFile."""
    columns = list(file.rows[0].keys()) if file.rows else []
    n_metadata_keys = 0
    sections: list[str] = []

    for k, v in file.metadata.items():
        if isinstance(v, dict):
            sections.append(k)
            n_metadata_keys += len(v)
        else:
            n_metadata_keys += 1

    return IncSummary(
        path=file.path,
        n_rows=len(file.rows),
        n_cols=len(columns),
        columns=columns,
        n_metadata_keys=n_metadata_keys,
        sections=sections,
    )


def print_summary(file: IncFile) -> None:
    """Print a human-readable summary of an IncFile to stdout."""
    s = summarise(file)
    print(f"File:     {s.path or '(unknown)'}")
    print(f"Rows:     {s.n_rows}")
    print(f"Columns:  {s.n_cols}")
    if s.columns:
        print(f"  Names: {', '.join(s.columns)}")
    print(f"Metadata keys: {s.n_metadata_keys}")
    if s.sections:
        print(f"  Sections: {', '.join(s.sections)}")
