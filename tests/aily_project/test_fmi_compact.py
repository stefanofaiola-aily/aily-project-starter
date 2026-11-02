"""Compact settings, lossless review migration and no hidden input overrides."""

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from click.testing import CliRunner

from aily_project.cli import cli
from aily_project.services.fmi.compact_inputs import refresh_reviews, write_bundle
from aily_project.services.fmi.configuration import (
    document,
    input_policy,
    query_settings,
)
from aily_project.services.fmi.inputs import read_inputs
from aily_project.services.fmi.models import Inputs
from aily_project.services.fmi.policy import Policy

pytestmark = pytest.mark.unit


def verbose() -> dict:
    inputs = Inputs(
        entities=[
            {
                "entity_id": "brand",
                "name": "Brand",
                "prospect": True,
                "light_code": "LIGHT",
                "shared_symbol": "TICKER",
                "handle": "brand",
                "mapping_approved": True,
                "evidence": "identity",
            },
            {
                "entity_id": "peer",
                "name": "Peer",
                "prospect": False,
                "shared_symbol": "PRIVATE",
                "mapping_approved": True,
                "evidence": "private mapping",
            },
        ],
        analyses=[
            {
                "analysis_id": "brand-headline",
                "entity_id": "brand",
                "route": "show",
                "show_date": "2025-09-01",
                "timezone": "Europe/Paris",
                "selected": True,
                "headline": True,
                "reviewed": True,
                "financial_comparable": True,
                "evidence": "analysis",
            }
        ],
        peers=[
            {
                "analysis_id": "brand-headline",
                "peer_entity_id": "peer",
                "approved": True,
                "comparable": True,
                "evidence": "peer",
            }
        ],
        financial_review=[
            {
                "analysis_id": "brand-headline",
                "entity_id": "brand",
                "role": "latest",
                "metric": "revenue",
                "source_row_id": "source-id",
                "approved": True,
                "period_label": "FY2024",
                "evidence": "period",
            }
        ],
        post_review=[
            {
                "analysis_id": "brand-headline",
                "post_key": "p:1",
                "reviewed": True,
                "relevant": False,
                "evidence": "post",
            }
        ],
    )
    return document(inputs, Policy())


def bundle(tmp_path: Path):
    path = tmp_path / "FMI_inputs.json"
    write_bundle(verbose(), path)
    return path, json.loads(path.read_text())


def test_small_settings_derive_ids_and_windows_preserve_decisions(tmp_path):
    path, config = bundle(tmp_path)
    brand = config["brands"][0]
    assert brand["light_code"] == "LIGHT" and brand["shared_symbol"] == "TICKER"
    assert brand["peers"] == ["peer"]
    assert brand["financial_periods"] == {"latest": "FY2024"}
    assert "financial_selection" not in brand and "cutoff" not in brand["analysis"]
    assert "policy" not in config and "policy_file" in config
    loaded = read_inputs(path)
    assert loaded.entities[0]["mapping_approved"] is True
    assert loaded.peers[0]["approved"] is True
    assert loaded.analyses[0]["analysis_id"] == "brand-headline"
    assert loaded.analyses[0]["cutoff"] == "2025-10-08T23:59:59.999999+02:00"
    latest = next(
        r
        for r in loaded.financial_review
        if r["role"] == "latest" and r["entity_id"] == "brand"
    )
    assert latest["source_row_id"] == "source-id" and latest["approved"] is True
    assert loaded.post_review[0]["relevant"] is False
    assert query_settings(path)["row_limit"] == 500000


def inline_bundle(tmp_path):
    path, config = bundle(tmp_path)
    config.pop("review_file")
    config["brands"][0]["review"] = {
        "identity": {"mapping_approved": True, "evidence": "identity"},
        "analysis": {
            "reviewed": True,
            "financial_comparable": True,
            "evidence": "analysis",
        },
        "peers": {"peer": {"approved": True, "comparable": True, "evidence": "peer"}},
        "financial": {
            "brand": {
                "latest": {
                    "source_row_id": "source-id",
                    "approved": True,
                    "evidence": "period",
                }
            }
        },
        "posts": {"p:1": {"reviewed": True, "relevant": False, "evidence": "post"}},
    }
    config["peer_entities"][0]["review"] = {
        "identity": {"mapping_approved": True, "evidence": "private mapping"}
    }
    path.write_text(json.dumps(config))
    return path, config


def test_single_input_inline_decisions_no_companion_required(tmp_path):
    path, config = inline_bundle(tmp_path)
    # A broken old companion is irrelevant when it is not referenced.
    (tmp_path / "FMI_reviews.json").write_text("not json")
    loaded = read_inputs(path)
    assert loaded.entities[0]["mapping_approved"] is True
    assert loaded.analyses[0]["reviewed"] is True
    assert loaded.peers[0]["approved"] is True
    selected = next(r for r in loaded.financial_review if r.get("source_row_id"))
    assert selected["source_row_id"] == "source-id"
    assert selected["approved"] is True
    assert loaded.post_review[0]["relevant"] is False
    config["brands"][0].pop("review")
    path.write_text(json.dumps(config))
    unreviewed = read_inputs(path)
    assert unreviewed.analyses[0]["reviewed"] is False
    assert all(not r["approved"] for r in unreviewed.financial_review)


def test_shared_calendar_forecast_target_does_not_approve_sources(tmp_path):
    path, config = inline_bundle(tmp_path)
    config["brands"][0].pop("review")
    config["forecast"] = {
        "label": "Calendar Q4 2026",
        "start": "2026-10-01",
        "end": "2026-12-31",
    }
    path.write_text(json.dumps(config))
    loaded = read_inputs(path)
    assert loaded.analyses[0]["forecast_target_start"] == "2026-10-01"
    assert loaded.analyses[0]["forecast_target_end"] == "2026-12-31"
    assert not loaded.analyses[0]["reviewed"]
    assert all(not r["approved"] for r in loaded.financial_review)
    config["brands"][0]["forecast"] = {
        "label": "Calendar Q1 2027",
        "start": "2027-01-01",
        "end": "2027-03-31",
    }
    path.write_text(json.dumps(config))
    assert read_inputs(path).analyses[0]["forecast_target_end"] == "2027-03-31"
    config["forecast"]["amount"] = 123
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="unknown fields"):
        read_inputs(path)


def test_calendar_forecast_target_requires_complete_ordered_boundaries(tmp_path):
    path, config = inline_bundle(tmp_path)
    config["forecast"] = {"label": "Q4"}
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="requires label, start and end"):
        read_inputs(path)
    config["forecast"].update(start="2026-12-31", end="2026-10-01")
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="start must precede end"):
        read_inputs(path)


@pytest.mark.parametrize("forbidden", ["amount", "available_at", "vintage_verified"])
def test_inline_decisions_cannot_invent_measurements_or_vintages(tmp_path, forbidden):
    path, config = inline_bundle(tmp_path)
    config["brands"][0]["review"]["financial"]["brand"]["latest"][forbidden] = 123
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="unknown fields"):
        read_inputs(path)


def test_inline_reviews_reject_unassigned_peers_and_invalid_forecasts(tmp_path):
    path, config = inline_bundle(tmp_path)
    config["brands"][0]["review"]["peers"]["stranger"] = {"approved": True}
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="assigned"):
        read_inputs(path)
    del config["brands"][0]["review"]["peers"]["stranger"]
    config["brands"][0]["review"]["financial"]["peer"] = {
        "baseline": {"approved": True}
    }
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="not peers"):
        read_inputs(path)


def test_active_notebooks_use_single_input_and_local_data_snapshot():
    root = Path(__file__).parents[2] / "scripts/fashion-momentum-index/notebooks"
    for name in ("01_extract.ipynb", "02_score.ipynb", "03_delivery.ipynb"):
        notebook = json.loads((root / name).read_text())
        code = "\n".join(
            "".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code"
        )
        compile(code, name, "exec")
        assert 'str(FMI / "inputs/FMI_inputs.json")' in code
        assert 'str(FMI / "data")' in code
        assert 'EXTRACT / "snapshot.json"' not in code
        assert "FMI_reviews" not in code
        assert 'FMI / "handover"' not in code
        assert "prepare-inputs" not in code
        assert "subprocess" not in code and "FMI_WORK_DIR" not in code
        assert all(not c.get("outputs") for c in notebook["cells"])
    assert "work_dir=OUT" in code and "WRITE_DELIVERY" in code


def test_yaml_policy_changes_without_approving_inputs(tmp_path):
    path, config = bundle(tmp_path)
    policy_path = path.parent / config["policy_file"]
    policy = yaml.safe_load(policy_path.read_text())
    policy["uplift_exponent"] = 4
    policy_path.write_text(yaml.safe_dump(policy))
    assert input_policy(path, Policy()).uplift_exponent == 4
    assert read_inputs(path).analyses[0]["reviewed"] is True
    policy["uplift_exponent"] = -1
    policy_path.write_text(yaml.safe_dump(policy))
    with pytest.raises(ValueError):
        input_policy(path, Policy())


@pytest.mark.parametrize(
    "change", ["show_date", "peer_identity", "forecast", "financial_period"]
)
def test_configuration_changes_never_reuse_stale_approvals(tmp_path, change):
    path, config = bundle(tmp_path)
    review_path = path.parent / config["review_file"]
    previous = review_path.read_bytes()
    if change == "show_date":
        config["brands"][0]["analysis"]["show_date"] = "2025-09-02"
    elif change == "peer_identity":
        config["peer_entities"][0]["shared_symbol"] = "NEW"
    elif change == "forecast":
        config["brands"][0]["forecast"] = {"label": "Q1"}
    else:
        config["brands"][0]["financial_periods"]["latest"] = "FY2025"
    path.write_text(json.dumps(config))
    changed = read_inputs(path)
    assert changed.analyses[0]["reviewed"] is False
    assert all(not r["approved"] for r in changed.financial_review)
    assert changed.post_review == []
    assert review_path.read_bytes() == previous
    new_review = tmp_path / "next-reviews.json"
    assert refresh_reviews(path, config, new_review) == ["brand-headline"]
    refreshed = json.loads(new_review.read_text())
    assert refreshed["financial_selection"][0]["source_row_id"] == "source-id"
    assert refreshed["financial_selection"][0]["approved"] is False
    assert refreshed["post_review"][0]["relevant"] is False


def test_event_only_changes_do_not_invalidate_measurement_reviews(tmp_path):
    path, config = bundle(tmp_path)
    config["brands"][0].update(required=True, category="Luxe")
    path.write_text(json.dumps(config))
    assert read_inputs(path).analyses[0]["reviewed"] is True


@pytest.mark.parametrize("section", ["brand", "review"])
def test_measurements_cannot_be_inserted_in_either_file(tmp_path, section):
    path, config = bundle(tmp_path)
    if section == "brand":
        config["brands"][0]["revenue"] = 999
        path.write_text(json.dumps(config))
    else:
        target = path.parent / config["review_file"]
        review = json.loads(target.read_text())
        review["financial_selection"][0]["amount"] = 999
        target.write_text(json.dumps(review))
    with pytest.raises(ValueError, match="unknown fields"):
        read_inputs(path)


def test_duplicate_review_rows_fail_instead_of_last_row_winning(tmp_path):
    path, config = bundle(tmp_path)
    target = path.parent / config["review_file"]
    review = json.loads(target.read_text())
    review["financial_selection"].append(deepcopy(review["financial_selection"][0]))
    target.write_text(json.dumps(review))
    with pytest.raises(ValueError, match="duplicate review key"):
        read_inputs(path)


def test_missing_reference_and_unsupported_show_overrides_fail(tmp_path):
    path, config = bundle(tmp_path)
    config["brands"][0]["analysis"]["cutoff"] = "2026-01-01T00:00:00Z"
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="derived"):
        read_inputs(path)
    config["brands"][0]["analysis"].pop("cutoff")
    config["review_file"] = "missing.json"
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="Missing input companion"):
        read_inputs(path)


def test_bundle_never_overwrites_inputs_or_review_decisions(tmp_path):
    path, _ = bundle(tmp_path)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        write_bundle(verbose(), path)
    assert path.read_bytes() == before


def test_one_time_migration_is_offline(tmp_path):
    source = tmp_path / "verbose.json"
    source.write_text(json.dumps(verbose()))
    with patch("aily_project.services.fmi.runner.initialize") as cloud:
        result = CliRunner().invoke(
            cli,
            [
                "fmi",
                "simplify-inputs",
                "--inputs",
                str(source),
                "--output",
                str(tmp_path / "FMI_inputs.json"),
            ],
        )
    assert result.exit_code == 0, result.output
    cloud.assert_not_called()


def test_no_reviews_means_unreviewed_not_automatically_approved(tmp_path):
    path = tmp_path / "inputs.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "fmi-input-v2",
                "brands": [{"id": "a", "name": "A", "peers": ["p"]}],
                "peer_entities": [{"id": "p", "name": "P"}],
            }
        )
    )
    loaded = read_inputs(path)
    assert loaded.entities[0]["mapping_approved"] is False
    assert loaded.analyses[0]["reviewed"] is False
    assert loaded.peers[0]["approved"] is False
