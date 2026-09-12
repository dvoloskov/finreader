"""Cash flow summary table parsing."""

from .._validation import validate_table

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from finreader.parsers.sberbank.brokerage_report._common import (
    find_table_by_title,
    iter_data_rows,
    parse_money,
)

if TYPE_CHECKING:
    from bs4 import BeautifulSoup


@dataclass(frozen=True)
class CashFlowSummaryRow:
    """Single row in the cash flow summary table."""

    description: str
    amount: Decimal
    currency: str


@dataclass(frozen=True)
class CashFlowSummary:
    """Cash flow summary table: movement of funds for the period."""

    rows: list[CashFlowSummaryRow]


def parse_cash_flow_summary(soup: 'BeautifulSoup') -> CashFlowSummary | None:
    """
    Parse the cash flow summary table.

    Args:
        soup: BeautifulSoup object containing the report.

    Returns:
        CashFlowSummary if table found, None otherwise.

    """
    title_prefix = 'Сводная информация по движению денежных средств за период'
    table = find_table_by_title(soup, title_prefix)

    if table is None:
        return None

    validate_table(table, 'Сводная информация по движению денежных средств за период')

    rows: list[CashFlowSummaryRow] = []

    for row_cells in iter_data_rows(table):
        # Map columns: Описание | Сумма | Валюта
        description = row_cells[0].strip()
        amount_text = row_cells[1]
        currency = row_cells[2].strip()

        amount = parse_money(amount_text)

        if amount is None:
            # Skip rows with no amount (should not happen in this table)
            continue

        rows.append(
            CashFlowSummaryRow(
                description=description, amount=amount, currency=currency
            )
        )

    return CashFlowSummary(rows=rows)
