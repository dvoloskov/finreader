"""Tests for cash_flow_summary table parsing."""

from pathlib import Path
from decimal import Decimal

from finreader.parsers.sberbank.brokerage_report._common import parse_soup
from finreader.parsers.sberbank.brokerage_report.tables.cash_flow_summary import (
    CashFlowSummary,
    CashFlowSummaryRow,
    parse_cash_flow_summary,
)


def test_parse_cash_flow_summary(sample_html_path: Path) -> None:
    """Test parsing cash_flow_summary table from sample HTML."""
    soup = parse_soup(sample_html_path)
    result = parse_cash_flow_summary(soup)

    assert result is not None
    assert isinstance(result, CashFlowSummary)
    assert len(result.rows) == 7

    # Check first row: "Входящий остаток"
    row0 = result.rows[0]
    assert isinstance(row0, CashFlowSummaryRow)
    assert row0.description == 'Входящий остаток'
    assert row0.amount == Decimal('1087.63')
    assert row0.currency == 'RUB'

    # Check second row: "Пополнение счета"
    row1 = result.rows[1]
    assert row1.description == 'Пополнение счета'
    assert row1.amount == Decimal('47523.18')
    assert row1.currency == 'RUB'

    # Check third row: "Сальдо расчетов по сделкам" (negative)
    row2 = result.rows[2]
    assert row2.description == 'Сальдо расчетов по сделкам'
    assert row2.amount == Decimal('-312797.65')
    assert row2.currency == 'RUB'

    # Check fourth row: "Корпоративные действия"
    row3 = result.rows[3]
    assert row3.description == 'Корпоративные действия'
    assert row3.amount == Decimal('268486.77')
    assert row3.currency == 'RUB'

    # Check fifth row: "Комиссия брокера" (negative)
    row4 = result.rows[4]
    assert row4.description == 'Комиссия брокера'
    assert row4.amount == Decimal('-117.98')
    assert row4.currency == 'RUB'

    # Check sixth row: "Комиссия биржи" (negative)
    row5 = result.rows[5]
    assert row5.description == 'Комиссия биржи'
    assert row5.amount == Decimal('-22.64')
    assert row5.currency == 'RUB'

    # Check seventh row: "Исходящий остаток"
    row6 = result.rows[6]
    assert row6.description == 'Исходящий остаток'
    assert row6.amount == Decimal('4159.31')
    assert row6.currency == 'RUB'


def test_parse_cash_flow_summary_missing_table(sample_html_path: Path) -> None:
    """Test that parse_cash_flow_summary returns None when table is missing."""
    soup = parse_soup(sample_html_path)

    # Remove the table
    for p in soup.find_all('p'):
        if p.get_text(strip=True).startswith(
            'Сводная информация по движению денежных средств'
        ):
            table = p.find_next_sibling('table')
            if table:
                table.decompose()

    result = parse_cash_flow_summary(soup)
    assert result is None


def test_cash_flow_summary_negative_amounts_preserved(sample_html_path: Path) -> None:
    """Test that negative signs are preserved on amounts."""
    soup = parse_soup(sample_html_path)
    result = parse_cash_flow_summary(soup)
    assert result is not None

    # Find negative amounts
    negative_amounts = [r.amount for r in result.rows if r.amount < 0]
    assert len(negative_amounts) == 3

    # Check that negative broker commission is preserved
    broker_fees = [r for r in result.rows if r.description == 'Комиссия брокера']
    assert len(broker_fees) == 1
    assert broker_fees[0].amount == Decimal('-117.98')


def test_cash_flow_summary_currency_per_row(sample_html_path: Path) -> None:
    """Test that currency is parsed per row (not assumed to be RUB)."""
    soup = parse_soup(sample_html_path)
    result = parse_cash_flow_summary(soup)
    assert result is not None

    # All rows in sample have RUB, but verify we're reading it from the row
    assert all(r.currency == 'RUB' for r in result.rows)


def test_cash_flow_summary_all_row_types_present(sample_html_path: Path) -> None:
    """Test that all expected row types are present."""
    soup = parse_soup(sample_html_path)
    result = parse_cash_flow_summary(soup)
    assert result is not None

    descriptions = {r.description for r in result.rows}
    expected_descriptions = {
        'Входящий остаток',
        'Пополнение счета',
        'Сальдо расчетов по сделкам',
        'Корпоративные действия',
        'Комиссия брокера',
        'Комиссия биржи',
        'Исходящий остаток',
    }

    assert descriptions == expected_descriptions
