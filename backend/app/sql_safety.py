"""Shared SQL validation helpers for admin read-only paths."""

from __future__ import annotations

import re


# Tables that can be queried by admin read-only database helpers.
ALLOWED_TABLES = {
    "admins",
    "instance_settings",
    "user_types",
    "user_field_definitions",
    "users",
    "user_field_values",
}


def referenced_sql_tables(sql: str) -> set[str]:
    """Extract simple FROM/JOIN table identifiers for allowlist checks."""
    tables = set()
    pattern = r'\b(?:FROM|JOIN)\s+(?:"([^"]+)"|`([^`]+)`|\[([^\]]+)\]|([A-Za-z_][A-Za-z0-9_\.]*))'
    for match in re.finditer(pattern, sql, re.IGNORECASE):
        identifier = next(group for group in match.groups() if group)
        identifier = identifier.split(".")[-1]
        if identifier:
            tables.add(identifier.lower())
    return tables


def validate_sql_allowed_tables(sql: str) -> tuple[bool, str]:
    """Return whether SELECT SQL references only allowlisted tables."""
    allowed = {table.lower() for table in ALLOWED_TABLES}
    disallowed = sorted(table for table in referenced_sql_tables(sql) if table not in allowed)
    if disallowed:
        return False, f"Query references disallowed table(s): {', '.join(disallowed)}"
    return True, ""
