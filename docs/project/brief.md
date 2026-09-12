# Project brief

Last updated: 2026-09-09

## Purpose

Turn brokerage reports into reliable, reconciled accounting imports. Complete one provider-to-ledger workflow before expanding provider coverage.

## Users

The repository owner uses GnuCash for personal brokerage/bond accounting and is considering a future move to Beancount. Discussion is currently in Russian.

## Goals and success criteria

- Parse Sberbank brokerage HTML, reconcile economic events, produce GnuCash transactions, and verify the actual saved book against expected postings and balances.
- Fail explicitly on ambiguous, unsupported or inconsistent facts; never silently repair financial data.
- Preserve financial meaning independently of the current destination so a future Beancount adapter does not require rebuilding the parser.

## In scope

- Completed RUB bond purchases, cash transfers, separate fees, purchased accrued interest (НКД), coupons, partial principal repayments and closing НКД reconciliation.
- Explicit account mapping; read-only closed-book snapshots; native multi-split CSV, verification manifests and repeat-export protection.
- Simplifying the import workflow through reliable column profiles is the next usability task.

## Out of scope

- Sales, full redemptions, realized gains, lot disposal, active foreign currencies, tax calculations and historical rewrites.
- Beancount exporter/dependency or historical migration in this milestone.
- Writing directly to GnuCash databases or importing into live books during development.

## Constraints

- Python 3.13, frozen dataclasses and Decimal; no pandas migration.
- Preserve the source parser API and original anonymized fixture.
- Only synthetic data in tracked fixtures; keep private reports, mappings, books and exports in ignored `local/`.
- GitHub/Git project, not Arcadia. Run uv checks from the repository root.
