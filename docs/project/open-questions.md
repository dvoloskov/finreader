# Open questions

Last updated: 2026-09-12

## Active

### OQ-001: Why did automatic CSV mapping assign Description to Void Reason?

- Impact: manual column selection undermines the desired simple import workflow. Actual accounting import is verified, automatic preset selection is not.
- Evidence: generated CSV consistently has 18 columns; Description is fourth, Void Reason seventh. The official GnuCash 5.14 preset source fetched during investigation uses those same positions. The user observed incorrect mapping and corrected columns manually before successfully importing.
- Owner: next implementing agent, with user-assisted UI capture if Accessibility remains unavailable.
- Next step: reproduce with a fresh synthetic book, capture the actual preset/separators/preview, compare the 5.14 preset and current single-line Notes output, then validate a saved profile. Root cause must be established rather than guessed.
- 2026-09-12: Fresh CSV structural checks passed; both built-in 5.14 export presets have identical first seven column assignments. User reported correct preview and completed import using the fresh synthetic files under `local/csv-profile-8sjbm5r0/`; saved-book verification and repeat-export checks passed after quitting GnuCash. No screenshot was captured, no root cause established, and saved-profile reuse remains untested.
- Status: Open. The earlier suggestion to reselect the preset was not confirmed as a fix.

### OQ-002: What should a future Beancount migration include?

- Impact: determines a later adapter and possible historical inventory/lot migration, not the completed GnuCash milestone.
- Owner: repository owner for scope; implementing agent for subsequent technical research.
- Next step: when that work is requested, decide new-report export versus historical migration and investigate lot/cost semantics using official Beancount documentation.
- Status: Deferred. Keep the neutral event boundary; do not add Beancount dependencies now.

## Resolved

- 2026-09-07: Actual multi-split CSV import, including a zero-quantity bond-value reduction, passed GnuCash 5.14 readback and repeat detection. See [acceptance evidence](../gnucash-acceptance.md).
- 2026-09-07: Missing built-in currency fractions and Notes newline flattening were reader/verifier compatibility issues, not incorrect user postings; fixed in `gnucash/book.py` and `gnucash/export.py` with actual-import regression tests.
- 2026-09-06–07: Use frozen dataclasses/Decimal and a destination-neutral core, not pandas or a CSV intermediate model. See [ADR-0001](decisions/0001-neutral-core-and-gnucash-boundary.md).
- 2026-09-06–07: New partial principal repayments reduce book value without changing quantity, rather than crediting gross income; do not rewrite historical entries. See [ADR-0002](decisions/0002-rub-bond-accounting-policy.md).
