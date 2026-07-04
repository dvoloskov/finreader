"""Tests for _common.py helper functions."""

from datetime import date, time
from decimal import Decimal

from bs4 import BeautifulSoup


def test_parse_money_strips_nbsp_and_leading_plus() -> None:
    """Test parse_money strips U+00A0 thousands separator and leading +."""
    from finreader.parsers.sberbank.brokerage_report._common import parse_money

    # Leading + should be stripped
    assert parse_money('+87 511.35') == Decimal('87511.35')

    # U+00A0 (nbsp) should be stripped (comma replaced with period for Decimal)
    assert parse_money('1\xa0234,56'.replace(',', '.')) == Decimal('1234.56')

    # Regular spaces should be stripped
    assert parse_money('1 234.56') == Decimal('1234.56')

    # Negative sign preserved
    assert parse_money('-123.45') == Decimal('-123.45')

    # Empty returns None
    assert parse_money('') is None

    # None returns None
    assert parse_money(None) is None

    # nbsp-only returns None
    assert parse_money('\xa0') is None


def test_parse_int_strips_whitespace_and_nbsp() -> None:
    """Test parse_int strips whitespace and nbsp."""
    from finreader.parsers.sberbank.brokerage_report._common import parse_int

    assert parse_int('123') == 123
    assert parse_int(' 123 ') == 123
    assert parse_int('1\xa0234') == 1234
    assert parse_int('') is None
    assert parse_int(None) is None
    assert parse_int('\xa0') is None


def test_parse_date_dayfirst() -> None:
    """Test parse_date with dayfirst=True."""
    from finreader.parsers.sberbank.brokerage_report._common import parse_date

    assert parse_date('01.02.2024') == date(2024, 2, 1)
    assert parse_date('31.12.2024') == date(2024, 12, 31)
    assert parse_date('') is None
    assert parse_date(None) is None


def test_parse_time() -> None:
    """Test parse_time."""
    from finreader.parsers.sberbank.brokerage_report._common import parse_time

    assert parse_time('12:34:56') == time(12, 34, 56)
    assert parse_time('00:00:00') == time(0, 0, 0)
    assert parse_time('') is None
    assert parse_time(None) is None


def test_cell_text_normalizes_nbsp() -> None:
    """Test cell_text normalizes nbsp and strips whitespace."""
    from finreader.parsers.sberbank.brokerage_report._common import cell_text

    html = '<td>Иванов&nbsp;И.И.</td>'
    soup = BeautifulSoup(html, 'lxml')
    td = soup.find('td')
    assert cell_text(td) == 'Иванов И.И.'

    html2 = '<td>  text  </td>'
    soup2 = BeautifulSoup(html2, 'lxml')
    td2 = soup2.find('td')
    assert cell_text(td2) == 'text'


def test_find_table_by_title_document_order() -> None:
    """Test find_table_by_title pairs <p> title with correct <table> in document order."""
    from finreader.parsers.sberbank.brokerage_report._common import find_table_by_title

    html = """
    <html><body>
        <p>First Table</p>
        <table id="table1"><tr><td>data1</td></tr></table>
        <p>Second Table</p>
        <table id="table2"><tr><td>data2</td></tr></table>
        <p>Third Table</p>
        <table id="table3"><tr><td>data3</td></tr></table>
    </body></html>
    """
    soup = BeautifulSoup(html, 'lxml')

    # Should find the second table when searching for "Second"
    table = find_table_by_title(soup, 'Second')
    assert table is not None
    assert table.get('id') == 'table2'

    # Should return None for non-existent title
    assert find_table_by_title(soup, 'Nonexistent') is None


def test_iter_data_rows_skips_special_rows() -> None:
    """Test iter_data_rows skips row-number, summary, and section rows."""
    from finreader.parsers.sberbank.brokerage_report._common import (
        iter_data_rows,
        iter_section_rows,
    )

    html = """
    <table>
        <tr class="rn"><td>1</td><td>A</td></tr>
        <tr><td>data1</td><td>B</td></tr>
        <tr class="summary-row"><td>Итого</td><td>100</td></tr>
        <tr><td colspan="2">Площадка: Фондовый рынок</td></tr>
        <tr><td>data2</td><td>C</td></tr>
    </table>
    """
    soup = BeautifulSoup(html, 'lxml')
    table = soup.find('table')

    # iter_data_rows should only yield data rows
    data_rows = list(iter_data_rows(table))
    assert len(data_rows) == 2
    assert data_rows[0] == ['data1', 'B']
    assert data_rows[1] == ['data2', 'C']

    # iter_section_rows should yield the section row
    section_rows = list(iter_section_rows(table))
    assert len(section_rows) == 1
    assert 'Площадка:' in section_rows[0]


def test_parse_soup() -> None:
    """Test parse_soup opens file and parses with lxml."""
    from pathlib import Path
    from finreader.parsers.sberbank.brokerage_report._common import parse_soup

    # Use the sample HTML file
    soup = parse_soup(Path('tests/data/sberbank_report_sample.html'))
    assert isinstance(soup, BeautifulSoup)
    assert soup.find('h3') is not None
