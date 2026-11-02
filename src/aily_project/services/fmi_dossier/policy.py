"""Independent dossier policy and mathematics, never imported by FMI automation."""

import math
from decimal import ROUND_HALF_UP, Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: str = "fmi-dossier-v1"
    ir_weight: float = Field(default=0.5, ge=0, le=1)
    social_weight: float = Field(default=0.3, ge=0, le=1)
    trend_weight: float = Field(default=0.2, ge=0, le=1)
    display_lower: float = Field(default=70, ge=0, le=100)
    display_upper: float = Field(default=98, ge=0, le=100)
    display_equal: float = Field(default=84, ge=0, le=100)
    uplift_max: float = Field(default=0.11, ge=0, le=1)
    uplift_exponent: float = Field(default=8, gt=0, le=50)
    legacy_uplift_threshold: float = Field(default=60, ge=0, le=100)
    legacy_uplift_intercept: float = Field(default=0.03, ge=0, le=1)
    legacy_uplift_per_score: float = Field(default=0.002, ge=0, le=0.01)

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        if abs(self.ir_weight + self.social_weight + self.trend_weight - 1) > 1e-12:
            raise ValueError("Dossier weights must sum to one")
        if not self.display_lower <= self.display_equal <= self.display_upper:
            raise ValueError("Equal-cohort score must lie within display bounds")
        if not self.version.strip():
            raise ValueError("Dossier policy version is required")
        return self


def half_up(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def classify(raw: float) -> str:
    return (
        "High"
        if raw >= 70
        else "Medium"
        if raw >= 60
        else "Neutral"
        if raw >= 40
        else "Low"
    )


def uplift(display: float, policy: Policy) -> float:
    return (
        policy.uplift_max
        * math.expm1(policy.uplift_exponent * display / 100)
        / math.expm1(policy.uplift_exponent)
    )


def legacy_uplift(raw: float, policy: Policy) -> float:
    return (
        0
        if raw <= policy.legacy_uplift_threshold
        else policy.legacy_uplift_intercept
        + (raw - policy.legacy_uplift_threshold) * policy.legacy_uplift_per_score
    )
