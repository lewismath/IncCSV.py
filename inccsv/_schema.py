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


# Section name aliases match Julia's getsection() — case-insensitive on both sides.
_MUST_ALIASES    = frozenset({"must", "required"})
_MAYBE_ALIASES   = frozenset({"maybe", "optional"})
_SCHEMA_ALIASES  = frozenset({"schema", "options"})
_DESC_ALIASES    = frozenset({"description", "descriptions", "describe"})

# Values that mean False for allow_extra — matches Julia's parse_schema_bool.
_FALSY_ALLOW_EXTRA = frozenset({"false", "0", "no", "deny", "closed"})


def _get_section(meta: MetadataDict, aliases: frozenset[str]) -> dict:
    """Return the first section whose lowercased name is in aliases, or {}."""
    for key, value in meta.items():
        if key.lower() in aliases and isinstance(value, dict):
            return value
    return {}


def read_schema(path: str) -> IncSchema:
    """Read a schema definition from an INC file."""
    inc = read_inc(path)
    meta = inc.metadata

    schema_section = _get_section(meta, _SCHEMA_ALIASES)
    ae_raw = schema_section.get("allow_extra", "true")
    allow_extra = str(ae_raw).lower() not in _FALSY_ALLOW_EXTRA

    must        = {k: str(v) for k, v in _get_section(meta, _MUST_ALIASES).items()}
    maybe       = {k: str(v) for k, v in _get_section(meta, _MAYBE_ALIASES).items()}
    description = {k: str(v) for k, v in _get_section(meta, _DESC_ALIASES).items()}

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
