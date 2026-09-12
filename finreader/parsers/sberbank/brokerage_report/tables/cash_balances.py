"""Parse the 'Денежные средства' (cash balances) table."""

from .._validation import validate_table

from dataclasses import dataclass
from decimal import Decimal

from bs4 import BeautifulSoup

from finreader.parsers.sberbank.brokerage_report._common import (
    cell_text,
    find_table_by_title,
    int_attr,
    parse_money,
    row_classes,
)


@dataclass(frozen=True)
class CashBalanceRow:
    """Single currency row in cash balances table."""

    venue: str
    currency: str
    rate_end: Decimal | None
    start: Decimal
    change: Decimal | None
    end: Decimal
    planned_in: Decimal | None
    planned_out: Decimal | None
    planned_outgoing: Decimal | None


@dataclass(frozen=True)
class CashBalanceTotal:
    """Summary row (Итого) in cash balances table."""

    label: str
    start: Decimal | None
    change: Decimal | None
    end: Decimal | None
    planned_in: Decimal | None
    planned_out: Decimal | None
    planned_outgoing: Decimal | None


@dataclass(frozen=True)
class CashBalances:
    """Container for cash balances table data."""

    rows: list[CashBalanceRow]
    totals: list[CashBalanceTotal]


def parse_cash_balances(soup: BeautifulSoup) -> CashBalances | None:
    """
    Parse the 'Денежные средства' table.

    Returns None if table is not found.

    Args:
        soup: BeautifulSoup object.

    Returns:
        CashBalances or None.

    """
    table = find_table_by_title(soup, 'Денежные средства')
    if table is None:
        return None

    validate_table(table, 'Денежные средства')

    rows: list[CashBalanceRow] = []
    totals: list[CashBalanceTotal] = []

    for tr in table.find_all('tr'):
        # Skip header and row-number rows
        classes = row_classes(tr)
        if 'table-header' in classes:
            continue
        if any(cls.startswith('rn') for cls in classes):
            continue

        cells = tr.find_all(['td', 'th'])
        if not cells:
            continue

        first_cell = cells[0]
        colspan = int_attr(first_cell, 'colspan')

        # Summary row: first cell has colspan=3
        if colspan == 3:
            label = cell_text(first_cell)
            # Columns after label: start, change, end, planned_in, planned_out, planned_outgoing
            # (6 columns total)
            start = parse_money(cell_text(cells[1]))
            change = parse_money(cell_text(cells[2]))
            end = parse_money(cell_text(cells[3]))
            planned_in = parse_money(cell_text(cells[4]))
            planned_out = parse_money(cell_text(cells[5]))
            planned_outgoing = parse_money(cell_text(cells[6]))
            totals.append(
                CashBalanceTotal(
                    label=label,
                    start=start,
                    change=change,
                    end=end,
                    planned_in=planned_in,
                    planned_out=planned_out,
                    planned_outgoing=planned_outgoing,
                )
            )
            continue

        # Data row: 9 columns
        # 0: venue, 1: currency, 2: rate_end, 3: start, 4: change,
        # 5: end, 6: planned_in, 7: planned_out, 8: planned_outgoing
        if len(cells) >= 9:
            venue = cell_text(cells[0])
            currency = cell_text(cells[1])
            rate_end = parse_money(cell_text(cells[2]))
            start = parse_money(cell_text(cells[3]))
            change = parse_money(cell_text(cells[4]))
            end = parse_money(cell_text(cells[5]))
            planned_in = parse_money(cell_text(cells[6]))
            planned_out = parse_money(cell_text(cells[7]))
            planned_outgoing = parse_money(cell_text(cells[8]))

            # Ensure required fields are present
            if start is not None and end is not None:
                rows.append(
                    CashBalanceRow(
                        venue=venue,
                        currency=currency,
                        rate_end=rate_end,
                        start=start,
                        change=change,
                        end=end,
                        planned_in=planned_in,
                        planned_out=planned_out,
                        planned_outgoing=planned_outgoing,
                    )
                )

    return CashBalances(rows=rows, totals=totals)
