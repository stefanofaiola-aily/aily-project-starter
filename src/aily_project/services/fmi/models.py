"""Shared typed records for scoring, Excel and the app handover."""

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

Value = str | int | float | bool | None
Row = dict[str, Any]


def truth(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "yes", "1"}


def number(value: Any) -> float | None:
    if value is None or isinstance(value, bool) or value == "":
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def instant(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    try:
        result = (
            value
            if isinstance(value, datetime)
            else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        )
        if result.tzinfo is None:
            return None  # Never guess a timestamp's timezone.
        return result.astimezone(UTC)
    except (ValueError, TypeError):
        return None


def calendar_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def show_cutoff(show: Any, zone: str) -> datetime:
    """End of day +37, including DST transitions in the local show timezone."""
    next_day = calendar_date(show) + timedelta(days=38)
    return datetime.combine(next_day, time.min, ZoneInfo(zone)) - timedelta(
        microseconds=1
    )


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (datetime, date)):
        formatted = value.isoformat()
        return None if formatted == "NaT" else formatted
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def fingerprint(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(clean(value), sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


@dataclass
class Inputs:
    entities: list[Row] = field(default_factory=list)
    peers: list[Row] = field(default_factory=list)
    analyses: list[Row] = field(default_factory=list)
    financial_review: list[Row] = field(default_factory=list)
    post_review: list[Row] = field(default_factory=list)


@dataclass
class Snapshot:
    financials: list[Row] = field(default_factory=list)
    posts: list[Row] = field(default_factory=list)
    profiles: list[Row] = field(default_factory=list)
    registry: list[Row] = field(default_factory=list)
    overrides: list[Row] = field(default_factory=list)
    metadata: Row = field(default_factory=dict)


@dataclass
class FMIResult:
    """Single canonical result consumed by Excel and app serialization."""

    brand_id: str
    analysis_id: str | None
    values: Row = field(default_factory=dict)
    gaps: list[str] = field(default_factory=list)
    peers: list[Row] = field(default_factory=list)
    financial_periods: list[Row] = field(default_factory=list)
    social_posts: list[Row] = field(default_factory=list)

    def record(self) -> Row:
        return {
            "brand_id": self.brand_id,
            "analysis_id": self.analysis_id,
            **self.values,
            "missing_reasons": "; ".join(dict.fromkeys(self.gaps)),
        }
