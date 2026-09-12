# Pipeline and safety contract

## Layers

1. `parsers/sberbank/brokerage_report`: existing frozen source-table dataclasses. Structural checks reject malformed rows, duplicate sections and non-finite numbers with section/row/field context. Recognized headers, section rows, totals and spacers remain supported.
2. `sberbank.normalize_sberbank`: reconcile cash and trade totals, grouped settlement/commission rows, quantities, nominal principal changes and closing НКД; produce immutable `Statement` and `FinancialEvent` objects with source-row references.
3. `accounting.build_journal`: apply accounting policy using explicit `OpeningState`; return balanced `JournalEntry` / `Posting` records and closing holdings. Logical account roles and separate quantities/values are destination independent.
4. `gnucash`: read-only snapshots, explicit destination mapping, CSV serialization, provenance markers and independent readback checks. Native GUIDs, paths and commodity namespaces stay here.

The source's percentage bond quote is checked against nominal value and the reported principal rounded to kopecks. It is not a RUB unit price. Book basis comes from the book, never the portfolio market valuation. Core arithmetic uses an isolated Decimal context and rejects inexact calculations; the invoice check has an explicit half-up kopeck rounding rule. The exporter refuses values beyond account precision, RUB kopecks, or GnuCash's signed 64-bit numeric range.

## Mapping and snapshots

Use `tests/data/gnucash/mapping.toml` as the synthetic example. Copy it to `local/` before inserting private details.

- `contract_code` must match the report's source contract.
- `broker_root` identifies the whole broker subtree for overlap and completeness checks.
- `cash`, `external`, `fees`, and `income` map distinct existing RUB accounts.
- Each `[securities.ISIN]` maps an existing `bond`, `nkd` and native `commodity` (`namespace::mnemonic`). The source ISIN is authoritative; an existing nonempty commodity identifier must agree. No fuzzy name matching or automatic account creation is performed.
- All portfolio securities must be explicitly mapped. Cash, bonds and НКД belong under the broker root; the external funding account is outside it. Unmapped nonzero opening balances block export, but historically used accounts that are now zero do not.
- Bond accounts must be STOCK/MUTUAL; НКД must be an asset account; fees EXPENSE; coupon income INCOME. Placeholder accounts are rejected.

Only use **closed, consistent snapshots**, preferably outside a sync directory. SQLite is opened with `mode=ro&immutable=1` and query-only enabled. Lock/WAL/journal sidecars cause refusal. XML/gzip is read without DTD/entity expansion; XML input is limited to 128 MiB. The reader has no book-writing interface.

Opening quantities and НКД must match the statement. Nonzero opening holdings require positive recorded basis. Existing transactions in external funding accounts remain part of the verification baseline and are not duplicated or overwritten.

## Posting policy

| Event | Debit/increase | Credit/decrease |
|---|---|---|
| Purchase | Bond quantity/principal; purchased НКД | Broker cash |
| Funding | Broker cash | External account |
| Withdrawal | External account | Broker cash |
| Fees | Investment expense | Broker cash |
| Coupon receipt | Broker cash | Bond's НКД asset |
| Principal repayment | Broker cash | Bond principal value; zero quantity change |
| Closing НКД adjustment | НКД asset (signed difference) | Coupon income (opposite signed difference) |

An intermediate negative НКД balance after coupon payment is expected under this policy; the closing adjustment reconciles it. There are no tax, market revaluation or realized-gain postings. Tax-summary source tables are not treated as duplicate economic events.

Supported descriptions are deliberately explicit: `Зачисление д/с`, `Списание д/с`, `Сделка от DD.MM.YYYY`, `Комиссия Биржи от DD.MM.YYYY`, `Комиссия Брокера оборотная от DD.MM.YYYY`, and the sample's coupon/amortization descriptions. Unknown variants fail instead of guessing. A settlement/fee group must match trade date, settlement date, venue, currency and exact total. The first version supports one active RUB cash balance and one portfolio row per security.

## Repeats and recovery

Transaction notes carry versioned source/statement/event markers and source-row references. CSV Notes are single-line; verification also accepts the newline-to-space transformation observed in GnuCash 5.14 for earlier multiline Notes, without ignoring other content changes. The CSV transaction ID groups rows; it is not assumed to persist as a native GUID or to provide importer deduplication.

- Fresh export requires an empty broker period with no later broker activity. Previously marked statement periods must end before the requested period.
- An exact repeat is a no-op only after matching every expected transaction and split against the saved book.
- Missing markers, partial imports, changed overlapping statements, manual broker activity in the period, or later broker transactions cause refusal.
- Exporting a file does not mark it imported. Existing output files are never overwritten. Both output contents are rendered before exclusive file creation; failures clean up only files created by that call.
- If import fails or readback differs, discard the disposable book and restart from a clean snapshot. Do not patch the live book or automatically rewrite historical entries.
- After unrelated backdated changes, obtain a new closed snapshot and regenerate/verify. The manifest checks opening/closing balances and account GUIDs, not merely file presence.

A manifest is a local expected-results artifact, not a signed audit certificate. Preserve it with its CSV and source report. Keep all private artifacts in ignored `local/`.

## Future Beancount adapter

Translate `Statement` / `FinancialEvent` facts with acquisition dates, security identities, quantities, principal, acquired interest and fees. Implement destination-specific inventory/lot transformations separately; a GnuCash zero-quantity value adjustment is not prescribed as Beancount syntax. Export support and historical migration remain separate future work.
