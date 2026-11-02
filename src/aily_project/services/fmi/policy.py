"""Validated business policy, resolved through the published ConfigRepository."""

from pathlib import Path
from typing import ClassVar, Self

from aily_py_commons.config import AilyConfigBaseModel, AilyService, ConfigRepository
from pydantic import ConfigDict, Field, model_validator


class Services(AilyService):
    FASHION_MOMENTUM = "fashion_momentum"


class Policy(AilyConfigBaseModel):
    config_id: ClassVar[str] = "fashion_momentum__score"
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: str = "fmi-controlled-v4"
    ir_weight: float = Field(default=0.5, ge=0, le=1)
    social_weight: float = Field(default=0.3, ge=0, le=1)
    trend_weight: float = Field(default=0.2, ge=0, le=1)
    ir_gap_multiplier: float = Field(default=5, gt=0)
    trend_change_boundary_pp: float = Field(default=2, ge=0)
    sustained_gap_pp: float = Field(default=5, ge=0)
    show_min_posts: int = Field(default=5, ge=1)
    annual_min_posts: int = Field(default=20, ge=1)
    annual_min_common_months: int = Field(default=3, ge=1, le=12)
    scenario_quarter_tolerance_days: int = Field(default=14, ge=0, le=14)
    scenario_forecast_tolerance_days: int = Field(default=62, ge=0, le=62)
    display_lower: float = Field(default=70, ge=0, le=100)
    display_upper: float = Field(default=98, ge=0, le=100)
    display_equal: float = Field(default=84, ge=0, le=100)
    uplift_max: float = Field(default=0.11, ge=0, le=1)
    uplift_exponent: float = Field(default=8, gt=0, le=50)
    legacy_uplift_threshold: float = Field(default=60, ge=0, le=100)
    legacy_uplift_intercept: float = Field(default=0.03, ge=0, le=1)
    legacy_uplift_per_score: float = Field(default=0.002, ge=0, le=0.01)

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if abs(self.ir_weight + self.social_weight + self.trend_weight - 1) > 1e-12:
            raise ValueError("Component weights must sum to one")
        if not self.display_lower <= self.display_equal <= self.display_upper:
            raise ValueError("Equal-cohort score must lie within display bounds")
        if not self.version.strip():
            raise ValueError("Policy version is required")
        return self


def resolve_policy(package_root: Path) -> Policy:
    """Call after AilySettings, once per task; never during module import."""
    repository = ConfigRepository(
        package_root=package_root,
        base_dir="services/fmi/config",
        service_enum=Services,
        strict=True,
    )
    errors = repository.validate_all()
    if any(errors.values()):
        raise ValueError(f"Invalid FMI configuration: {errors}")
    return repository.get(Policy)
