"""Tests for income_expenses_consolidated table parser (Task 10)."""

import pytest
from decimal import Decimal

from finreader.parsers.sberbank.brokerage_report._common import parse_soup
from finreader.parsers.sberbank.brokerage_report.tables.income_expenses_consolidated import (
    ConsolidatedIncomeExpenseRow,
    IncomeExpensesConsolidated,
    parse_income_expenses_consolidated,
)


def test_parse_income_expenses_consolidated_sample() -> None:
    """Test parsing consolidated income/expenses table from sample."""
    soup = parse_soup('tests/data/sberbank_report_sample.html')
    result = parse_income_expenses_consolidated(soup)

    assert result is not None
    assert isinstance(result, IncomeExpensesConsolidated)
    assert len(result.rows) == 1

    row = result.rows[0]
    assert isinstance(row, ConsolidatedIncomeExpenseRow)

    # Client name should have &nbsp; normalized to space
    assert row.client_name == 'Иванов И.И.'
    assert '\xa0' not in row.client_name

    # Numeric values
    assert row.income_code == '1530'
    assert row.income_amount == Decimal('31186.51')
    assert row.taxable_amount == Decimal('7319.69')
    assert row.expense_code == '201'
    assert row.expense_amount == Decimal('23866.82')

    # Optional fields that are empty in sample
    assert row.deductions is None
    assert row.nkd_reduction is None
    assert row.loss_carryforward is None


def test_parse_income_expenses_consolidated_missing_table() -> None:
    """Test that None is returned when table is absent."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup('<html><body><p>No table here</p></body></html>', 'lxml')
    result = parse_income_expenses_consolidated(soup)
    assert result is None


def test_consolidated_income_expense_row_immutable() -> None:
    """Test that ConsolidatedIncomeExpenseRow is frozen (immutable)."""
    row = ConsolidatedIncomeExpenseRow(
        client_name='Test Client',
        income_code='1530',
        income_amount=Decimal('1000.00'),
        taxable_amount=Decimal('800.00'),
        expense_code='201',
        expense_amount=Decimal('200.00'),
        deductions=None,
        nkd_reduction=None,
        loss_carryforward=None,
    )
    with pytest.raises(Exception):  # FrozenInstanceError
        setattr(row, 'client_name', 'New Name')


def test_consolidated_income_expense_row_with_all_values() -> None:
    """Test row with all optional fields populated."""
    row = ConsolidatedIncomeExpenseRow(
        client_name='Test Client',
        income_code='1530',
        income_amount=Decimal('1000.00'),
        taxable_amount=Decimal('800.00'),
        expense_code='201',
        expense_amount=Decimal('200.00'),
        deductions=Decimal('100.00'),
        nkd_reduction=Decimal('50.00'),
        loss_carryforward=Decimal('25.00'),
    )

    assert row.deductions == Decimal('100.00')
    assert row.nkd_reduction == Decimal('50.00')
    assert row.loss_carryforward == Decimal('25.00')
