# Progress tracker for sberbank-gnucash-plan.md

Status format: [ ] - not processed, [X] - completed

## Execution Stages

[X] Stage 1: Harden source parsing
[X] Stage 2: Parser tests and coherent fixtures
[X] Stage 3: Financial events and accounting
[X] Stage 4: Accounting tests
[X] Stage 5: GnuCash adapter and CLI
[X] Stage 6: Actual import, adapter tests and documentation

## Notes

- 2026-09-06: Created `feature/sberbank-gnucash` from freshly fetched `origin/dev`. This GitHub project uses Git/uv, not Arcadia/ya; no Arcadia rebase commands apply. Live books will not be modified.
- Stage 1: 105 tests passed; Ruff and basedpyright clean. Required-field/layout validation now runs at each public table parser boundary.
- Stage 2: 117 public-parser tests passed; coherent fixture added separately; Ruff and basedpyright clean.
- Stage 3: Existing 117 tests and checks pass. Coherent report smoke test produces 7 events / 8 balanced entries, closing cash 14039, 15 bonds with basis 12100 and NKD 20 from explicit premium opening basis 5100.
- Stage 4: 142 tests passed; Ruff and basedpyright clean. Added operation/reconciliation, grouped settlement, opening basis, deterministic identity and Decimal-context tests.
- Stage 5: Implemented read-only XML/gzip/SQLite snapshots, explicit TOML mapping, native CSV plus manifest, repeat/conflict preflight and export/verify CLI. Existing 142 tests, CLI help, Ruff and basedpyright pass. Adapter-specific/actual-app acceptance follows in Stage 6.
- 2026-09-07: Stage 6 automated work: 202 tests pass; `uv sync --locked`, pytest, Ruff lint/format, basedpyright, `uv lock --check`, and `git diff --check` pass. Packaging smoke installation succeeds; public type completeness is 100%. Fixed the CI verify-types install command to stop requesting the nonexistent dev extra.
- Earlier Stage 6 blocker (resolved later on 2026-09-07): actual GnuCash 5.14 (`5.14+(2025-12-20)`) was downloaded/mounted read-only and launched on the synthetic disposable book, but System Events returned “osascript is not allowed assistive access” (-1728). User input requested for Accessibility access or manual import. No actual CSV import/readback success is claimed. See `docs/gnucash-acceptance.md` for prepared paths, settings and expected balances.
- Live GnuCash books and the original anonymized HTML fixture were not modified. All application acceptance artifacts are synthetic and under `/private/tmp/finreader-acceptance`. At that point no commit had been created while acceptance was outstanding.
- 2026-09-07: Stage 6 completed after the user manually mapped/imported CSV and saved/closed the synthetic book. Actual GnuCash 5.14 readback matches all 8 imported transactions, quantities, values and opening/closing balances. Repeat export reports already imported and writes no files. Fixed native built-in currency definitions without fractions and Notes newline flattening; saved a synthetic actual-import regression fixture. All 207 tests, Ruff, formatting, basedpyright and lock checks pass.
- Automatic preset mapping is NOT marked verified: the user reported Description → Void Reason and manually corrected the columns. Documented as a usability follow-up. No saved-book edits were made to make verification pass.
