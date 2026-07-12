"""Tests for asset_valuation table parsing."""

from pathlib import Path
from decimal import Decimal

from finreader.parsers.sberbank.brokerage_report._common import parse_soup
from finreader.parsers.sberbank.brokerage_report.tables.asset_valuation import (
    AssetValuation,
    AssetValuationRow,
    AssetValuationTotals,
    parse_asset_valuation,
)


def test_parse_asset_valuation(sample_html_path: Path) -> None:
    """Test parsing asset_valuation table from sample HTML."""
    soup = parse_soup(sample_html_path)
    result = parse_asset_valuation(soup)

    assert result is not None
    assert isinstance(result, AssetValuation)
    assert len(result.rows) == 1

    # Check the only data row
    row = result.rows[0]
    assert isinstance(row, AssetValuationRow)
    assert row.venue == 'Основной рынок'

    # Start period values
    assert row.start_securities == Decimal('98734.52')
    assert row.start_cash == Decimal('1087.63')
    assert row.start_total == Decimal('99822.15')

    # End period values
    assert row.end_securities == Decimal('186245.87')
    assert row.end_cash == Decimal('4159.31')
    assert row.end_total == Decimal('190405.18')

    # Change values (note: change values have leading + in HTML)
    assert row.change_securities == Decimal('87511.35')
    assert row.change_cash == Decimal('3071.68')
    assert row.change_total == Decimal('90583.03')


def test_parse_asset_valuation_totals(sample_html_path: Path) -> None:
    """Test that Итого summary row is captured as totals."""
    soup = parse_soup(sample_html_path)
    result = parse_asset_valuation(soup)

    assert result is not None
    assert result.total is not None
    assert isinstance(result.total, AssetValuationTotals)

    # Totals should match the summed values from the data row
    assert result.total.start_total == Decimal('99822.15')
    assert result.total.end_total == Decimal('190405.18')
    assert result.total.change_total == Decimal('90583.03')


def test_parse_asset_valuation_missing_table(sample_html_path: Path) -> None:
    """Test that parse_asset_valuation returns None when table is missing."""
    soup = parse_soup(sample_html_path)

    # Remove the table
    for p in soup.find_all('p'):
        if p.get_text(strip=True).startswith('Оценка активов, руб.'):
            table = p.find_next_sibling('table')
            if table:
                table.decompose()

    result = parse_asset_valuation(soup)
    assert result is None


def test_parse_asset_valuation_change_values_signed(sample_html_path: Path) -> None:
    """Test that change values handle leading + signs correctly."""
    soup = parse_soup(sample_html_path)
    result = parse_asset_valuation(soup)

    assert result is not None
    row = result.rows[0]

    # All change values should be positive (they have leading + in HTML)
    assert row.change_securities > 0
    assert row.change_cash > 0
    assert row.change_total > 0


def test_parse_asset_valuation_two_row_header_structure(sample_html_path: Path) -> None:
    """Test that the 2-row header is correctly handled (9 numeric sub-columns)."""
    soup = parse_soup(sample_html_path)
    result = parse_asset_valuation(soup)

    assert result is not None
    row = result.rows[0]

    # Verify we have 9 numeric fields (3 periods × 3 measures)
    numeric_fields = [
        row.start_securities,
        row.start_cash,
        row.start_total,
        row.end_securities,
        row.end_cash,
        row.end_total,
        row.change_securities,
        row.change_cash,
        row.change_total,
    ]

    # All should be Decimal instances
    assert all(isinstance(f, Decimal) for f in numeric_fields)

    # Verify the structure: start + cash = total, end + cash = total, change + cash = total
    assert row.start_securities + row.start_cash == row.start_total
    assert row.end_securities + row.end_cash == row.end_total
    assert row.change_securities + row.change_cash == row.change_total


def test_parse_asset_valuation_none_when_table_absent() -> None:
    """Test that parse_asset_valuation returns None when table is completely absent."""
    html = '<html><body><p>Some other table</p><table><tr><td>data</td></tr></table></body></html>'
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, 'lxml')
    result = parse_asset_valuation(soup)
    assert result is None
