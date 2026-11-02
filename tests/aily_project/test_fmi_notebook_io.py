"""Notebook source reads and committed notebook hygiene; no live databases."""

import json
import runpy
from pathlib import Path

import pandas as pd
import pytest

from aily_project.services.fmi.extraction import SPECS

pytestmark = pytest.mark.unit
FMI = Path(__file__).resolve().parents[2] / "scripts/fashion-momentum-index"
HELPERS = runpy.run_path(str(FMI / "helpers.py"))


class Reader:
    def __init__(self, rows, read_only=True):
        self.rows, self.read_only, self.calls = rows, read_only, []

    def fetch_data_as_df(self, query, *, bind_params=()):
        self.calls.append((query, bind_params))
        if "current_setting" in query:
            return pd.DataFrame(
                [
                    {
                        "transaction_read_only": "on" if self.read_only else "off",
                        "default_transaction_read_only": "on",
                    }
                ]
            )
        return pd.DataFrame(self.rows)


def test_source_read_saves_exact_rows_and_sql_after_read_only_check(tmp_path):
    client = Reader([{"company_code": "B", "year": 2025, "type_filter_value": 100}])
    relation = "light.light_financial_statements_actuals"
    metadata = {
        "extracted_at": "2026-11-02T00:00:00Z",
        "queries": [],
        "limitations": [],
    }
    rows = HELPERS["read_source"](
        client,
        {relation: set(SPECS[relation])},
        relation,
        "company_code = %s AND year BETWEEN %s AND %s",
        ("B", 2023, 2025),
        {"company_code"},
        tmp_path / "sources",
        metadata,
        10,
    )
    assert client.calls[0][0].startswith("SELECT current_setting")
    assert client.calls[1][1] == ("B", 2023, 2025, 11)
    assert rows[0]["source_row_id"] and rows[0]["source_relation"] == relation
    assert "scope" not in rows[0] and "unit_multiplier" not in rows[0]
    assert (tmp_path / "sources/light__light_financial_statements_actuals.csv").exists()
    assert HELPERS["load_table"](tmp_path / "queries")[0]["row_count"] == 1
    assert not list(tmp_path.rglob("*.json"))


@pytest.mark.parametrize("writable,overflow", [(True, False), (False, True)])
def test_source_read_refuses_writable_sessions_and_overflow(
    tmp_path, writable, overflow
):
    client = Reader(
        [{"company_code": "B"}] * (11 if overflow else 1), read_only=not writable
    )
    relation = "light.light_financial_statements_actuals"
    metadata = {"extracted_at": "stamp", "queries": [], "limitations": []}
    with pytest.raises(ValueError, match="read-only|row limit"):
        HELPERS["read_source"](
            client,
            {relation: set(SPECS[relation])},
            relation,
            "company_code = %s",
            ("B",),
            {"company_code"},
            tmp_path / "sources",
            metadata,
            10,
        )
    assert not (tmp_path / "sources").exists()


def test_csv_escapes_formulas_and_restores_types_for_calculation(tmp_path):
    HELPERS["save_table"](
        [
            {
                "caption": "=HYPERLINK(1)",
                "amount": -2,
                "post_id": "00123",
                "vintage_verified": False,
                "scope": None,
                "source_candidates": [{"amount": 2}],
            }
        ],
        tmp_path / "posts",
    )
    row = HELPERS["load_table"](tmp_path / "posts")[0]
    assert row["caption"] == "=HYPERLINK(1)"
    assert row["post_id"] == "00123" and row["vintage_verified"] is False
    assert row["scope"] is None and row["source_candidates"] == [{"amount": 2}]
    assert not (tmp_path / "posts.json").exists()
    csv = pd.read_csv(tmp_path / "posts.csv")
    assert csv.iloc[0]["caption"].startswith("'=")
    assert csv.iloc[0]["amount"] == -2


def test_failed_extraction_does_not_replace_complete_handoff(tmp_path):
    data = tmp_path / "data"
    complete = data / "extract"
    HELPERS["save_table"]([{"amount": 42}], complete / "financials")
    staged = HELPERS["begin_extract"](data)
    HELPERS["save_table"]([{"amount": 99}], staged / "financials")
    with pytest.raises(ValueError, match="incomplete"):
        HELPERS["publish_extract"](staged, complete)
    assert HELPERS["load_table"](complete / "financials")[0]["amount"] == 42
    for name in ("posts", "profiles", "registry", "overrides"):
        HELPERS["save_table"]([], staged / name)
    HELPERS["save_table"]([{"authenticated": False}], staged / "metadata")
    with pytest.raises(ValueError, match="unauthenticated"):
        HELPERS["publish_extract"](staged, complete)
    HELPERS["save_table"]([{"authenticated": True}], staged / "metadata")
    HELPERS["publish_extract"](staged, complete)
    assert HELPERS["load_table"](complete / "financials")[0]["amount"] == 99
    prior = staged.with_name("previous-" + staged.name)
    assert HELPERS["load_table"](prior / "financials")[0]["amount"] == 42
    assert not staged.exists()


def test_notebooks_are_source_only_and_save_csv_intermediates():
    for path in list((FMI / "notebooks").glob("*.ipynb")) + list(
        (FMI.parent / "fmi-dossier/notebooks").glob("*.ipynb")
    ):
        notebook = json.loads(path.read_text())
        code = "\n".join(
            "".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code"
        )
        compile(code, str(path), "exec")
        assert "subprocess" not in code and "aily_project.cli" not in code
        assert "FMI_WORK_DIR" not in code
        assert "snapshot.json" not in code and "raw-score.json" not in code
        assert "input_hash" not in code and "snapshot_hash" not in code
        assert 'FMI / "handover"' not in code and "dossier_records" not in code
        assert len([c for c in notebook["cells"] if c["cell_type"] == "code"]) >= 7
        for cell in notebook["cells"]:
            if cell["cell_type"] == "code":
                assert cell["execution_count"] is None and cell["outputs"] == []


def test_issuer_query_includes_quarterly_press_release_document_type():
    notebook = json.loads((FMI / "notebooks/01_extract.ipynb").read_text())
    cell = next(c for c in notebook["cells"] if c["id"] == "01-18")
    code = "".join(cell["source"])
    # Shared classifies Burberry releases as report_type='quarterly report',
    # document_type='press release'. They must be freshly retrieved, not seeded.
    assert "document_type IN ('presentation','press release')" in code
    assert "include_content=True" in code
    assert "AND LENGTH(content::text) <= %s" in code


def test_dossier_workflow_is_cli_owned_without_active_notebooks_or_word_parsing():
    folder = FMI.parent / "fmi-dossier"
    assert not (folder / "notebooks").exists()
    code = (
        FMI.parents[1] / "src/aily_project/services/fmi_dossier/runner.py"
    ).read_text()
    assert 'click.command("fmi-dossier")' in code
    assert "FMI_dossier_inputs.xlsx" in code
    assert "outputs/fmi-dossier" in code
    assert "read_connections" not in code
    assert "report_content" not in code and "project_report" not in code
    assert "FMI_inputs.json" not in code and "FMI_OUTPUT_DIR" not in code
    assert "--query-missing-forecasts" in code


def test_automated_notebooks_keep_database_extraction_and_json_inputs():
    paths = sorted((FMI / "notebooks").glob("*.ipynb"))
    assert [p.name for p in paths] == [
        "01_extract.ipynb",
        "02_score.ipynb",
        "03_delivery.ipynb",
    ]
    for path in paths:
        notebook = json.loads(path.read_text())
        code = "\n".join("".join(c["source"]) for c in notebook["cells"])
        assert "FMI_inputs.json" in code and "FMI_OUTPUT_DIR" in code
        assert "FMI_dossier_inputs.xlsx" not in code and "dossier.excel" not in code
        assert "fmi_dossier" not in code and "refresh_dossier_delivery" not in code
        if path.name == "01_extract.ipynb":
            assert "read_connections" in code and "AilySettings" in code
            assert "read_source" in code and "light.light_companies" in code
