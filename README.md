# finreader

Parse Sberbank brokerage HTML reports and prepare reconciled RUB bond transactions for GnuCash 5.x.

**Status:** actual GnuCash 5.14 import/readback and repeat-export verification passed on the synthetic book with manually mapped columns. Automatic preset matching still needs investigation. Start with a disposable book; see [acceptance evidence](docs/gnucash-acceptance.md).

## Quick start

Python 3.13 and uv are required. Run commands from the repository root.

```bash
uv sync --locked
mkdir -p local
cp tests/data/gnucash/opening.gnucash local/disposable.gnucash
uv run python -m finreader export tests/data/sberbank_report_coherent.html \
  --book local/disposable.gnucash \
  --mapping tests/data/gnucash/mapping.toml \
  --output local/import.csv
```

This writes CSV plus `local/import.csv.manifest.json`, not transactions into a book. Import using the [GnuCash instructions](docs/gnucash-acceptance.md), save and close GnuCash, then verify:

```bash
uv run python -m finreader verify \
  --book local/disposable.gnucash \
  --manifest local/import.csv.manifest.json
```

After a successful import, rerunning export against that saved book verifies the existing transactions and writes nothing. Reimporting the CSV directly through GnuCash bypasses this protection.

## Supported accounting

- Completed RUB bond purchases, posted on settlement date; original trade date, number, percentage quote, principal, fees and acquired accrued interest (НКД) remain available in financial events.
- Broker funding/withdrawals and separately expensed brokerage/exchange fees.
- Coupons received against per-bond НКД assets; period-end НКД reconciliation against coupon income.
- Partial principal repayment reduces the bond's recorded value, without changing quantity. This is not gross income or a historical correction.
- Daily settlement and fee cash rows reconcile against trades; they never duplicate the trade cash postings.

Sales, full redemptions, lot disposal, foreign-currency activity, incomplete trades, ambiguous descriptions, and same-day purchase/partial-repayment ordering are rejected. Empty foreign-currency balance rows are informational. Principal repayment exceeding available basis requires a separate policy and is rejected. No tax calculations or market-value-to-cost-basis inference are performed.

See [architecture and safety](docs/pipeline.md) for mappings, opening balances and failure recovery.

## Проверка на другом компьютере

См. [получение ветки, синтетический тест и безопасная проверка личного отчёта](docs/another-computer.md).

## Python interfaces

```python
from finreader.parsers.sberbank.brokerage_report import parse
from finreader.sberbank import normalize_sberbank
from finreader.accounting import build_journal
from finreader.models import Holding, OpeningState
```

`parse(path)` remains source-faithful and distinguishes absent tables from present empty tables. `normalize_sberbank(report)` returns reconciled destination-independent facts; `build_journal(statement, opening)` requires explicit book quantities, cost basis and НКД. All monetary values use `Decimal`.

GnuCash-specific public functions live in `finreader.gnucash`: `book.read_book`, `mapping.load_mapping`, and `export.export_report`, `prepare_export`, `load_manifest`, `verify_book`.

Beancount is a future adapter, not a current dependency. The canonical intermediate representation is financial events, not GnuCash CSV; no historical migration is implemented.

## Development

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run basedpyright
uv lock --check
```

The original anonymized sample remains a structural parser fixture: its financial totals are inconsistent, so accounting rejects it. The separate coherent report and GnuCash book contain synthetic identities and independently specified balances. Keep real reports, books, mappings and generated exports in ignored `local/`; do not commit them.

Implementation plan and progress are in [vibe](vibe/sberbank-gnucash-plan-track.md).
