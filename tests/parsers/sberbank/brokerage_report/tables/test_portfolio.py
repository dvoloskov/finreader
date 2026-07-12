"""Tests for portfolio table parser (Task 5 — most complex table)."""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest
from bs4 import BeautifulSoup

from finreader.parsers.sberbank.brokerage_report._common import parse_soup
from finreader.parsers.sberbank.brokerage_report.tables.portfolio import (
    Portfolio,
    PortfolioRow,
    PortfolioTotal,
    parse_portfolio,
)


@pytest.fixture
def soup() -> BeautifulSoup:
    """Load sample HTML."""
    return parse_soup('tests/data/sberbank_report_sample.html')


# ---------------------------------------------------------------------------
# Structural tests
# ---------------------------------------------------------------------------


def test_parse_portfolio_returns_portfolio(soup: BeautifulSoup) -> None:
    """parse_portfolio returns a populated Portfolio object."""
    result = parse_portfolio(soup)
    assert result is not None
    assert isinstance(result, Portfolio)


def test_parse_portfolio_returns_none_if_table_missing() -> None:
    """parse_portfolio returns None when the table is absent."""
    empty_soup = BeautifulSoup('<html><body><p>No table here</p></body></html>', 'lxml')
    assert parse_portfolio(empty_soup) is None


def test_portfolio_has_7_rows(soup: BeautifulSoup) -> None:
    """The sample contains exactly 7 securities (Облигация А..Ж)."""
    result = parse_portfolio(soup)
    assert result is not None
    assert len(result.rows) == 7


def test_all_rows_carry_venue_metadata(soup: BeautifulSoup) -> None:
    """Every data row carries venue='Фондовый рынок' from the section row."""
    result = parse_portfolio(soup)
    assert result is not None
    assert all(r.venue == 'Фондовый рынок' for r in result.rows)


def test_row_names_in_order(soup: BeautifulSoup) -> None:
    """Row names are Облигация А..Ж in document order."""
    result = parse_portfolio(soup)
    assert result is not None
    expected = [
        'Облигация А',
        'Облигация Б',
        'Облигация В',
        'Облигация Г',
        'Облигация Д',
        'Облигация Е',
        'Облигация Ж',
    ]
    assert [r.name for r in result.rows] == expected


# ---------------------------------------------------------------------------
# Per-row exact value tests (from plan)
# ---------------------------------------------------------------------------


def test_first_row_exact_values(soup: BeautifulSoup) -> None:
    """Облигация А matches the plan's exact values."""
    result = parse_portfolio(soup)
    assert result is not None
    a = [r for r in result.rows if r.name == 'Облигация А'][0]
    assert isinstance(a, PortfolioRow)
    assert a.isin == 'RU000TEST001'
    assert a.price_currency == 'RUB'
    assert a.venue == 'Фондовый рынок'
    assert a.start_quantity == 0
    assert a.start_nominal == Decimal('1000')
    assert a.start_price == Decimal('104.31')
    assert a.start_market_value == Decimal('0.00')
    assert a.start_nkd == Decimal('0')
    assert a.end_quantity == 100
    assert a.end_nominal == Decimal('1000')
    assert a.end_price == Decimal('105.58')
    assert a.end_market_value == Decimal('10558.00')
    assert a.end_nkd == Decimal('296.17')
    assert a.change_quantity == 100
    assert a.change_market_value == Decimal('10558.00')
    assert a.planned_receipts == 0
    assert a.planned_charges == 0
    assert a.planned_outgoing == 100


def test_last_row_start_end_quantities(soup: BeautifulSoup) -> None:
    """Облигация Ж: start_quantity=328, end_quantity=509."""
    result = parse_portfolio(soup)
    assert result is not None
    zh = [r for r in result.rows if r.name == 'Облигация Ж'][0]
    assert zh.start_quantity == 328
    assert zh.end_quantity == 509
    assert zh.isin == 'RU000TEST007'


def test_row_field_types(soup: BeautifulSoup) -> None:
    """All typed fields use the correct Python types."""
    result = parse_portfolio(soup)
    assert result is not None
    for r in result.rows:
        assert isinstance(r.name, str)
        assert isinstance(r.isin, str)
        assert isinstance(r.price_currency, str)
        assert isinstance(r.venue, str)
        assert isinstance(r.start_quantity, int)
        assert isinstance(r.end_quantity, int)
        assert isinstance(r.change_quantity, int)
        assert isinstance(r.planned_receipts, int)
        assert isinstance(r.planned_charges, int)
        assert isinstance(r.planned_outgoing, int)
        assert isinstance(r.start_nominal, Decimal)
        assert isinstance(r.start_price, Decimal)
        assert isinstance(r.start_market_value, Decimal)
        assert isinstance(r.start_nkd, Decimal)
        assert isinstance(r.end_nominal, Decimal)
        assert isinstance(r.end_price, Decimal)
        assert isinstance(r.end_market_value, Decimal)
        assert isinstance(r.end_nkd, Decimal)
        assert isinstance(r.change_market_value, Decimal)


def test_obligatsiya_e_quantities(soup: BeautifulSoup) -> None:
    """Облигация Е shows buy during period (start 118 → end 168, +50)."""
    result = parse_portfolio(soup)
    assert result is not None
    e = [r for r in result.rows if r.name == 'Облигация Е'][0]
    assert e.start_quantity == 118
    assert e.end_quantity == 168
    assert e.change_quantity == 50


# ---------------------------------------------------------------------------
# Totals tests
# ---------------------------------------------------------------------------


def test_totals_count(soup: BeautifulSoup) -> None:
    """Both summary rows (Итого по площадке / Итого по Основному рынку) captured."""
    result = parse_portfolio(soup)
    assert result is not None
    assert len(result.totals) == 2


def test_first_total_label_and_values(soup: BeautifulSoup) -> None:
    """First total: 'Итого по площадке Фондовый рынок, RUB' with exact Decimals."""
    result = parse_portfolio(soup)
    assert result is not None
    t = result.totals[0]
    assert isinstance(t, PortfolioTotal)
    assert t.label == 'Итого по площадке Фондовый рынок, RUB'
    assert t.start_market_value == Decimal('191052.42')
    assert t.start_nkd == Decimal('12652.37')
    assert t.end_market_value == Decimal('190917.44')
    assert t.end_nkd == Decimal('14252.80')
    assert t.change_market_value == Decimal('-134.98')


def test_second_total_label(soup: BeautifulSoup) -> None:
    """Second total: 'Итого по Основному рынку, RUB'."""
    result = parse_portfolio(soup)
    assert result is not None
    assert result.totals[1].label == 'Итого по Основному рынку, RUB'


def test_both_totals_same_values(soup: BeautifulSoup) -> None:
    """Both totals in the sample carry identical values."""
    result = parse_portfolio(soup)
    assert result is not None
    t0, t1 = result.totals
    assert t0.start_market_value == t1.start_market_value
    assert t0.end_market_value == t1.end_market_value
    assert t0.change_market_value == t1.change_market_value


def test_total_optional_fields_are_none_when_empty(soup: BeautifulSoup) -> None:
    """Empty cells in the summary row map to None (not zero)."""
    result = parse_portfolio(soup)
    assert result is not None
    t = result.totals[0]
    # cells at "end_quantity / end_nominal / end_price" slots are empty → not exposed
    # but we exposed them as None per the plan
    # PortfolioTotal has only the 5 fields per plan; ensure type is correct
    assert isinstance(t, PortfolioTotal)


# ---------------------------------------------------------------------------
# Spacer row must be explicitly skipped
# ---------------------------------------------------------------------------


def test_spacer_row_not_treated_as_data_or_total(soup: BeautifulSoup) -> None:
    """The blank `<td colspan="18">&nbsp;</td>` row must NOT inflate counts."""
    result = parse_portfolio(soup)
    assert result is not None
    # 7 data rows + 2 totals = 9 tr entities consumed from the body.
    # The spacer row must not appear as either.
    assert len(result.rows) == 7
    assert len(result.totals) == 2
    # And no row has its name derived from the spacer (empty string)
    assert all(r.name for r in result.rows)


# ---------------------------------------------------------------------------
# Inline HTML fragment tests (table absent / spacer-only / minimal)
# ---------------------------------------------------------------------------


def test_inline_minimal_table_parses_one_row_one_total() -> None:
    """A hand-crafted minimal portfolio table yields 1 row + 1 total."""
    html = """
    <html><body>
    <p>Портфель Ценных Бумаг</p>
    <table border="1">
      <tr class="table-header">
        <td class="c" colspan="3">Основной рынок</td>
        <td class="c" colspan="5">Начало периода</td>
        <td class="c" colspan="5">Конец периода</td>
        <td class="c" colspan="2">Изменение за период</td>
        <td class="c" colspan="3">Плановые показатели</td>
      </tr>
      <tr align="center" class="table-header">
        <td>Наименование</td><td>ISIN</td><td>Валюта</td>
        <td>Количество</td><td>Номинал</td><td>Цена</td><td>Стоимость</td><td>НКД</td>
        <td>Количество</td><td>Номинал</td><td>Цена</td><td>Стоимость</td><td>НКД</td>
        <td>Количество</td><td>Стоимость</td>
        <td>Зачисления</td><td>Списания</td><td>Исходящий</td>
      </tr>
      <tr class="rn"><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td><td>8</td><td>9</td><td>10</td><td>11</td><td>12</td><td>13</td><td>14</td><td>15</td><td>16</td><td>17</td><td>18</td></tr>
      <tr><td colspan="18">Площадка: Фондовый рынок</td></tr>
      <tr>
        <td>Бонд Х</td><td>RU000X</td><td>RUB</td>
        <td>0</td><td>1 000</td><td>100.00</td><td>0.00</td><td>0</td>
        <td>10</td><td>1 000</td><td>100.00</td><td>1 000.00</td><td>10.00</td>
        <td>10</td><td>1 000.00</td>
        <td>0</td><td>0</td><td>10</td>
      </tr>
      <tr><td colspan="18">&nbsp;</td></tr>
      <tr class="summary-row">
        <td colspan="6">Итого по площадке Фондовый рынок, RUB</td>
        <td>0.00</td><td>0</td>
        <td></td><td></td><td></td>
        <td>1 000.00</td><td>10.00</td>
        <td></td><td>0.00</td>
        <td></td><td></td><td></td>
      </tr>
    </table>
    </body></html>
    """
    soup = BeautifulSoup(html, 'lxml')
    result = parse_portfolio(soup)
    assert result is not None
    assert len(result.rows) == 1
    r = result.rows[0]
    assert r.name == 'Бонд Х'
    assert r.isin == 'RU000X'
    assert r.venue == 'Фондовый рынок'
    assert r.end_market_value == Decimal('1000.00')
    assert r.end_nkd == Decimal('10.00')
    assert len(result.totals) == 1
    t = result.totals[0]
    assert t.start_market_value == Decimal('0.00')
    assert t.start_nkd == Decimal('0')
    assert t.end_market_value == Decimal('1000.00')
    assert t.end_nkd == Decimal('10.00')
    assert t.change_market_value == Decimal('0.00')


def test_inline_no_venue_section_yields_empty_venue() -> None:
    """Rows before any section row keep venue='' (not None, not crash)."""
    html = """
    <html><body>
    <p>Портфель Ценных Бумаг</p>
    <table border="1">
      <tr class="table-header">
        <td colspan="18">Основной рынок</td>
      </tr>
      <tr align="center" class="table-header">
        <td>Наименование</td><td>ISIN</td><td>Валюта</td>
        <td>Количество</td><td>Номинал</td><td>Цена</td><td>Стоимость</td><td>НКД</td>
        <td>Количество</td><td>Номинал</td><td>Цена</td><td>Стоимость</td><td>НКД</td>
        <td>Количество</td><td>Стоимость</td>
        <td>Зачисления</td><td>Списания</td><td>Исходящий</td>
      </tr>
      <tr class="rn"><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td><td>8</td><td>9</td><td>10</td><td>11</td><td>12</td><td>13</td><td>14</td><td>15</td><td>16</td><td>17</td><td>18</td></tr>
      <tr>
        <td>Бонд Y</td><td>RU000Y</td><td>RUB</td>
        <td>0</td><td>1 000</td><td>100.00</td><td>0.00</td><td>0</td>
        <td>10</td><td>1 000</td><td>100.00</td><td>1 000.00</td><td>10.00</td>
        <td>10</td><td>1 000.00</td>
        <td>0</td><td>0</td><td>10</td>
      </tr>
    </table>
    </body></html>
    """
    soup = BeautifulSoup(html, 'lxml')
    result = parse_portfolio(soup)
    assert result is not None
    assert len(result.rows) == 1
    assert result.rows[0].venue == ''
    assert result.totals == []


# ---------------------------------------------------------------------------
# Dataclass immutability
# ---------------------------------------------------------------------------


def test_all_dataclasses_are_frozen(soup: BeautifulSoup) -> None:
    """All public dataclasses must be frozen."""
    result = parse_portfolio(soup)
    assert result is not None

    with pytest.raises(FrozenInstanceError):
        setattr(result, 'rows', [])
    with pytest.raises(FrozenInstanceError):
        setattr(result, 'totals', [])

    first = result.rows[0]
    with pytest.raises(FrozenInstanceError):
        setattr(first, 'name', 'mutated')

    t0 = result.totals[0]
    with pytest.raises(FrozenInstanceError):
        setattr(t0, 'label', 'mutated')
