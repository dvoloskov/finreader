"""Tests for income_expenses table parsing (Table I)."""

from pathlib import Path
from decimal import Decimal


from finreader.parsers.sberbank.brokerage_report._common import parse_soup
from finreader.parsers.sberbank.brokerage_report.tables.income_expenses import (
    IncomeExpenses,
    parse_income_expenses,
)


def test_parse_income_expenses_two_rows(sample_html_path: Path) -> None:
    """Test parsing income_expenses table from sample HTML with 2 rows."""
    soup = parse_soup(sample_html_path)
    result = parse_income_expenses(soup)

    assert result is not None
    assert isinstance(result, IncomeExpenses)
    assert len(result.rows) == 2


def test_parse_income_expenses_row1_values(sample_html_path: Path) -> None:
    """Test first row values: TEST002 contract with all fields."""
    soup = parse_soup(sample_html_path)
    result = parse_income_expenses(soup)

    assert result is not None
    row = result.rows[0]

    assert row.contract_code == 'TEST002'
    assert row.income_code == '1530'
    assert row.income_amount == Decimal('12453.87')
    assert row.taxable_amount == Decimal('3891.52')
    assert row.expense_code == '201'
    assert row.expense_amount == Decimal('8562.35')
    assert row.deductions is None  # &nbsp; → None


def test_parse_income_expenses_row2_values(sample_html_path: Path) -> None:
    """Test second row values: TEST001 contract."""
    soup = parse_soup(sample_html_path)
    result = parse_income_expenses(soup)

    assert result is not None
    row = result.rows[1]

    assert row.contract_code == 'TEST001'
    assert row.income_code == '1530'
    assert row.income_amount == Decimal('18732.64')
    assert row.taxable_amount == Decimal('3428.17')
    assert row.expense_code == '201'
    assert row.expense_amount == Decimal('15304.47')
    assert row.deductions is None


def test_parse_income_expenses_missing_table(sample_html_path: Path) -> None:
    """Test that parse_income_expenses returns None when table is missing."""
    soup = parse_soup(sample_html_path)

    # Remove the table
    for p in soup.find_all('p'):
        if p.get_text(strip=True).startswith('I. ДОХОДЫ И РАСХОДЫ'):
            table = p.find_next_sibling('table')
            if table:
                table.decompose()

    result = parse_income_expenses(soup)
    assert result is None


def test_parse_income_expenses_none_when_table_absent() -> None:
    """Test that parse_income_expenses returns None when table is completely absent."""
    html = '<html><body><p>Some other table</p><table><tr><td>data</td></tr></table></body></html>'
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, 'lxml')
    result = parse_income_expenses(soup)
    assert result is None


def test_parse_income_expenses_seven_columns(sample_html_path: Path) -> None:
    """Test that all 7 columns are correctly parsed."""
    soup = parse_soup(sample_html_path)
    result = parse_income_expenses(soup)

    assert result is not None
    row = result.rows[0]

    # Verify all 7 fields are present and typed correctly
    assert isinstance(row.contract_code, str)
    assert isinstance(row.income_code, str)
    assert isinstance(row.income_amount, Decimal)
    assert isinstance(row.taxable_amount, Decimal)
    assert isinstance(row.expense_code, str)
    assert isinstance(row.expense_amount, Decimal)
    assert row.deductions is None or isinstance(row.deductions, Decimal)


def test_parse_income_expenses_contracts_may_differ(sample_html_path: Path) -> None:
    """Test that contract_code can differ from report contract (TEST001 vs TEST002)."""
    soup = parse_soup(sample_html_path)
    result = parse_income_expenses(soup)

    assert result is not None
    contracts = {row.contract_code for row in result.rows}

    # Should have both TEST001 and TEST002 in the table
    assert 'TEST001' in contracts
    assert 'TEST002' in contracts
