# Automated input

Edit **FMI_inputs.json**, then run the top-level notebooks 01 →02 →03.
It controls mappings, peers, selected dates/windows and review decisions.
Financial/social measurements still come from authenticated Light/shared sources.

`raw/` holds original event/peer material; `legacy/` holds historical human
configuration. Generated CSV handoffs belong in `data/`, not here.

Dossier inputs now belong exclusively to
`scripts/fmi-dossier/inputs/FMI_dossier_inputs.xlsx`. That workbook was moved
unchanged. See the [separate dossier script](../../fmi-dossier/README.md).
