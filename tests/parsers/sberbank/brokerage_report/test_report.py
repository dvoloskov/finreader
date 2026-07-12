"""
End-to-end tests for the top-level ``parse()`` entry point.

These tests exercise the full integration of all 11 modules (header + 10
tables) against the anonymised sample report. Spot-checks assert concrete
cross-table values to catch regressions in any of the underlying parsers.
"""

from datetime import date
from decimal import Decimal

import pytest

from finreader.parsers.sberbank.brokerage_report import (
    SberbankBrokerageReport,
    parse,
)

SAMPLE_PATH = 'tests/data/sberbank_report_sample.html'

ALL_TABLE_ATTRS = (
    'asset_valuation',
    'cash_flow_summary',
    'portfolio',
    'cash_balances',
    'cash_flow',
    'trades',
    'income_expenses',
    'income_expenses_consolidated',
    'income_expenses_tax_summary',
    'securities',
)


@pytest.fixture(scope='module')
def report() -> SberbankBrokerageReport:
    """Parse the sample report once for the whole module."""
    return parse(SAMPLE_PATH)


def test_parse_returns_sberbank_brokerage_report(
    report: SberbankBrokerageReport,
) -> None:
    """parse() returns a SberbankBrokerageReport instance."""
    assert isinstance(report, SberbankBrokerageReport)


def test_header_contract_code(report: SberbankBrokerageReport) -> None:
    """Header carries the expected contract code from the sample."""
    assert report.header.contract_code == 'TEST001'
    assert report.header.investor == 'Иванов Иван Иванович'
    assert report.header.start_date == date(2024, 1, 1)
    assert report.header.end_date == date(2024, 1, 31)


def test_all_ten_tables_present(report: SberbankBrokerageReport) -> None:
    """Every Optional table field is populated for the sample."""
    missing = [attr for attr in ALL_TABLE_ATTRS if getattr(report, attr) is None]
    assert missing == [], f'missing tables: {missing}'


def test_trades_row_count(report: SberbankBrokerageReport) -> None:
    """Trades table has 10 rows in the sample."""
    assert report.trades is not None
    assert len(report.trades.rows) == 10


def test_securities_row_count(report: SberbankBrokerageReport) -> None:
    """Securities table has 7 rows in the sample."""
    assert report.securities is not None
    assert len(report.securities.rows) == 7


def test_cash_balances_rub_end(report: SberbankBrokerageReport) -> None:
    """Spot-check cash_balances RUB end balance."""
    assert report.cash_balances is not None
    assert report.cash_balances.rows[0].end == Decimal('4159.31')


def test_portfolio_spot_check(report: SberbankBrokerageReport) -> None:
    """Spot-check portfolio: Облигация А end quantity/market value."""
    assert report.portfolio is not None
    bond_a = [r for r in report.portfolio.rows if r.name == 'Облигация А'][0]
    assert bond_a.isin == 'RU000TEST001'
    assert bond_a.venue == 'Фондовый рынок'
    assert bond_a.end_quantity == 100
    assert bond_a.end_market_value == Decimal('10558.00')


def test_trades_total(report: SberbankBrokerageReport) -> None:
    """Spot-check trades total amount."""
    assert report.trades is not None
    assert report.trades.total is not None
    assert report.trades.total.amount == Decimal('312797.65')


def test_cash_flow_row_count_and_total(report: SberbankBrokerageReport) -> None:
    """Spot-check cash_flow: 23 rows, dates are date objects, total correct."""
    assert report.cash_flow is not None
    assert len(report.cash_flow.rows) == 23
    assert isinstance(report.cash_flow.rows[0].date, date)
    assert report.cash_flow.rows[0].date == date(2024, 1, 7)
    assert report.cash_flow.total is not None
    assert report.cash_flow.total.credit == Decimal('368871.04')
    assert report.cash_flow.total.debit == Decimal('313039.43')


def test_report_is_frozen(report: SberbankBrokerageReport) -> None:
    """SberbankBrokerageReport is immutable."""
    with pytest.raises(Exception):  # FrozenInstanceError
        setattr(report, 'header', report.header)


def test_parse_accepts_path_object() -> None:
    """parse() accepts a pathlib.Path as well as a str."""
    from pathlib import Path

    r = parse(Path(SAMPLE_PATH))
    assert r.header.contract_code == 'TEST001'
