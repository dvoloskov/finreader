# Architecture

Last updated: 2026-09-09

## System boundaries

finreader parses, interprets, reconciles, exports and verifies. GnuCash performs the import itself. The application never writes a native book. Beancount support is a future independent adapter.

## Components

- `finreader/parsers/sberbank/brokerage_report`: source-faithful frozen table models and `parse(path)`; structural validation in `_validation.py`.
- `finreader/models.py`: immutable Statement, FinancialEvent, Holding, OpeningState, Journal, JournalEntry, Posting and logical Role types.
- `finreader/sberbank.py`: `normalize_sberbank(report)`; strict operation classification, source provenance and cross-table reconciliation.
- `finreader/accounting.py`: `build_journal(statement, opening)`; explicit opening basis and balanced accounting policy.
- `finreader/validation.py`: shared errors and isolated exact Decimal arithmetic.
- `finreader/gnucash/book.py`: read-only XML/gzip/SQLite snapshots.
- `finreader/gnucash/mapping.py`: strict TOML account/commodity mapping and broker completeness checks.
- `finreader/gnucash/export.py`: preflight, native 18-column CSV, manifests, exact saved-book checks and no-op repeat exports.
- `finreader/__main__.py`: `python -m finreader export` and `verify` commands.

## Dependencies

- Runtime: BeautifulSoup and lxml; other new pipeline functionality uses the standard library.
- Tooling: uv, pytest, Ruff and basedpyright, pinned through `uv.lock`.
- External acceptance application: GnuCash 5.14 on macOS; no Beancount dependency.

## Data flow

HTML → source model → reconciled source-neutral events → journal using explicit opening book state → destination account mapping → CSV plus manifest → user imports into disposable GnuCash book → saved-book readback → verification and repeat detection.

## Invariants and constraints

- Quantities, transaction-currency values, principal, accrued interest and quoted prices are distinct.
- Market valuation is never opening book cost basis. Daily settlement and fee rows reconcile trades without duplicate postings.
- Partial repayment reduces bond value with zero quantity change; coupons and closing accrued interest follow the established НКД asset policy.
- Every transaction balances exactly. Export refuses rounding beyond destination precision or numeric limits.
- Source markers live in Notes, not assumed native transaction GUIDs. GnuCash 5.14 flattens Notes newlines into spaces: verification accepts only that transformation, not arbitrary provenance edits; new CSV Notes are single-line.
- Native XML currency quote definitions may omit fractions. Currency account definitions supply reader precision; missing security fractions remain errors.
- Actual import can reorder transactions/splits; compare semantic contents, not native GUIDs or order.

See [detailed safety/accounting contract](../pipeline.md), [actual acceptance evidence](../gnucash-acceptance.md) and [ADRs](decisions/README.md).
