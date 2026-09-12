"""Public financial interpretation and accounting contract tests."""

from dataclasses import replace
from decimal import Decimal, localcontext

import pytest

from finreader.accounting import build_journal
from finreader.models import EventKind, Holding, OpeningState, Role, Statement, ZERO
from finreader.parsers.sberbank.brokerage_report import SberbankBrokerageReport, parse
from finreader.parsers.sberbank.brokerage_report.tables.trades import (
    TradeDirection,
    TradeStatus,
)
from finreader.sberbank import normalize_sberbank
from finreader.validation import ReconciliationError

D = Decimal


@pytest.fixture
def report() -> SberbankBrokerageReport:
    """Load an independent financially coherent report."""
    return parse('tests/data/sberbank_report_coherent.html')


@pytest.fixture
def statement(report: SberbankBrokerageReport) -> Statement:
    """Normalize once per test to prevent mutation leakage."""
    return normalize_sberbank(report)


@pytest.fixture
def opening() -> OpeningState:
    """Use a premium opening basis different from reported market value."""
    return OpeningState(D(1000), (Holding('RU000TEST001', D(5), D(5100), D(25)),))


def test_complete_journal(statement: Statement, opening: OpeningState) -> None:
    """Preserve cost basis, quantity and NKD with every transaction balanced."""
    journal = build_journal(statement, opening)
    assert len(statement.events) == 7
    assert len(journal.entries) == 8
    assert journal.closing == OpeningState(
        D(14039), (Holding('RU000TEST001', D(15), D(12100), D(20)),)
    )
    assert all(sum((p.value for p in e.postings), ZERO) == 0 for e in journal.entries)
    repayment = next(e for e in journal.entries if 'амортизация' in e.description)
    bond = next(p for p in repayment.postings if p.role == Role.BOND)
    assert bond.quantity == 0 and bond.value == -3000
    accrual = journal.entries[-1]
    assert [(p.role, p.value) for p in accrual.postings] == [
        (Role.NKD, D(45)),
        (Role.INCOME, D(-45)),
    ]
    assert (
        sum(
            (
                p.value
                for e in journal.entries
                for p in e.postings
                if p.role == Role.FEES
            ),
            ZERO,
        )
        == 11
    )


def test_grouped_settlement_and_acquisition_provenance(statement: Statement) -> None:
    """Two trades consume one cash settlement while retaining trade facts."""
    buys = [e for e in statement.events if e.kind == EventKind.BUY]
    assert len(buys) == 2
    assert all('cash_flow:2' in e.source_rows for e in buys)
    assert all(e.trade_date is not None and e.trade_date < e.date for e in buys)
    assert all(e.quoted_price == 100 for e in buys)
    assert sum((e.amount + e.nkd for e in buys), ZERO) == 10050


def test_deterministic_ids(report: SberbankBrokerageReport) -> None:
    """Repeated normalization preserves statement and event identities."""
    assert normalize_sberbank(report) == normalize_sberbank(report)


def test_original_sample_is_not_financially_consistent() -> None:
    """Anonymization did not preserve accounting identities; never repair it silently."""
    report = parse('tests/data/sberbank_report_sample.html')
    with pytest.raises(ReconciliationError, match='Cash-flow printed totals'):
        _ = normalize_sberbank(report)


@pytest.mark.parametrize(
    'case',
    [
        'sale',
        'pending',
        'currency',
        'missing_amount',
        'unknown_security',
        'duplicate_trade',
        'totals',
        'quantity',
        'missing_table',
        'ambiguous_name',
        'bad_summary',
        'unknown_cash',
        'group_date',
    ],
)
def test_source_rejections(report: SberbankBrokerageReport, case: str) -> None:
    """Unsupported and inconsistent facts cannot reach an exporter."""
    assert report.trades is not None and report.portfolio is not None
    assert report.cash_flow is not None and report.securities is not None
    t = report.trades.rows[0]
    if case == 'sale':
        t = replace(t, direction=TradeDirection.SELL)
    elif case == 'pending':
        t = replace(t, status=TradeStatus.O)
    elif case == 'currency':
        t = replace(t, currency='USD')
    elif case == 'missing_amount':
        t = replace(t, amount=None)
    elif case == 'unknown_security':
        t = replace(t, security_code='UNKNOWN')
    elif case == 'duplicate_trade':
        t = replace(t, trade_number=report.trades.rows[1].trade_number)
    elif case == 'totals':
        t = replace(t, amount=D(4001))
    elif case == 'quantity':
        p = replace(
            report.portfolio.rows[0],
            end_quantity=16,
            change_quantity=11,
            planned_outgoing=16,
        )
        report = replace(report, portfolio=replace(report.portfolio, rows=[p]))
    elif case == 'missing_table':
        report = replace(report, cash_flow=None)
    elif case == 'ambiguous_name':
        p = replace(report.portfolio.rows[0], isin='SECOND')
        sec = replace(report.securities.rows[0], isin='SECOND', code='SECOND')
        report = replace(
            report,
            portfolio=replace(report.portfolio, rows=[*report.portfolio.rows, p]),
            securities=replace(report.securities, rows=[*report.securities.rows, sec]),
        )
    elif case == 'bad_summary':
        assert report.cash_flow_summary is not None
        rows = report.cash_flow_summary.rows
        report = replace(
            report,
            cash_flow_summary=replace(
                report.cash_flow_summary,
                rows=[replace(rows[0], amount=D(2)), *rows[1:]],
            ),
        )
    else:
        row = report.cash_flow.rows[1]
        row = (
            replace(row, description='Unknown')
            if case == 'unknown_cash'
            else replace(row, description='Сделка от 07.01.2024')
        )
        report = replace(
            report,
            cash_flow=replace(
                report.cash_flow,
                rows=[report.cash_flow.rows[0], row, *report.cash_flow.rows[2:]],
            ),
        )
    assert report.trades is not None
    report = replace(
        report, trades=replace(report.trades, rows=[t, *report.trades.rows[1:]])
    )
    with pytest.raises(ReconciliationError):
        _ = normalize_sberbank(report)


@pytest.mark.parametrize(
    'field,value',
    [
        ('cash', D(1)),
        ('quantity', D(4)),
        ('nkd', D(0)),
        ('value', D(0)),
        ('value', D('NaN')),
    ],
)
def test_opening_state_must_be_explicit(
    statement: Statement, opening: OpeningState, field: str, value: Decimal
) -> None:
    """Never use reported market value as a fallback for missing book basis."""
    if field == 'cash':
        opening = replace(opening, cash=value)
    else:
        h = opening.holdings[0]
        if field == 'quantity':
            h = replace(h, quantity=value)
        elif field == 'nkd':
            h = replace(h, nkd=value)
        else:
            h = replace(h, value=value)
        opening = replace(opening, holdings=(h,))
    with pytest.raises(ReconciliationError):
        _ = build_journal(statement, opening)


def test_insufficient_basis(statement: Statement, opening: OpeningState) -> None:
    """A repayment cannot create negative basis or silently calculate a gain."""
    events = tuple(
        replace(e, amount=D(20000)) if e.kind == EventKind.PRINCIPAL else e
        for e in statement.events
    )
    with pytest.raises(ReconciliationError, match='sufficient recorded basis'):
        _ = build_journal(replace(statement, events=events), opening)


def test_decimal_context_is_isolated(
    statement: Statement, opening: OpeningState
) -> None:
    """A caller's low-precision Decimal context cannot round the journal."""
    with localcontext() as context:
        context.prec = 2
        journal = build_journal(statement, opening)
    assert journal.closing.cash == 14039


def test_withdrawal_is_a_transfer(statement: Statement, opening: OpeningState) -> None:
    """Withdrawal postings have the reverse transfer signs, not expense semantics."""
    events = tuple(
        replace(e, amount=D(-20000)) if e.kind == EventKind.TRANSFER else e
        for e in statement.events
    )
    journal = build_journal(
        replace(statement, events=events, closing_cash=D(-25961)), opening
    )
    transfer = journal.entries[0]
    assert transfer.postings[0].value == -20000
    assert (
        transfer.postings[1].role == Role.EXTERNAL
        and transfer.postings[1].value == 20000
    )


def test_nominal_repayment_reconciliation(report: SberbankBrokerageReport) -> None:
    """A cash credit labelled amortization must explain the change in nominal."""
    assert report.portfolio is not None
    p = replace(report.portfolio.rows[0], end_nominal=D(900))
    report = replace(report, portfolio=replace(report.portfolio, rows=[p]))
    with pytest.raises(ReconciliationError, match='principal|nominal'):
        _ = normalize_sberbank(report)


def test_full_redemption_rejected(report: SberbankBrokerageReport) -> None:
    """Zero final nominal is not treated as supported partial principal repayment."""
    assert report.portfolio is not None
    p = replace(report.portfolio.rows[0], end_nominal=D(0))
    report = replace(report, portfolio=replace(report.portfolio, rows=[p]))
    with pytest.raises(ReconciliationError, match='Full redemption'):
        _ = normalize_sberbank(report)


def test_foreign_zero_balances_are_only_informational(
    report: SberbankBrokerageReport,
) -> None:
    """An unused currency row is not an FX transaction, but nonzero holdings fail."""
    assert report.cash_balances is not None
    row = replace(
        report.cash_balances.rows[0],
        currency='USD',
        rate_end=D(80),
        start=ZERO,
        change=ZERO,
        end=ZERO,
        planned_in=ZERO,
        planned_out=ZERO,
        planned_outgoing=ZERO,
    )
    report = replace(
        report,
        cash_balances=replace(
            report.cash_balances, rows=[*report.cash_balances.rows, row]
        ),
    )
    _ = normalize_sberbank(report)
    assert report.cash_balances is not None
    report = replace(
        report,
        cash_balances=replace(
            report.cash_balances,
            rows=[report.cash_balances.rows[0], replace(row, start=D(1))],
        ),
    )
    with pytest.raises(ReconciliationError, match='foreign-currency'):
        _ = normalize_sberbank(report)


def test_duplicate_events_rejected(statement: Statement, opening: OpeningState) -> None:
    """Direct neutral-core callers receive the same identity safety checks."""
    statement = replace(statement, events=(statement.events[0], *statement.events))
    with pytest.raises(ReconciliationError, match='Duplicate event'):
        _ = build_journal(statement, opening)
