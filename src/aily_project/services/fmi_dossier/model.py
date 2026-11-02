"""Dossier-owned flat records and app dictionary, independent of automated FMI."""

import math
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

Row = dict[str, Any]


def truth(value: Any) -> bool:
    return str(value).lower() in {"true", "yes", "1"}


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    group: str
    type: str = "string"
    unit: str = "text"
    description: str = ""
    derivation: str = "Dossier input"
    required: bool = False
    influences_fmi: bool = False
    source_kind: str = "input_excel"
    source_reference: str = "FMI_dossier_inputs.xlsx / Inputs; match brand_id"
    source_fields: tuple[str, ...] = ()

    def record(self) -> Row:
        result = asdict(self)
        result["field_key"] = result.pop("key")
        result["excel_label"] = result.pop("label")
        result["description"] = self.description or self.label
        return result
