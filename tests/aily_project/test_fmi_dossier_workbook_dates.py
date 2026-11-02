"""Exercise the workbook's native date conversion without Artifact Tool or AWS."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("zone", ["UTC", "Europe/Madrid", "America/New_York"])
def test_dossier_excel_timestamps_preserve_utc_under_any_host_timezone(zone):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for the isolated workbook date function")
    source = (
        Path(__file__).parents[2] / "src/aily_project/services/fmi_dossier/workbook.mjs"
    ).read_text()
    # Execute only the actual writer's pure date function; no import/cloud/export.
    function = (
        "const spreadsheetDate"
        + source.split("const spreadsheetDate", 1)[1].split("const matrix", 1)[0]
    )
    checks = """
const expected = '2026-11-02T11:14:03.673Z';
for (const input of [expected, '2026-11-02T11:14:03.673000',
                     '2026-11-02T12:14:03.673+01:00']) {
  if (spreadsheetDate(input, 'datetime').toISOString() !== expected)
    throw new Error('Timestamp shifted: '+input);
}
if (spreadsheetDate('2026-11-02', 'date').toISOString() !==
    '2026-11-02T00:00:00.000Z') throw new Error('Calendar date shifted');
"""
    subprocess.run(
        [node, "-e", function + checks],
        env={**os.environ, "TZ": zone},
        check=True,
        capture_output=True,
        text=True,
    )
