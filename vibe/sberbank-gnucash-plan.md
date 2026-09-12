# Sberbank → GnuCash, with a Beancount-ready core

## Task

Build Sberbank HTML → source-faithful parsed report → destination-independent financial events → accounting journal → verified GnuCash 5.x multi-split CSV import. Base implementation on `origin/dev`, preserving frozen dataclasses, Decimal arithmetic, and the existing parser API. Beancount serialization and historical migration are deferred.

## Execution stages

### Stage 1: Harden source parsing

Reject malformed data rows, missing required fields, invalid/non-finite values and duplicate sections with section/row/field diagnostics. Preserve recognized structural rows and absent-versus-empty tables. Do not correct financial inconsistencies while parsing.

Verification: existing parser tests, Ruff, basedpyright.

### Stage 2: Parser tests and coherent fixtures

Test public parsers for malformed shapes, values, duplicates, optional tables and valid formats. Preserve the original anonymized sample and add a financially coherent synthetic report with grouped settlements, purchases, fees, coupons, partial principal repayment and closing accrued interest.

Verification: `uv run pytest tests/parsers/sberbank/brokerage_report`.

### Stage 3: Financial events and accounting

Add frozen statement/event/journal/posting types and public `normalize_sberbank` and `build_journal`. Preserve dates, security identity, acquisition facts and provenance independently of destination accounts. Support completed RUB bond purchases, funding/withdrawals, separate fees, coupons, partial principal repayment, and period-end НКД reconciliation. Match cash settlement/fee rows against trades without double counting. Reconcile cash, quantities, totals and НКД exactly. Never infer book basis from market value.

Purchases increase quantity/principal and НКД against cash on settlement date; coupons increase cash against НКД; period-end adjustments reconcile НКД against coupon income. Principal repayment reduces bond value without changing quantity. Reject ambiguous/unsupported operations, unexplained differences and insufficient basis. Sales, full redemption, FX, lot disposal and tax calculations are unsupported.

Verification: existing suite and basedpyright.

### Stage 4: Accounting tests

Test all supported operations, grouped settlement, opening holdings, exact balancing, deterministic IDs, unsupported operations and reconciliation failures. Confirm the original sample parses but fails financial reconciliation.

Verification: `uv run pytest`.

### Stage 5: GnuCash adapter and CLI

Add explicit TOML account/commodity mappings; read closed SQLite/XML/gzip snapshots without writes. Export native multi-split CSV with independent quantities and values and stable markers in notes. Add `python -m finreader export REPORT --book SNAPSHOT --mapping CONFIG --output CSV` and `python -m finreader verify --book IMPORTED_SNAPSHOT --manifest MANIFEST`. A manifest records expected transactions and balances. Validate before output; refuse conflicting/partial/overlapping imports and permit an exact verified repeat as a no-op. No direct book writes. Keep private inputs, configurations and exports untracked.

Documentation: https://www.gnucash.org/docs/v5/C/gnucash-manual/trans-import.html

Verification: CLI help, existing suite, Ruff and basedpyright.

### Stage 6: Actual import, adapter tests and documentation

Test readers, mapping, CSV precision/escaping, manifests and duplicate/readback checks. Import into a sanitized disposable GnuCash 5.x book, save, and verify all splits, quantities, values, balances and notes. Record exact tested version/settings. Document supported operations, commands and recovery. Actual GnuCash import/readback is mandatory for completion; file generation alone is insufficient. Never modify the user's live books or rewrite history.

Final verification:

```bash
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run basedpyright
uv lock --check
```
