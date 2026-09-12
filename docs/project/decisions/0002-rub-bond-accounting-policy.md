# ADR-0002: Explicit RUB bond principal and accrued-interest accounting

- Status: Accepted
- Date: 2026-09-09
- Supersedes: None
- Superseded by: None

## Context

This record captures the accounting policy agreed and implemented on 2026-09-06–07. Existing user conventions separate broker cash, bond positions, per-bond НКД assets, fees and coupon income. The user accepted treating new partial principal repayments as book-value reductions instead of gross income.

## Decision

Support completed RUB purchases, cash transfers, separate fee expenses, coupons, partial principal repayment and period-end НКД reconciliation. Purchases add principal/quantity and purchased НКД against cash on settlement date. Coupons increase cash against НКД; a closing adjustment reconciles НКД against coupon income. Partial principal repayment increases cash and reduces bond recorded value with no quantity change. Use explicit opening book basis, never market valuation. Reconcile nominal changes and grouped trade settlements without duplicate postings. Reject insufficient basis and unsupported/ambiguous operations instead of inferring gains or history.

## Consequences

- Sales, full redemptions, realized gains, tax calculations, FX and lot disposal are outside this milestone.
- Existing historical postings are not automatically rewritten.
- Same-day purchase/repayment ordering requiring intraday information is explicitly unsupported.
- The actual-import synthetic fixture independently validates principal, quantities, accrued interest and closing balances; this is not a tax-accounting implementation.
