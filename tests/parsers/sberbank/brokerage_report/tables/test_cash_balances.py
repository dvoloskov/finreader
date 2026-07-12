"""Tests for cash_balances table parser."""

from decimal import Decimal


from finreader.parsers.sberbank.brokerage_report._common import parse_soup
from finreader.parsers.sberbank.brokerage_report.tables.cash_balances import (
    parse_cash_balances,
)


def test_parse_cash_balances_three_currencies_and_two_totals() -> None:
    """Test parsing 3 currency rows (RUB, EUR, USD) + 2 totals."""
    soup = parse_soup('tests/data/sberbank_report_sample.html')
    cb = parse_cash_balances(soup)

    assert cb is not None
    assert len(cb.rows) == 3
    assert {r.currency for r in cb.rows} == {'RUB', 'EUR', 'USD'}

    # RUB row: no rate (empty cell)
    rub = [r for r in cb.rows if r.currency == 'RUB'][0]
    assert rub.venue == 'Торговый счет,  Основной рынок'
    assert rub.rate_end is None
    assert rub.start == Decimal('1087.63')
    assert rub.change == Decimal('3071.68')
    assert rub.end == Decimal('4159.31')
    assert rub.planned_in == Decimal('0.00')
    assert rub.planned_out == Decimal('0.00')
    assert rub.planned_outgoing == Decimal('4159.31')

    # USD row: has rate
    usd = [r for r in cb.rows if r.currency == 'USD'][0]
    assert usd.venue == 'Торговый счет,  Основной рынок'
    assert usd.rate_end == Decimal('81.3508')
    assert usd.start == Decimal('0.00')
    assert usd.end == Decimal('0.00')

    # EUR row: has rate
    eur = [r for r in cb.rows if r.currency == 'EUR'][0]
    assert eur.venue == 'Торговый счет,  Основной рынок'
    assert eur.rate_end == Decimal('93.4827')
    assert eur.start == Decimal('0.00')
    assert eur.end == Decimal('0.00')

    # 2 totals: venue total + ruble total
    assert len(cb.totals) == 2
    assert cb.totals[0].label == 'Итого по площадке Основной рынок'
    assert cb.totals[0].start == Decimal('1087.63')
    assert cb.totals[0].change == Decimal('3071.68')
    assert cb.totals[0].end == Decimal('4159.31')
    assert cb.totals[1].label == 'Итого в рублевой оценке по курсам Банка России'
    assert cb.totals[1].end == Decimal('4159.31')


def test_parse_cash_balances_returns_none_when_table_absent() -> None:
    """Test that None is returned when the table is not found."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup('<p>Some other content</p>', 'lxml')
    assert parse_cash_balances(soup) is None
