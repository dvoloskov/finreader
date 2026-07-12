"""income_expenses table parsing (Table I - without loss carryforward)."""

from dataclasses import dataclass
from decimal import Decimal

from bs4 import BeautifulSoup

from finreader.parsers.sberbank.brokerage_report._common import (
    cell_text,
    find_table_by_title,
    iter_data_rows,
    parse_money,
    row_classes,
)


@dataclass(frozen=True)
class IncomeExpenseRow:
    """Single row from the income_expenses table (Table I)."""

    contract_code: str  # "Код договора" (may differ from report contract)
    income_code: str  # "Код дохода"
    income_amount: Decimal  # "Сумма дохода, руб."
    taxable_amount: (
        Decimal  # "Облагаемая сумма дохода или сумма убытка" (may be negative)
    )
    expense_code: str  # "Код расхода или убытка"
    expense_amount: Decimal  # "Сумма документально подтвержденных расходов, руб."
    deductions: Decimal | None  # "Сумма стандартных налоговых вычетов" (&nbsp; → None)


@dataclass(frozen=True)
class IncomeExpenses:
    """Income and expenses table (Table I - without loss carryforward)."""

    rows: list[IncomeExpenseRow]


def parse_income_expenses(soup: BeautifulSoup) -> IncomeExpenses | None:
    """
    Parse the income_expenses table (Table I).

    Args:
        soup: BeautifulSoup object.

    Returns:
        IncomeExpenses object or None if table is not found.

    """
    # Find table by title prefix
    table = find_table_by_title(soup, 'I. ДОХОДЫ И РАСХОДЫ')
    if table is None:
        return None

    # Get data rows (skips row-number rows, summary rows, section rows)
    data_rows = iter_data_rows(table)

    # Parse each data row
    rows = []
    for row in data_rows:
        # Expect 7 columns
        if len(row) != 7:
            continue  # Skip malformed rows

        # Parse each column
        # Column 0: Код договора
        contract_code = (
            cell_text(table.find_all('tr')[3].find_all('td')[0])
            if len(row) == 7
            else row[0]
        )

        # Actually, let me use a different approach - get cells directly from the table row
        # The iter_data_rows returns cell text, but we need to parse with proper helpers

    # Actually, let me redo this properly - use the table structure directly
    rows: list[IncomeExpenseRow] = []
    for tr in table.find_all('tr'):
        # Skip header rows and row-number rows
        classes = row_classes(tr)
        if 'table-header' in classes or any(cls.startswith('rn') for cls in classes):
            continue

        # Get all cells
        cells = tr.find_all('td')
        if len(cells) != 7:
            continue  # Skip rows that don't have exactly 7 columns

        # Parse each column using helpers
        contract_code = cell_text(cells[0])
        income_code = cell_text(cells[1])
        income_amount = parse_money(cells[2].get_text(strip=True))
        taxable_amount = parse_money(cells[3].get_text(strip=True))
        expense_code = cell_text(cells[4])
        expense_amount = parse_money(cells[5].get_text(strip=True))
        deductions = parse_money(cells[6].get_text(strip=True))

        # Skip if required numeric fields are None
        if income_amount is None or expense_amount is None:
            continue

        # Create row
        row = IncomeExpenseRow(
            contract_code=contract_code,
            income_code=income_code,
            income_amount=income_amount,
            taxable_amount=taxable_amount or Decimal('0'),
            expense_code=expense_code,
            expense_amount=expense_amount,
            deductions=deductions,
        )
        rows.append(row)

    if not rows:
        return None

    return IncomeExpenses(rows=rows)
