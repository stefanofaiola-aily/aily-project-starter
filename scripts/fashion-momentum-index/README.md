# Fashion Momentum Index automation

**FMI_inputs.json → extraction → scoring → delivery.**

1. Edit [FMI_inputs.json](inputs/FMI_inputs.json) for identities, peer sets,
   periods/windows and review decisions.
2. Run [01_extract](notebooks/01_extract.ipynb), [02_score](notebooks/02_score.ipynb)
   and [03_delivery](notebooks/03_delivery.ipynb), using the project kernel.
3. Automated output is repository-root `outputs/fmi/weighted-delivery.xlsx/.json`.

```sh
uv sync --locked --group notebook
uv run --locked --group notebook jupyter notebook
```

Revenue, forecasts and social data come from authenticated Light/shared sources.
Settings and AWS profiles remain in `.env` or shell: your `demos` tenant and
`shared` scanner profiles. Both sessions are read-only. Extraction SQL and
scoring calculations remain unchanged. Existing per-brand JSON parameters,
including historical dossier-aligned dates/method choices, remain human inputs;
no handover document or dossier measurement Excel is read during these runs.

CSV handoffs are under ignored `data/extract/`, `data/score/` and `data/delivery/`.
`config/FMI_policy.yaml` controls this automation only. Excel is one Delivery
sheet; JSON is the corresponding flat row array. `WRITE_DELIVERY=True` replaces
stale outputs even if scores are unavailable. It does not refresh dossier files.

The independent [dossier script](../fmi-dossier/README.md) owns its Excel input,
policy, calculations, optional forecast-only query and delivery. There are no
runtime calculation imports or automatic comparison updates between the jobs.
The historical `outputs/fmi/dossier-delivery.*` reference remains unchanged.

Optional automated paths: `FMI_INPUTS_PATH`, `FMI_DATA_DIR`, `FMI_OUTPUT_DIR`.
Managed workbook runtime: `FMI_NODE`, `FMI_NODE_MODULES`. Extracts and outputs
stay out of git. See [how it works](docs/HOW_IT_WORKS.md) and
[metrics](docs/METRICS.md).
