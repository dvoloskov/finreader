"""
Parser for income_expenses_consolidated table (Task 10).

Table: II. ДОХОДЫ И РАСХОДЫ ... (консолидированные данные с переносом убытков)

Columns (9):
1. Наименование клиента (client_name)
2. Код дохода (income_code)
3. Сумма дохода, руб. (income_amount)
4. Облагаемая сумма дохода или сумма убытка (taxable_amount)
5. Код расхода или убытка (expense_code)
6. Сумма документально подтвержденных расходов, руб. (expense_amount)
7. Сумма стандартных налоговых вычетов, руб. (deductions)
8. Сумма УНКД, уменьшающая доход по коду 1011, руб. (nkd_reduction)
9. Сумма убытка по ЦБ, перенесенная на доход по коду 1011 (loss_carryforward)

Note: client_name may contain &nbsp; which must be normalized to space.
"""

from .._validation import validate_table

from dataclasses import dataclass
from decimal import Decimal

from bs4 import BeautifulSoup

from .._common import find_table_by_title, iter_data_rows, parse_money


@dataclass(frozen=True)
class ConsolidatedIncomeExpenseRow:
    """Single row from consolidated income/expenses table."""

    client_name: str  # "Наименование клиента" (e.g. "Иванов И.И.")
    income_code: str  # "Код дохода"
    income_amount: Decimal  # "Сумма дохода, руб."
    taxable_amount: Decimal  # "Облагаемая сумма дохода или сумма убытка"
    expense_code: str  # "Код расхода или убытка"
    expense_amount: Decimal  # "Сумма документально подтвержденных расходов, руб."
    deductions: Decimal | None  # "Сумма стандартных налоговых вычетов, руб."
    nkd_reduction: Decimal | None  # "Сумма УНКД, уменьшающая доход по коду 1011, руб."
    loss_carryforward: (
        Decimal | None
    )  # "Сумма убытка по ЦБ, перенесенная на доход по коду 1011"


@dataclass(frozen=True)
class IncomeExpensesConsolidated:
    """Consolidated income/expenses table with loss carryforward."""

    rows: list[ConsolidatedIncomeExpenseRow]


def parse_income_expenses_consolidated(
    soup: BeautifulSoup,
) -> IncomeExpensesConsolidated | None:
    """
    Parse consolidated income/expenses table (II. ДОХОДЫ И РАСХОДЫ).

    Args:
        soup: BeautifulSoup object.

    Returns:
        IncomeExpensesConsolidated object or None if table not found.

    """
    # Find table by title prefix
    table = find_table_by_title(soup, 'II. ДОХОДЫ И РАСХОДЫ')
    if table is None:
        return None

    validate_table(table, 'II. ДОХОДЫ И РАСХОДЫ')

    # Get data rows
    data_rows = iter_data_rows(table)
    if not data_rows:
        return IncomeExpensesConsolidated(rows=[])

    # Parse each row
    rows: list[ConsolidatedIncomeExpenseRow] = []
    for cells in data_rows:
        # Skip header row (contains "Наименование клиента")
        if 'Наименование клиента' in cells:
            continue

        # Map 9 columns
        client_name = cells[0]
        income_code = cells[1]
        income_amount = parse_money(cells[2])
        taxable_amount = parse_money(cells[3])
        expense_code = cells[4]
        expense_amount = parse_money(cells[5])
        deductions = parse_money(cells[6])
        nkd_reduction = parse_money(cells[7])
        loss_carryforward = parse_money(cells[8])

        # Validate required fields
        if income_amount is None or expense_amount is None:
            continue  # Skip rows without required monetary values

        row = ConsolidatedIncomeExpenseRow(
            client_name=client_name,
            income_code=income_code,
            income_amount=income_amount,
            taxable_amount=taxable_amount
            if taxable_amount is not None
            else Decimal('0'),
            expense_code=expense_code,
            expense_amount=expense_amount,
            deductions=deductions,
            nkd_reduction=nkd_reduction,
            loss_carryforward=loss_carryforward,
        )
        rows.append(row)

    return IncomeExpensesConsolidated(rows=rows)
