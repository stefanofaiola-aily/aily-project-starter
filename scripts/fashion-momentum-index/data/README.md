# Automated notebook data

| Folder | Contains |
| --- | --- |
| `extract/` | Authenticated Light/shared source rows and prepared snapshot |
| `score/` | Automated components, headline scores and diagnostics |
| `delivery/` | Automated app context and final delivery rows |

Notebook 01 queries the databases; 02/03 read saved CSVs. Final output is
repository-root `outputs/fmi/weighted-delivery.xlsx/.json`. CSV reading through
`helpers.py` preserves identifiers, missingness, numeric types and nested evidence.

The independent dossier job uses `scripts/fmi-dossier/data/` and its own CSV
reader; it does not read these tables. Earlier dossier intermediates here are
historical local data, not active inputs. Generated tables stay out of git.
