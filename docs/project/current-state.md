# Current state

Last updated: 2026-09-12

## Active objective

Prepare the completed Sberbank-to-GnuCash milestone for user testing on another computer. Keep the previous column mismatch open as unreproduced; fresh user-assisted import and verification passed.

## Completed

- All six stages in [the plan tracker](../../vibe/sberbank-gnucash-plan-track.md) are complete.
- Actual GnuCash 5.14 (`5.14+(2025-12-20)`), macOS 26.4.1: user manually mapped columns, imported eight transactions, saved and closed the synthetic book on 2026-09-07. Saved gzip XML contains nine transactions including the opening entry.
- The verifier confirmed all imported transaction metadata, accounts, quantities, values and opening/closing balances. Repeat export reported `Already imported and verified: 8 transactions; no files written.` No book edits were made to make verification pass.
- Closing synthetic balances: cash 14039 RUB; 15 bonds with recorded value 12100 RUB; НКД 20 RUB; fees 11 RUB; coupon income credit balance 45 RUB; external bank zero. Opening bond basis was 5100 RUB, deliberately different from source market value 5000 RUB.
- Actual import exposed and resolved missing built-in currency XML fractions and Notes newline flattening. Regression coverage uses the actual saved synthetic book.
- Full code validation rerun on 2026-09-12: 207 tests; Ruff lint/format, basedpyright and lock checks pass. Packaging smoke install and 100% public type completeness were also checked during implementation. Packaging/type-completeness checks are historical; test/lint/format/type/lock checks were rerun for handoff.

## Next actions

1. Transfer the implementation branch through GitHub and follow [another-computer instructions](../another-computer.md).
2. User runs the synthetic acceptance, then a real report against a disposable closed-book copy; no live-book imports.
3. Capture any new failures and application/OS versions. Investigate OQ-001 if it recurs; custom profile reuse remains untested.

## Blockers

- No blocker for the completed accounting/import milestone.
- UI automation through System Events failed with `osascript is not allowed assistive access` (-1728). Accessibility access or user-assisted UI testing is needed for automated-profile acceptance. Do not bypass the OS permission restriction.
- Exact UI state of the failed automatic mapping was not captured. No screenshot was supplied; user corrected the columns manually.

## Handoff notes

- Working branch: `feature/sberbank-gnucash`, created from fetched `origin/dev` (`0e60a65` baseline). The implementation and handoff documentation are being packaged in the milestone commit on this branch. Check `git status` and upstream before assuming publication; preserve any subsequent uncommitted changes. The old `main` branch is not the implementation baseline.
- Durable synthetic fixtures: `tests/data/sberbank_report_coherent.html`, `tests/data/gnucash/opening.gnucash`, `mapping.toml`, and `imported-5.14.gnucash`. The last file is decompressed native output from the actual user-performed import.
- Original `tests/data/sberbank_report_sample.html` is unchanged. Its anonymized financial totals are inconsistent; it is a parser regression fixture, not an accounting acceptance fixture.
- Historical temporary artifacts: `/private/tmp/finreader-acceptance/{disposable.gnucash,import.csv,import.csv.manifest.json}`; app mounted at `/private/tmp/finreader-gnucash-app/Gnucash.app`; downloaded image `/private/tmp/finreader-Gnucash-Intel-5.14-1.dmg`; fetched preset source `/private/tmp/finreader-gnucash514-csv-settings.cpp`. Check existence before relying on them. Do not reimport into the already imported book; make a fresh copy for new tests.
- Live user books were researched read-only under `~/Yandex.Disk.localized/gnucash`; never modify, copy into the repository, or use them for acceptance imports.
- Full usage and import steps are in the root README and `docs/gnucash-acceptance.md`. No need to repeat the earlier manual import merely to prove the already completed milestone.
- Standard checks: `uv sync --locked`, `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run basedpyright`, `uv lock --check`, `git diff --check`. If the default uv cache is sandbox-inaccessible, the previous session used `UV_CACHE_DIR=/private/tmp/finreader-research-uv-cache`; request approval for required network/GUI operations.

## 2026-09-12: CSV-profile investigation

- Reran pytest (207 passed), Ruff lint/format, basedpyright, lock check and `git diff --check`; all passed.
- Downloaded official GnuCash tag 5.14 CSV settings and assistant sources into `/private/tmp/finreader-gnucash514-{csv-settings,assistant}.cpp`. Both built-in export presets put Description fourth and Void Reason seventh; selecting the older preset alone does not explain that specific mismatch. No root cause established.
- Prepared a fresh synthetic book and export in ignored `local/csv-profile-8sjbm5r0/`: `disposable.gnucash`, `import.csv`, and manifest. Export contains eight transactions in 18 data rows, all with 18 columns and single-line Notes. User subsequently completed import, saved and quit GnuCash; verification and repeat-export protection both passed.
- Next: capture selected preset, separators, mode, and first seven preview columns before manual corrections; then validate actual import and profile reuse. No application code changed.

### Fresh import outcome

- User reported the preview now looked correct after being instructed to select GnuCash Export Settings, then completed import. No screenshot or exact column-by-column UI capture was available; do not claim the previous mismatch has an established root cause.
- First verification refused the open book due to `.LCK`. After the user quit GnuCash, verification confirmed transaction metadata, split quantities/values, and opening/closing balances. Repeat export reported eight already imported and verified transactions; no files written.
- Fresh built-in-preset workflow has successful user-assisted import/readback evidence. A separately saved Finreader profile and its reuse have not been tested. Do not reimport into this now-imported test book.
