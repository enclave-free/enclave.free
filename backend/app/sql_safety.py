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
    if re.match(r"^\s*WITH\b", sql, re.IGNORECASE):
        raise ValueError("CTEs are not supported in read-only admin SQL")
    if re.search(r"\b(?:FROM|JOIN)\s*\(", sql, re.IGNORECASE):
        raise ValueError("Nested subqueries are not supported in read-only admin SQL")

    tables = set()
    source_pattern = r"\b(FROM|JOIN)\s+(.+?)(?=\b(?:JOIN|WHERE|GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT|OFFSET|UNION|EXCEPT|INTERSECT|ON)\b|$)"
    for match in re.finditer(source_pattern, sql, re.IGNORECASE | re.DOTALL):
        for source in match.group(2).split(","):
            identifier = source.strip().split()[0] if source.strip() else ""
            identifier = identifier.strip('"`[]').split(".")[-1].strip('"`[]')
            if identifier:
                tables.add(identifier.lower())
    return tables


def validate_sql_allowed_tables(sql: str) -> tuple[bool, str]:
    """Return whether SELECT SQL references only allowlisted tables."""
    allowed = {table.lower() for table in ALLOWED_TABLES}
    try:
        referenced_tables = referenced_sql_tables(sql)
    except ValueError as exc:
        return False, str(exc)

    disallowed = sorted(table for table in referenced_tables if table not in allowed)
    if disallowed:
        return False, f"Query references disallowed table(s): {', '.join(disallowed)}"
    return True, ""
