# GnuCash 5.x disposable-book acceptance

## Current status

**Passed on 2026-09-07 using an actual GnuCash 5.14 import and saved-book readback.** The user manually mapped the CSV columns, imported eight transactions into the synthetic book, then saved and closed GnuCash. Both the verifier and repeat-export check succeeded without modifying that book.

Application: GnuCash 5.14, build `5.14+(2025-12-20)`, macOS 26.4.1. Saved format: gzip-compressed native XML. The regression fixture `tests/data/gnucash/imported-5.14.gnucash` is the decompressed synthetic saved book, not a simulated importer result.

**Column preset caveat:** the user observed Description mapped to Void Reason and corrected the mappings manually. The exact UI preset/selection state was not captured, so automatic preset matching is not claimed as validated. The successful import used the logical column assignments documented below.

Actual import exposed two adapter compatibility bugs, now fixed and covered by regression tests:

- Built-in currency quote definitions may omit `cmdty:fraction`; the reader resolves the currency from its account definitions, as for an absent standalone currency definition. Missing security fractions remain errors.
- GnuCash flattens newlines in Notes to spaces. Verification tolerates that exact transformation while continuing to reject changed provenance, missing markers, duplicate events, changed transactions and changed splits. New CSV exports emit single-line Notes.

Acceptance output:

```text
Verified transactions, split quantities/values and opening/closing balances.
Already imported and verified: 8 transactions; no files written.
```

No live book was opened or modified. System Events automation was unavailable due to Accessibility permissions; the user performed the GUI steps.

Prepared files for this session:

- `/private/tmp/finreader-acceptance/disposable.gnucash`
- `/private/tmp/finreader-acceptance/import.csv`
- `/private/tmp/finreader-acceptance/import.csv.manifest.json`

These temporary paths are not durable artifacts. Reproduce them using the README commands if needed.

## Import procedure

1. Copy `tests/data/gnucash/opening.gnucash` into ignored `local/` and export the coherent report as shown in the README. Never open the tracked fixture for editing.
2. Open the copied book in GnuCash 5.x. Dismiss first-run/tip dialogs without creating a different book.
3. Select **File → Import → Import Transactions from CSV** and choose the generated CSV.
4. Select **GnuCash Export Settings** (the current preset, not the GnuCash 4 preset), **Multi-split**, UTF-8, comma separator, one header row to skip, ISO `YYYY-MM-DD` dates, and decimal-point number format.
5. Confirm the 18 columns map as follows. Do not let the importer infer prices or balancing accounts.

| Column | Import property |
|---|---|
| Date | Date |
| Transaction ID | Transaction ID |
| Number | Number |
| Description | Description |
| Notes | Notes |
| Commodity/Currency | Commodity/Currency |
| Void Reason | Void Reason |
| Action | Action |
| Memo | Memo |
| Full Account Name | Account |
| Account Name | None |
| Amount With Sym | None |
| Amount Num. | Amount |
| Value With Sym | None |
| Value Num. | Value |
| Reconcile | Reconcile |
| Reconcile Date | Reconcile Date |
| Rate/Price | Price (blank; explicit Value takes precedence) |

6. Confirm existing synthetic accounts are matched. There should be **8 new transactions**, with no imbalance/orphan account, no automatic additional balancing split, and no update/replacement of the opening transaction.
7. Finish import, save, and close the book (or quit GnuCash) so its lock file is removed.
8. Run the `verify` command from the README against that saved book and the manifest.
9. Rerun the original export command against the imported book. It must say already imported/verified and write no files. Do not manually reimport the CSV as a deduplication test: that bypasses finreader's preflight.

## Expected results

The synthetic opening book has cash 1000 RUB, 5 bonds with **5100 RUB book basis** (the source market valuation is only 5000), purchased/earned accrued interest asset 25 RUB, and external bank funds 20000 RUB.

| Account/result | Closing quantity | Closing recorded RUB value |
|---|---:|---:|
| Broker cash | 14039 | 14039 |
| Bond | 15 | 12100 |
| Bond НКД asset | 20 | 20 |
| External bank | 0 | 0 |
| Fee expense | 11 | 11 |
| Coupon income, credit-sign balance | -45 | -45 |

Two purchases share one settlement cash row. The 3000 RUB partial principal repayment must have a bond split with **quantity 0, value -3000**. Closing interest adjustment is +45 RUB to НКД and -45 RUB to coupon income. Every transaction's RUB split values sum to zero.

## Regression evidence

`test_real_gnucash_514_import` verifies the actual saved synthetic book against the prepared journal and balances. `test_actual_import_repeat_writes_nothing` checks that repeating export creates no files and leaves the saved fixture unchanged. Additional tests cover native Notes flattening without accepting altered source references and missing security fractions.

Automatic column-profile selection remains a usability follow-up, not a verified capability of this acceptance run.

## Official references

- [GnuCash 5 transaction import manual](https://www.gnucash.org/docs/v5/C/gnucash-manual/trans-import.html)
- [Native CSV preset column definitions](https://code.gnucash.org/docs/STABLE/gnc-imp-settings-csv-tx_8cpp_source.html)
- [Importer amount/value split handling](https://code.gnucash.org/docs/STABLE/gnc-imp-props-tx_8cpp_source.html)

## 2026-09-12: Fresh user-assisted preset import

Prepared a new synthetic book and current CSV in ignored `local/csv-profile-8sjbm5r0/`. The user was instructed to select **GnuCash Export Settings** (not the GnuCash 4 variant), reported that the preview looked correct, and completed import. No screenshot or exact UI-state capture was available. The earlier Description/Void Reason mismatch was not reproduced; its cause remains unknown. A custom saved profile and profile reuse were not tested.

Verification initially refused the book because its `.LCK` was present. After the user quit GnuCash, both checks passed:

```text
Verified transactions, split quantities/values and opening/closing balances.
Already imported and verified: 8 transactions; no files written.
```

The book was not edited to make verification pass. It is now imported; use another fresh copy for any further import test. Live books were not used.
