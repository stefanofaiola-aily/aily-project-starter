# How FMI works

## Automated workflow

Edit `inputs/FMI_inputs.json`. It controls identities, approved parent proxies,
peers, selected periods, social windows and review decisions. Existing business
parameters seeded from documents remain editable JSON, not runtime Word reads.
Some internal selectors still use the historical name dossier; they select
database observations and do not import the separate dossier script's logic.

Run the top-level notebooks in order:

1. `01_extract.ipynb`: initialize AilySettings once, verify read-only Light/shared
   connections, discover relations, issue bounded SELECTs and save source and
   prepared CSV tables under `data/extract/`. Failed extraction does not replace
   a complete snapshot.
2. `02_score.ipynb`: read the saved database tables, calculate revenue growth,
   peer medians, IR, Social, Trend and one headline per brand. Save `data/score/`.
3. `03_delivery.ipynb`: normalize, calculate both uplift scenarios and app context;
   save `data/delivery/` and `outputs/fmi/weighted-delivery.xlsx/.json`.

Dates, reporting scope, units, source provenance and review control eligibility.
Missing required score components leave FMI blank with reasons. Missing compatible
forecast baselines leave adjusted amounts blank without erasing valid scores.
One missing peer does not block an otherwise valid approved peer subset.
Dossier amounts are never substituted for database measurements.

Tenant/environment and AWS profiles remain in `.env` or shell. The configured
`demos` tenant and `shared` scanner profiles have separate DAL credentials.
Use `FMI_INPUTS_PATH`, `FMI_DATA_DIR`, `FMI_OUTPUT_DIR` to override paths.
Automation's policy is `config/FMI_policy.yaml`.

The last database output remains the saved 2 November run: 94 rows, 17 complete
FMI and no compatible adjusted forecasts. No fresh automation extraction was
performed during the dossier separation. Details remain in
[the one-time coverage check](SCORE_COVERAGE_CHECK_2026-11-02.md).

## Separate dossier workflow

The document-based task is in `scripts/fmi-dossier/`, with its own
`services/fmi_dossier/` logic. It shares no scoring, policy or workbook code with
the automation. Only general published libraries and managed runtime settings
are common technical infrastructure.

Its input is `scripts/fmi-dossier/inputs/FMI_dossier_inputs.xlsx`, populated once
from handover brand/new-prospect documents and supporting source workbooks.
Refresh source cells only when documents are added/changed. Recurring calculations
read this Excel, never Word, automatic JSON/CSV or automatic delivery.

```sh
uv run aily-project fmi-dossier --previews
uv run aily-project fmi-dossier --query-missing-forecasts --previews
```

The second command optionally queries missing forecast amounts from Light with
its own verified read-only connection. It does not refresh revenue/social score
measurements. Candidates need confirmed identity, target alignment, native scope,
currency, units and an unadjusted-baseline review before uplift can use them.

It produces `outputs/fmi-dossier/dossier-calculated-delivery.xlsx/.json`, with
reported/weighted FMI, normalization, previous and exponential uplifts, driver
metrics, source references, statuses and an app field dictionary. Missing baselines
do not erase dossier FMI. The original input Excel is never overwritten by a run.

Full input/run instructions and formulas are in the
[independent dossier README](../../fmi-dossier/README.md).

## Isolation

Neither job modifies the other's input, policy or calculated output, even when
sharing an output directory, because their delivery filenames differ. Automated
delivery no longer reads handover reports or refreshes existing dossier comparison
columns. The historical `outputs/fmi/dossier-delivery.xlsx/.json` stays frozen.
No dossier service imports the automated FMI service.
