"""The frozen historical reference is complete and requires no sibling repo."""

import hashlib
import json
import runpy
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "scripts/fmi-dossier/reference/aily-superagent-roadmap"
RESEARCH = SNAPSHOT / "docs/research/wwd-fashion-momentum"


def test_reference_assets_match_manifest_and_are_local():
    manifest = json.loads((SNAPSHOT / "manifest.json").read_text())
    assert manifest["source_repository"] == "aily-superagent-roadmap"
    paths = [entry["path"] for entry in manifest["files"]]
    assert len(paths) == len(set(paths)) == 75
    assert "docs/research/wwd-fashion-momentum/weighted-delivery.xlsx" in paths
    assert ".agents/skills/update-fashion-momentum/SKILL.md" in paths
    assert ".github/workflows/fashion-momentum-sync.yml" in paths
    for entry in manifest["files"]:
        path = SNAPSHOT / entry["path"]
        assert path.resolve().is_relative_to(SNAPSHOT.resolve())
        assert path.is_file() and not path.is_symlink()
        assert path.stat().st_size == entry["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
    assert len(list((RESEARCH / "prompts").glob("*.md"))) == 25


def test_historical_comparison_defaults_to_local_snapshot(tmp_path, monkeypatch):
    script = ROOT / "scripts/fmi-dossier/check_weighted_reference.py"
    module = runpy.run_path(str(script))
    assert module["REFERENCE_ROOT"] == RESEARCH
    destination = tmp_path / "reference.json"
    monkeypatch.setattr("sys.argv", [str(script), "--output", str(destination)])
    module["main"]()
    result = json.loads(destination.read_text())
    assert len(result["brands"]) == len(result["delivery_snapshots"]) == 74
    assert result["verified_cells"] == 2812
    assert result["workbook_roadmap_differences"] == []
    assert Path(result["source"]) == RESEARCH / "weighted-delivery.xlsx"
    assert Path(result["roadmap_source"]) == RESEARCH / "weighted-delivery.json"
    assert result["brands"]["fendi"]["raw_fmi"] is not None
    assert result["delivery_snapshots"]["fendi"]["values"][
        "source_q4_sales_yoy_2026"
    ] == pytest.approx(-0.01308528)
