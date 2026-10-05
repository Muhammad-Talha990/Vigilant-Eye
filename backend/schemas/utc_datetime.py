"""Pydantic UTC datetime type — JSON serialization always includes Z."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import PlainSerializer

from time_utils import to_api_iso


def _serialize_utc_datetime(value: datetime) -> str:
    out = to_api_iso(value)
    assert out is not None
    return out


UtcDateTime = Annotated[
    datetime,
    PlainSerializer(_serialize_utc_datetime, return_type=str, when_used="always"),
]
