# FMI roadmap reference snapshot

Copied on 2 November 2026 from `aily-superagent-roadmap`, commit
`0deb412f771628332f6962d8e0e1e49086464e94`. The FMI source folders had no
uncommitted changes. Original files are preserved byte-for-byte; `manifest.json`
records each original relative path, size and SHA-256.

This is a historical reference, not the active delivery implementation. Its
older scores, overrides, methods and uplift must not replace the approved
dossier inputs or current exponential policy. The archived skill and GitHub
workflow are documentation only, not installed or enabled in this project.

## Contents

- [Research package](docs/research/wwd-fashion-momentum/README.md): all FMI research
  documents, reviews, methodology, prompts, captured inputs, historical delivery
  Excel/JSON, and the original builders and regression checks.
- [Historical skill](.agents/skills/update-fashion-momentum/SKILL.md) and its
  `agents/openai.yaml` configuration.
- [Historical workflow](.github/workflows/fashion-momentum-sync.yml).
- [Weighted delivery rules](docs/research/wwd-fashion-momentum/weighted-delivery.md).
- [Prospect update guide](docs/research/wwd-fashion-momentum/prospect-update-guide.md).
- [Implementation handoff](docs/research/wwd-fashion-momentum/implementation-handoff.md).

Python caches, machine-only caches and unrelated roadmap files were not copied.
Original links to Slack, GitHub or the canonical external dossier repository are
provenance references; following them is not required to regenerate the current
delivery from its saved input workbook.

## Regenerate the current delivery

From the `aily-project-starter` root:

```sh
# Reconstruct historical comparison metadata if its local cache is absent.
uv run python scripts/fmi-dossier/check_weighted_reference.py

# Calculate the current dossier delivery, not the historical roadmap snapshot.
uv run aily-project fmi-dossier
```

Both historical-comparison defaults now use files in this snapshot. The source
repo and `handover/weighted-delivery-1606_2810.xlsx` are no longer required by that
check. Existing comparison caches are not silently replaced.

The active calculation still requires `scripts/fmi-dossier/inputs/FMI_dossier_inputs.xlsx`,
`scripts/fmi-dossier/policy.yaml`, project dependencies and the spreadsheet runtime.
The accepted input workbook and dossiers remain private/git-ignored, so a fresh
Git clone alone does not include them. Transfer those inputs securely when
replicating on another computer. Ordinary runs use saved data without AWS;
explicit missing-forecast queries and the separate automated FMI workflow still
require authenticated read-only database access.

See [the active README](../../README.md) for the runtime setup, approved method,
and current Excel/JSON output contract. App upload remains outside this workflow.

## Check the archived historical delivery

This checks only the original roadmap snapshot, without modifying it or running
the current dossier score logic:

```sh
python3.12 scripts/fmi-dossier/reference/aily-superagent-roadmap/docs/research/wwd-fashion-momentum/refresh-delivery.py --check
```

The original builders use Python 3.12 f-string syntax, despite their older guide
mentioning Python 3.10+. Use Python 3.12 for this historical check; the active
project remains on Python 3.11. Run any historical regeneration experiments on a
disposable copy. Do not run
the archived `build.py` or full refresh as the current delivery command.
