"""Parse the 'Движение денежных средств за период' (cash flow) table."""

from .._validation import validate_table

from dataclasses import dataclass
from decimal import Decimal
from datetime import date

from bs4 import BeautifulSoup

from finreader.parsers.sberbank.brokerage_report._common import (
    cell_text,
    find_table_by_title,
    iter_data_rows,
    parse_date,
    parse_money,
    row_classes,
)


@dataclass(frozen=True)
class CashFlowRow:
    """Single row in cash flow table."""

    date: date
    venue: str
    description: str
    currency: str
    credit: Decimal | None  # Сумма зачисления
    debit: Decimal | None  # Сумма списания


@dataclass(frozen=True)
class CashFlowTotal:
    """Summary row (Итого, RUB) in cash flow table."""

    label: str
    credit: Decimal
    debit: Decimal


@dataclass(frozen=True)
class CashFlow:
    """Container for cash flow table data."""

    rows: list[CashFlowRow]
    total: CashFlowTotal | None


def parse_cash_flow(soup: BeautifulSoup) -> CashFlow | None:
    """
    Parse the 'Движение денежных средств за период' table.

    Returns None if table is not found.

    Args:
        soup: BeautifulSoup object.

    Returns:
        CashFlow or None.

    """
    table = find_table_by_title(soup, 'Движение денежных средств за период')
    if table is None:
        return None

    validate_table(table, 'Движение денежных средств за период')

    rows: list[CashFlowRow] = []
    total: CashFlowTotal | None = None

    # Parse data rows using iter_data_rows
    data_rows = iter_data_rows(table)

    for row_cells in data_rows:
        # Expected columns:
        # 0: Дата, 1: Торговая площадка, 2: Описание операции,
        # 3: Валюта, 4: Сумма зачисления, 5: Сумма списания
        if len(row_cells) >= 6:
            row_date = parse_date(row_cells[0])
            venue = row_cells[1].strip()
            description = row_cells[2].strip()
            currency = row_cells[3].strip()
            credit = parse_money(row_cells[4])
            debit = parse_money(row_cells[5])

            # Ensure date was parsed successfully
            if row_date is not None:
                rows.append(
                    CashFlowRow(
                        date=row_date,
                        venue=venue,
                        description=description,
                        currency=currency,
                        credit=credit,
                        debit=debit,
                    )
                )

    # Parse summary row (Итого, RUB)
    # Summary row has class="summary-row" and colspan=4 on first cell
    for tr in table.find_all('tr'):
        classes = row_classes(tr)
        if 'summary-row' in classes:
            cells = tr.find_all(['td', 'th'])
            if len(cells) >= 3:
                first_cell = cells[0]
                label = cell_text(first_cell)

                # Columns after label: credit, debit
                # (label has colspan=4, so cells[1] is credit, cells[2] is debit)
                credit = parse_money(cell_text(cells[1]))
                debit = parse_money(cell_text(cells[2]))

                # Ensure both credit and debit are present
                if credit is not None and debit is not None:
                    total = CashFlowTotal(
                        label=label,
                        credit=credit,
                        debit=debit,
                    )
                    break

    return CashFlow(rows=rows, total=total)
