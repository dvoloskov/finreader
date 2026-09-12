"""
Parse the 'Портфель Ценных Бумаг' (portfolio) table — Task 5 (most complex).

The portfolio table has 18 columns under a 2-row group header:
  - Основной рынок      (colspan 3): Наименование, ISIN, Валюта
  - Начало периода      (colspan 5): quantity, nominal, price, market_value, nkd
  - Конец периода       (colspan 5): same 5 fields
  - Изменение за период (colspan 2): quantity, market_value
  - Плановые показатели (colspan 3): receipts, charges, outgoing

Interleaved special rows (handled by a single ordered pass over <tr>):
  - Section row  ``<td colspan="18">Площадка: <venue></td>``  → sets ``venue``
    for every subsequent data row until the next section row.
  - Summary row  ``class="summary-row"`` with ``colspan="6"`` label
    ("Итого по площадке Фондовый рынок, RUB", "Итого по Основному рынку, RUB").
    The 12 cells after the colspan label map positionally (per the 18-column
    layout, columns 7..18) to: start_market_value, start_nkd, _skip_,
    _skip_, _skip_, end_market_value, end_nkd, _skip_, change_market_value,
    _skip_, _skip_, _skip_.  Empty cells → ``None``.
  - Spacer row   ``<td colspan="18">&nbsp;</td>``  → explicitly skipped.
"""

from .._validation import validate_table

from dataclasses import dataclass
from decimal import Decimal

from bs4 import BeautifulSoup, Tag

from finreader.parsers.sberbank.brokerage_report._common import (
    cell_text,
    find_table_by_title,
    has_table_header,
    int_attr,
    parse_int,
    parse_money,
    row_classes,
)


@dataclass(frozen=True)
class PortfolioRow:
    """Single security row in the portfolio table."""

    name: str
    isin: str
    price_currency: str
    venue: str
    start_quantity: int | None
    start_nominal: Decimal | None
    start_price: Decimal | None
    start_market_value: Decimal | None
    start_nkd: Decimal | None
    end_quantity: int | None
    end_nominal: Decimal | None
    end_price: Decimal | None
    end_market_value: Decimal | None
    end_nkd: Decimal | None
    change_quantity: int | None
    change_market_value: Decimal | None
    planned_receipts: int | None
    planned_charges: int | None
    planned_outgoing: int | None


@dataclass(frozen=True)
class PortfolioTotal:
    """
    Summary row ('Итого по ...') of the portfolio table.

    Only the 5 columns the report actually populates are exposed; the empty
    cells in the summary row map to ``None``.
    """

    label: str
    start_market_value: Decimal | None
    start_nkd: Decimal | None
    end_market_value: Decimal | None
    end_nkd: Decimal | None
    change_market_value: Decimal | None


@dataclass(frozen=True)
class Portfolio:
    """Container for the portfolio table."""

    rows: list[PortfolioRow]
    totals: list[PortfolioTotal]


_TITLE_PREFIX = 'Портфель Ценных Бумаг'
_VENUE_PREFIX = 'Площадка:'
# Expected total cell count of a populated data row (matches the 18-column
# 2-row group header: 3 + 5 + 5 + 2 + 3).
_EXPECTED_DATA_CELL_COUNT = 18
# Positional mapping of the 12 numeric cells that follow the colspan="6"
# label in a summary row. Indices are 0-based into the post-label cell list
# and correspond to columns 7..18 of the 18-column layout.
_TOTAL_START_MARKET_VALUE_IDX = 0
_TOTAL_START_NKD_IDX = 1
_TOTAL_END_MARKET_VALUE_IDX = 5
_TOTAL_END_NKD_IDX = 6
_TOTAL_CHANGE_MARKET_VALUE_IDX = 8
_TOTAL_NUMERIC_CELL_COUNT = 12


def _is_section_row(tr: Tag) -> str | None:
    """
    If ``tr`` is a 'Площадка:' section row, return the venue; else ``None``.

    A section row's first cell has ``colspan > 1`` and text starting with
    ``Площадка:``; the venue is the text after that prefix, stripped.
    """
    first_cell = tr.find('td')
    if first_cell is None:
        return None
    if int_attr(first_cell, 'colspan', 1) <= 1:
        return None
    text = cell_text(first_cell)
    if text.startswith(_VENUE_PREFIX):
        return text[len(_VENUE_PREFIX) :].strip()
    return None


def _is_blank_spacer_row(tr: Tag) -> bool:
    """
    Detect the explicit blank spacer row ``<td colspan="18">&nbsp;</td>``.

    Such rows have a single cell with ``colspan > 1`` whose normalised text is
    empty (the cell renders ``&nbsp;`` which ``cell_text`` collapses to '').
    """
    cells = tr.find_all('td')
    if len(cells) != 1:
        return False
    only = cells[0]
    if int_attr(only, 'colspan', 1) <= 1:
        return False
    return cell_text(only) == ''


def _parse_total_row(tr: Tag) -> PortfolioTotal | None:
    """
    Map a ``summary-row`` <tr> to a ``PortfolioTotal``.

    The first cell is the colspan label ("Итого по ..."). The remaining cells
    (12 in the sample) correspond positionally to columns 7..18 of the layout;
    we extract the 5 columns the report actually populates and treat the rest
    as positional gaps. Returns ``None`` if the row shape is unrecognised.
    """
    cells = tr.find_all(['td', 'th'])
    if len(cells) < 2:
        return None
    label = cell_text(cells[0])
    numeric = [cell_text(c) for c in cells[1:]]

    def _get(idx: int) -> Decimal | None:
        if idx >= len(numeric):
            return None
        return parse_money(numeric[idx])

    return PortfolioTotal(
        label=label,
        start_market_value=_get(_TOTAL_START_MARKET_VALUE_IDX),
        start_nkd=_get(_TOTAL_START_NKD_IDX),
        end_market_value=_get(_TOTAL_END_MARKET_VALUE_IDX),
        end_nkd=_get(_TOTAL_END_NKD_IDX),
        change_market_value=_get(_TOTAL_CHANGE_MARKET_VALUE_IDX),
    )


def parse_portfolio(soup: BeautifulSoup) -> Portfolio | None:
    """
    Parse the 'Портфель Ценных Бумаг' table.

    Returns ``None`` if the table is absent.

    Strategy: a single ordered pass over ``<tr>`` elements so that section-row
    venue metadata can be attached to the right data rows. Each row is
    classified exactly once: header / row-number / section / spacer / summary /
    data. The blank spacer row is explicitly detected and skipped (never
    silently dropped).

    Args:
        soup: BeautifulSoup object.

    Returns:
        ``Portfolio`` or ``None``.

    """
    table = find_table_by_title(soup, _TITLE_PREFIX)
    if table is None:
        return None

    validate_table(table, 'Портфель Ценных Бумаг')

    rows: list[PortfolioRow] = []
    totals: list[PortfolioTotal] = []
    current_venue = ''

    for tr in table.find_all('tr'):
        if has_table_header(tr):
            continue

        classes = row_classes(tr)
        if any(c.startswith('rn') for c in classes):
            continue

        venue = _is_section_row(tr)
        if venue is not None:
            current_venue = venue
            continue

        if _is_blank_spacer_row(tr):
            continue

        if 'summary-row' in classes or 'summary-row2' in classes:
            total = _parse_total_row(tr)
            if total is not None:
                totals.append(total)
            continue

        cells = [cell_text(c) for c in tr.find_all(['td', 'th'])]
        if len(cells) < _EXPECTED_DATA_CELL_COUNT:
            continue

        name = cells[0].strip()
        if not name:
            # Defensive: don't emit anonymous rows.
            continue

        row = PortfolioRow(
            name=name,
            isin=cells[1].strip(),
            price_currency=cells[2].strip(),
            venue=current_venue,
            start_quantity=parse_int(cells[3]),
            start_nominal=parse_money(cells[4]),
            start_price=parse_money(cells[5]),
            start_market_value=parse_money(cells[6]),
            start_nkd=parse_money(cells[7]),
            end_quantity=parse_int(cells[8]),
            end_nominal=parse_money(cells[9]),
            end_price=parse_money(cells[10]),
            end_market_value=parse_money(cells[11]),
            end_nkd=parse_money(cells[12]),
            change_quantity=parse_int(cells[13]),
            change_market_value=parse_money(cells[14]),
            planned_receipts=parse_int(cells[15]),
            planned_charges=parse_int(cells[16]),
            planned_outgoing=parse_int(cells[17]),
        )
        rows.append(row)

    return Portfolio(rows=rows, totals=totals)
