# Project Rules

- This is a standalone project, not part of the FIN uv workspace.
- Import published Aily libraries; do not copy their code or use sys.path hacks.
- Keep one Click CLI; business logic belongs in services and accepts clients.
- Initialize AilySettings once per task entry point before DAL/configuration.
- Never create cloud clients or initialize settings at import time.
- Keep tenant/environment in .env or shell, never hardcode them in source.
- Database examples use the ro role and read-only sessions. Preserve this default.
- Shared/global database access uses `Dal.shared_db`; initialize AilySettings first.
- Shared DB credentials are separate from the tenant DB credentials and are resolved
  by DAL from Secrets Manager. Do not hardcode or print credentials.
- Set `default_transaction_read_only=on` on shared DB sessions and verify it before
  exploratory reads. The default shared secret route may authenticate as `dbo`;
  session read-only is not a replacement for database-enforced read-only grants.
- For shared DB exploration, discover schemas/tables first, then issue scoped,
  reviewed SELECT queries with explicit column lists and bounded date/row filters.
- Never execute DDL/DML against the shared database from an exploratory agent task.
- Never commit credentials, index tokens, tenant extracts, or notebook outputs.
- Add isolated pytest tests for behavior changes. Mark unit tests with unit.
- Run uv run pytest, uv run ruff check ., uv run ruff format --check .,
  and uv run ty check before shipping.
- Commit uv.lock after authenticated dependency resolution. Do not copy FIN's lock.
- Promote runnable batch jobs to services/<service>/tasks/<task>/ as they grow.
- Use Aily ConfigRepository for tenant-specific business configuration.
- Consult current centrally maintained Aily skills when available; do not freeze
  copied FIN skills into this template.
