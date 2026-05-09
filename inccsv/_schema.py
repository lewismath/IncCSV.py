# inccsv/_schema.py
from __future__ import annotations

from dataclasses import dataclass, field

from ._parser import MetadataDict
from ._reader import IncFile, read_inc


@dataclass
class SchemaValidation:
    valid: bool
    missing: list[str]
    extra: list[str]


@dataclass
class IncSchema:
    must: dict[str, str]
    maybe: dict[str, str]
    allow_extra: bool = True
    description: dict[str, str] = field(default_factory=dict)


def read_schema(path: str) -> IncSchema:
    """Read a schema definition from an INC file."""
    inc = read_inc(path)
    meta = inc.metadata

    allow_extra = True
    schema_section = meta.get("schema", {})
    if isinstance(schema_section, dict):
        ae_raw = schema_section.get("allow_extra", "true")
        allow_extra = str(ae_raw).lower() not in ("false", "0", "no")

    must: dict[str, str] = {}
    must_section = meta.get("MUST", {})
    if isinstance(must_section, dict):
        must = {k: str(v) for k, v in must_section.items()}

    maybe: dict[str, str] = {}
    maybe_section = meta.get("MAYBE", {})
    if isinstance(maybe_section, dict):
        maybe = {k: str(v) for k, v in maybe_section.items()}

    description: dict[str, str] = {}
    desc_section = meta.get("description", {})
    if isinstance(desc_section, dict):
        description = {k: str(v) for k, v in desc_section.items()}

    return IncSchema(must=must, maybe=maybe, allow_extra=allow_extra, description=description)


def validate_schema(file: IncFile, schema: IncSchema) -> SchemaValidation:
    """
    Validate an IncFile's global metadata keys against a schema.

    Only top-level scalar keys (not section dicts) are compared to the schema.
    """
    file_keys: set[str] = {
        k for k, v in file.metadata.items() if not isinstance(v, dict)
    }
    schema_keys = set(schema.must) | set(schema.maybe)

    missing = [k for k in schema.must if k not in file_keys]
    extra = [k for k in sorted(file_keys) if k not in schema_keys]

    valid = not missing and (schema.allow_extra or not extra)

    return SchemaValidation(valid=valid, missing=missing, extra=extra)
