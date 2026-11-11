"""Schema version gating.

``schema_version`` is a ``"MAJOR.MINOR"`` string. Any minor within a supported
major is accepted; unknown majors and malformed versions are rejected.
"""

from __future__ import annotations

from typing import Any

from app.schemas.event import EventPayload

SUPPORTED_MAJOR_VERSIONS: frozenset[int] = frozenset({1})


class UnsupportedSchemaVersionError(ValueError):
    """Raised when ``schema_version`` is malformed or an unsupported major."""


def _parse_major(schema_version: str) -> int:
    """Extract the integer major from a ``MAJOR.MINOR`` version string."""
    major_part = schema_version.split(".", 1)[0].strip()
    try:
        return int(major_part)
    except ValueError as exc:
        raise UnsupportedSchemaVersionError(
            f"malformed schema_version {schema_version!r}; "
            "expected a 'MAJOR.MINOR' string such as '1.0'"
        ) from exc


def check_schema_version(schema_version: str) -> None:
    """Raise if ``schema_version`` is an unsupported major or malformed."""
    major = _parse_major(schema_version)
    if major not in SUPPORTED_MAJOR_VERSIONS:
        supported = ", ".join(str(v) for v in sorted(SUPPORTED_MAJOR_VERSIONS))
        raise UnsupportedSchemaVersionError(
            f"unsupported schema_version {schema_version!r}; "
            f"this backend supports major version(s): {supported}"
        )


def parse_event(raw: Any) -> EventPayload:
    """Gate the schema version, then validate and return the payload."""
    if not isinstance(raw, dict):
        raise UnsupportedSchemaVersionError(
            "event payload must be a JSON object with a 'schema_version' field"
        )
    schema_version = raw.get("schema_version")
    if not isinstance(schema_version, str):
        raise UnsupportedSchemaVersionError(
            "missing or non-string 'schema_version'; expected a 'MAJOR.MINOR' string such as '1.0'"
        )
    check_schema_version(schema_version)
    return EventPayload.model_validate(raw)
