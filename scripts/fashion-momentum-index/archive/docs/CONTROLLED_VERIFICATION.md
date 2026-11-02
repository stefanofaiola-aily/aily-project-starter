# Verification and initial coverage — 30 October 2026

Implementation: three controlled notebooks, one reusable FMI service, existing
Click CLI extended, published ConfigRepository, Excel review inputs, strict raw
scoring, peer diagnostics, display rescaling, configurable exponential uplift,
optional context and a single Excel/app result contract.

The initial delivery contains 92 unique prospect rows and 167 typed app fields.
Available headline FMI: 0. Available adjusted forecasts: 0. No neutral imputation,
manual report measurements or current-forecast historical substitutions were used.
Identity/scope, analysis, peer, financial-period and post approvals are still open.
Every prospect has explicit review/coverage/vintage statuses and missing reasons.

Read-only live validation used separate injected Light/shared connections in the
approved environment. Both read-only settings were verified before discovery and
bounded SELECTs. The snapshot retains 9,368 financial metric candidates, 31,625
Instagram capture rows, 113 correction events and underlying candidate provenance.
Current financial sources do not establish verified historical vintages. Light
forecast rows lack native vintage evidence. Early Prada captures are timezone-naive
and excluded; no timezone is guessed. Unresolved aliases/private entities remain
review tasks. Reports and historical files remain audit references, unchanged.

The manager summary is CONTROLLED_EXECUTIVE_SUMMARY.md. The operating procedure,
inputs, limitations and refresh commands are in CONTROLLED_PIPELINE.md. Generated
workbooks, raw snapshot, app JSON, resolved YAML and coverage JSON are under ignored
`outputs/fmi-controlled/`. Raw values remain there, not in tracked source files.

Verification performed:

- 66 project unit tests passed with the managed artifact runtime enabled, including
  positive end-to-end scoring/forecasting, Excel cached-value parity and refresh.
- 74 legacy FMI regressions passed; historical behavior was not changed.
- Required `uv run pytest`, Ruff lint, Ruff formatting and `ty` checks passed.
- Source/capture filtering, missingness, aliases, private/shared-only mappings,
  correction provenance, fiscal alignment, peer duplication, Trend order, score
  boundaries, cohort membership, half-up rounding and uplift gates were tested.
- Optional financial/social context, sample denominators, follower timestamp
  comparability, app units/types, review preservation and bounded SELECTs were tested.
- Workbook recalculation and formula-error scans passed. Both workbook openings
  were rendered and visually reviewed on all 11 sheets; exported cells were also
  scanned for Excel error types. Synthetic positive results matched the service.

Native Microsoft Excel application recalculation was not separately exercised.
Production historical numeric coverage still requires reviewed inputs and eligible
dated source/forecast evidence. This is a verified pipeline and explicit coverage
handover, not a claim of complete historical numeric results or predictive accuracy.
