"""Approved legacy-calibrated exponential; isolated from cloud and workbooks."""

import math

import pytest

from aily_project.services.fmi_dossier.excel import finalize, score_rows
from aily_project.services.fmi_dossier.policy import Policy, legacy_uplift, uplift

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "score,expected",
    [(0, 0), (60, 0), (70, 0.05272203334), (83, 0.09217044216), (100, 0.16746254628)],
)
def test_floor_exponential_benchmarks(score, expected):
    assert uplift(score, Policy()) == pytest.approx(expected, abs=1e-10)


def test_curve_accelerates_above_legacy_and_has_no_eleven_percent_cap():
    policy = Policy()
    rates = [uplift(score / 10, policy) for score in range(1001)]
    assert all(rate == 0 for rate in rates[:601])
    assert all(a < b for a, b in zip(rates[601:], rates[602:], strict=False))
    assert uplift(60.000001, policy) == pytest.approx(0.03, abs=1e-8)
    for score in range(61, 101):
        assert uplift(score, policy) > legacy_uplift(score, policy)
    assert uplift(98, policy) > 0.15
    assert uplift(100, policy) == pytest.approx(0.03 + 0.08 * math.expm1(1))


def test_custom_policy_and_initial_slope_match_calibration():
    policy = Policy(uplift_intercept=0.04, uplift_scale=0.10, uplift_exponent=0.5)
    assert uplift(0, policy) == 0
    assert uplift(83, policy) == pytest.approx(
        0.04 + 0.10 * math.expm1(0.5 * (83 - 60) / 40)
    )
    default = Policy()
    initial_slope = (
        default.uplift_scale * default.uplift_exponent / default.uplift_score_span
    )
    assert initial_slope == default.legacy_uplift_per_score
    flat = Policy(uplift_intercept=0.05, uplift_scale=0)
    assert uplift(70, flat) == uplift(100, flat) == 0.05


@pytest.mark.parametrize(
    "settings",
    [
        {"uplift_intercept": -0.01},
        {"uplift_threshold": 100},
        {"uplift_score_span": 0},
        {"uplift_exponent": 0},
    ],
)
def test_invalid_calibration_is_rejected(settings):
    with pytest.raises(ValueError):
        Policy(**settings)


@pytest.mark.parametrize("score", [-1, 101, float("nan"), float("inf")])
def test_scores_outside_calibrated_domain_are_rejected(score):
    with pytest.raises(ValueError, match="finite 0–100"):
        uplift(score, Policy())


def test_fendi_floor_does_not_change_scores_baseline_or_source_legacy():
    inputs = [
        {
            "brand_id": "fendi",
            "include": True,
            "score_method": "reported",
            "reported_fmi": 47,
            "ir_score": 60,
            "social_score": 50,
            "trend_score": 10,
            "source_document": "fendi.docx",
            "source_display_fmi": 81.6,
            "source_projected_forecast": 555.13953,
            "baseline_revenue": 517.275,
            "baseline_kind": "unadjusted_forecast",
            "baseline_approved": True,
            "baseline_source": "source.xlsx | N11",
            "baseline_subject": "Fendi",
            "baseline_scope": "brand-keyed forecast",
            "baseline_currency": "EUR",
            "baseline_unit_multiplier": 1000000,
            "forecast_target_label": "Calendar Q4 2026",
            "forecast_target_start": "2026-10-01",
            "forecast_target_end": "2026-12-31",
        },
        {
            "brand_id": "cohort-min",
            "include": True,
            "score_method": "reported",
            "reported_fmi": 6.41,
            "source_document": "min.docx",
        },
        {
            "brand_id": "cohort-max",
            "include": True,
            "score_method": "reported",
            "reported_fmi": 94,
            "source_document": "max.docx",
        },
        {
            "brand_id": "missing",
            "include": True,
            "score_method": "reported",
            "reported_fmi": None,
        },
    ]
    before_policy, policy = Policy(uplift_scale=0), Policy()
    before, before_cohort = finalize(score_rows(inputs, before_policy), before_policy)
    after, cohort = finalize(score_rows(inputs, policy), policy)
    assert cohort == before_cohort
    for key in (
        "raw_fmi",
        "display_fmi",
        "ir_score",
        "social_score",
        "trend_score",
        "baseline_revenue",
        "legacy_uplift_fraction",
        "legacy_adjusted_forecast",
        "source_legacy_uplift_fraction",
        "source_legacy_adjusted_forecast",
    ):
        assert after[0][key] == before[0][key]
    assert after[0]["display_fmi"] == 83
    assert after[0]["adjusted_forecast"] == pytest.approx(564.9524654647568)
    assert after[0]["source_legacy_uplift_fraction"] == pytest.approx(0.0732)
    assert after[0]["legacy_uplift_fraction"] == legacy_uplift(47, policy) == 0
    assert after[1]["uplift_fraction"] > 0.03
    assert after[1]["adjusted_forecast"] is None
    assert after[3]["uplift_fraction"] is None
