from __future__ import annotations

from csv import DictWriter
from io import StringIO
from typing import Any


def render_csv(rows: list[dict[str, Any]], *, columns: list[str]) -> str:
    buffer = StringIO()
    writer = DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        normalized = {}
        for column in columns:
            value = row.get(column)
            normalized[column] = "" if value is None else str(value)
        writer.writerow(normalized)
    return buffer.getvalue()
