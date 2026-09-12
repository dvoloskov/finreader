# Work log

Keep the latest 20 material handoffs here. Archive older entries under `archive/YYYY-MM.md`.

## 2026-09-12: Prepare cross-computer handoff

- User approved committing the completed implementation and will perform real-report testing on another computer. Added `docs/another-computer.md` with branch retrieval, a non-overwriting synthetic setup, verification/repeat checks, and private-copy precautions.
- Reviewed changed-file inventory and tracked diff; private `local/` files are excluded. Milestone commit/publication is performed after checks; inspect Git for the resulting commit/upstream state.
- Follow-up: user runs synthetic acceptance and then a supported real report against a separate book copy. Earlier CSV mismatch remains unreproduced; no new accounting functionality added.

## 2026-09-12: Verify fresh user-assisted import

- User reported a correct preview and imported into `local/csv-profile-8sjbm5r0/disposable.gnucash`. No UI screenshot captured; prior mismatch not reproduced, root cause still unknown.
- Validation: verifier safely refused while `.LCK` existed; after user quit GnuCash, saved-book transaction/split/balance verification passed. Repeat export verified eight transactions and wrote nothing.
- Handoff: built-in-preset user-assisted workflow has fresh successful readback evidence. Saved custom profile/reuse remains untested. This disposable book is now imported; never reimport into it. No implementation changes or live-book writes.

## 2026-09-12: Start CSV-profile reproduction

- Inspected official GnuCash 5.14 preset/application source and generated a fresh synthetic export in ignored `local/csv-profile-8sjbm5r0/`. Both built-in presets agree on Description/Notes/Commodity/Void Reason positions; no speculative exporter fix made.
- Validation: 207 tests, Ruff lint/format, basedpyright, lock and diff checks passed; all 18 CSV data rows have 18 columns and single-line Notes.
- Handoff: awaiting user-assisted screenshot of preset/separators/preview before correcting mappings. Actual profile acceptance remains open; live books untouched.

## 2026-09-09: Save completed milestone and next investigation

- Changes: initialized repository-owned context and AGENTS routing; captured neutral-core and accounting decisions, actual GnuCash acceptance, uncommitted branch state, privacy constraints and next steps. Clarified the tracker's historical UI blocker without deleting its chronology.
- Validation: inspected Git status/branch and existing implementation documents; context structure/link and whitespace checks performed. No application code or live books changed. Last full code validation remains 207 passing tests and clean lint/format/type/lock checks on 2026-09-07.
- Follow-ups: reproduce and fix automatic Description/Void Reason column mapping; record the actual UI configuration. UI automation still requires Accessibility permission or user assistance. Beancount migration scope is deferred.
