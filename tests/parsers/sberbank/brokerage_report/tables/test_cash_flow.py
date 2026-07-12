"""Tests for cash_flow table parser."""

from datetime import date
from decimal import Decimal

import pytest
from bs4 import BeautifulSoup

from finreader.parsers.sberbank.brokerage_report.tables.cash_flow import (
    CashFlow,
    CashFlowRow,
    CashFlowTotal,
    parse_cash_flow,
)
from finreader.parsers.sberbank.brokerage_report._common import parse_soup


@pytest.fixture
def soup() -> BeautifulSoup:
    """Load sample HTML."""
    return parse_soup('tests/data/sberbank_report_sample.html')


def test_parse_cash_flow_returns_data(soup: BeautifulSoup) -> None:
    """Test that parse_cash_flow returns CashFlow with correct data."""
    result = parse_cash_flow(soup)

    assert result is not None
    assert isinstance(result, CashFlow)
    assert len(result.rows) == 23

    # Check first row
    first_row = result.rows[0]
    assert isinstance(first_row, CashFlowRow)
    assert first_row.date == date(2024, 1, 7)
    assert first_row.venue == 'Основной рынок'
    assert first_row.description == 'Зачисление д/с'
    assert first_row.currency == 'RUB'
    assert first_row.credit == Decimal('47523.18')
    assert first_row.debit == Decimal('0.00')

    # Check a debit row (row with trade)
    trade_row = result.rows[1]
    assert trade_row.date == date(2024, 1, 9)
    assert trade_row.description == 'Сделка от 08.01.2024'
    assert trade_row.credit == Decimal('0.00')
    assert trade_row.debit == Decimal('148410.60')


def test_parse_cash_flow_returns_none_if_table_missing() -> None:
    """Test that parse_cash_flow returns None when table is not found."""
    # This test is a bit tricky since we can't easily remove the table from the soup.
    # For now, we'll just test with a completely different HTML.
    from bs4 import BeautifulSoup

    empty_soup = BeautifulSoup('<html><body><p>No table here</p></body></html>', 'lxml')
    result = parse_cash_flow(empty_soup)
    assert result is None


def test_parse_cash_flow_total(soup: BeautifulSoup) -> None:
    """Test that parse_cash_flow parses the total row correctly."""
    result = parse_cash_flow(soup)

    assert result is not None
    assert result.total is not None
    assert isinstance(result.total, CashFlowTotal)
    assert result.total.label == 'Итого, RUB'
    assert result.total.credit == Decimal('368871.04')
    assert result.total.debit == Decimal('313039.43')


def test_date_column_is_date_type_not_str(soup: BeautifulSoup) -> None:
    """Regression guard: ensure date column returns date objects, not strings."""
    result = parse_cash_flow(soup)

    assert result is not None
    for row in result.rows:
        assert isinstance(row.date, date), (
            f'Expected date, got {type(row.date)} for row: {row}'
        )


def test_credit_debit_always_populated_not_none(soup: BeautifulSoup) -> None:
    """Test that credit/debit fields are always Decimal (never None) for populated cells."""
    result = parse_cash_flow(soup)

    assert result is not None
    for row in result.rows:
        # In this table, credit/debit are always populated (even 0.00)
        assert row.credit is not None, f'credit is None for row: {row}'
        assert row.debit is not None, f'debit is None for row: {row}'
        assert isinstance(row.credit, Decimal), (
            f'Expected Decimal, got {type(row.credit)} for credit'
        )
        assert isinstance(row.debit, Decimal), (
            f'Expected Decimal, got {type(row.debit)} for debit'
        )


def test_all_dataclasses_are_frozen(soup: BeautifulSoup) -> None:
    """Test that all dataclasses are frozen (immutable)."""
    from dataclasses import FrozenInstanceError

    result = parse_cash_flow(soup)

    assert result is not None

    # Check CashFlow is frozen (cannot assign to fields)
    with pytest.raises(FrozenInstanceError):
        setattr(result, 'rows', [])

    # Check CashFlowRow is frozen (cannot assign to fields)
    first_row = result.rows[0]
    with pytest.raises(FrozenInstanceError):
        setattr(first_row, 'venue', 'modified')

    # Check CashFlowTotal is frozen (cannot assign to fields)
    if result.total:
        with pytest.raises(FrozenInstanceError):
            setattr(result.total, 'label', 'modified')


def test_parse_cash_flow_all_dates_in_range(soup: BeautifulSoup) -> None:
    """Test that all dates fall within expected range (Jan 7-29, 2024)."""
    result = parse_cash_flow(soup)

    assert result is not None
    dates = [row.date for row in result.rows]

    min_date = min(dates)
    max_date = max(dates)

    assert min_date == date(2024, 1, 7)
    assert max_date == date(2024, 1, 29)


def test_parse_cash_flow_all_venues_are_main_market(soup: BeautifulSoup) -> None:
    """Test that all venues in sample are 'Основной рынок'."""
    result = parse_cash_flow(soup)

    assert result is not None
    for row in result.rows:
        assert row.venue == 'Основной рынок'


def test_parse_cash_flow_all_currencies_are_rub(soup: BeautifulSoup) -> None:
    """Test that all currencies in sample are 'RUB'."""
    result = parse_cash_flow(soup)

    assert result is not None
    for row in result.rows:
        assert row.currency == 'RUB'
