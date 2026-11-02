"""Dossier-only managed artifact exporter; no automated FMI writer imports."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from .model import Row, clean


def write_workbook(payload: Row, path: Path, *, previews: bool = False) -> None:
    node = os.environ.get("FMI_NODE", "node")
    modules = os.environ.get("FMI_NODE_MODULES")
    path.parent.mkdir(parents=True, exist_ok=True)
    artifacts = path.parent / ".work"
    artifacts.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dossier-workbook-") as folder:
        work = Path(folder)
        script = work / "workbook.mjs"
        script.write_bytes(Path(__file__).with_name("workbook.mjs").read_bytes())
        if modules:
            (work / "node_modules").symlink_to(Path(modules), target_is_directory=True)
        source = work / "payload.json"
        source.write_text(
            json.dumps(clean(payload), ensure_ascii=False, allow_nan=False)
        )
        staged = artifacts / path.name
        result = subprocess.run(
            [
                node,
                str(script),
                str(source),
                str(staged.resolve()),
                str(previews).lower(),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            lines = [
                line[:1000] for line in result.stderr.splitlines() if len(line) < 2000
            ]
            raise RuntimeError(
                "Dossier workbook generation failed: " + "\n".join(lines[-10:])
            )
        print(result.stdout)
        staged.replace(path)
