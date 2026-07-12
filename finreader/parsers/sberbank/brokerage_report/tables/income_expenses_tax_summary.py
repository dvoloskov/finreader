"""
Income/expenses tax summary (table III) parsing.

Table "III. ИТОГОВЫЙ ФИНАНСОВЫЙ РЕЗУЛЬТАТ" has 8 monetary columns and
interleaved ``<td colspan="8">Ставка X%</td>`` section rows that set the tax
rate for the data rows that follow them. Data rows appearing before any
"Ставка X%" section have ``tax_rate = None``.

Design note: we cannot use ``iter_data_rows`` + ``iter_section_rows`` together
here because those helpers return two independent lists and lose the
document-order relationship between a section row and the data rows that
follow it — which is exactly what we need to attach ``tax_rate``. Instead we
make a single ordered pass over ``<tr>`` elements, classifying each row with
the same heuristics the shared helpers use, and reuse ``cell_text``,
``parse_money`` and ``parse_int`` from ``_common``.
"""

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from bs4 import Tag

from finreader.parsers.sberbank.brokerage_report._common import (
    cell_text,
    find_table_by_title,
    int_attr,
    parse_int,
    parse_money,
    row_classes,
)

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

_TITLE_PREFIX = 'III. ИТОГОВЫЙ ФИНАНСОВЫЙ РЕЗУЛЬТАТ'
# "Ставка 13%", "Ставка 13 %" — tolerate optional space before the percent.
_TAX_RATE_RE = re.compile(r'Ставка\s+(\d+)\s*%')


@dataclass(frozen=True)
class TaxSummaryRow:
    """Single data row in the tax summary table (III)."""

    income_amount: Decimal | None
    taxable_amount: Decimal | None
    calculated_tax: Decimal | None  # "Сумма налога исчисленная"
    withheld_tax: Decimal | None  # "Сумма налога удержанная"
    tax_to_withhold: Decimal | None  # may be negative ("со знаком минус")
    expenses: Decimal | None
    deductions: Decimal | None
    loss: Decimal | None
    tax_rate: int | None  # from the preceding "Ставка X%" row


@dataclass(frozen=True)
class IncomeExpensesTaxSummary:
    """Table III: final financial result per tax-rate bracket."""

    rows: list[TaxSummaryRow]


def _extract_tax_rate(text: str) -> int | None:
    """Extract the integer rate from a ``Ставка X%`` section-row label."""
    match = _TAX_RATE_RE.search(text)
    if match is None:
        return None
    # parse_int handles stray nbsp/whitespace; the regex guarantees digits.
    return parse_int(match.group(1))


def _classify_row(row: Tag):
    """
    Classify a ``<tr>`` for the ordered pass.

    Returns one of:
    - ``('skip', None)``    — header / row-number / summary / non-tax section
    - ``('section', rate)`` — a ``Ставка X%`` row (rate is int or None)
    - ``('data', None)``    — a normal data row
    """
    classes = row_classes(row)
    if any(c.startswith('rn') for c in classes):
        return 'skip', None
    if any(c in ('summary-row', 'summary-row2', 'table-header') for c in classes):
        return 'skip', None

    first_cell = row.find('td')
    if first_cell is not None and int_attr(first_cell, 'colspan', 1) > 1:
        label = cell_text(first_cell)
        if label.startswith('Ставка'):
            return 'section', _extract_tax_rate(label)
        # Other colspan>1 rows (Площадка:, Итого, ...) are not data.
        return 'skip', None

    return 'data', None


def parse_income_expenses_tax_summary(
    soup: 'BeautifulSoup',
) -> IncomeExpensesTaxSummary | None:
    """
    Parse table III ("III. ИТОГОВЫЙ ФИНАНСОВЫЙ РЕЗУЛЬТАТ").

    Args:
        soup: BeautifulSoup object containing the report.

    Returns:
        ``IncomeExpensesTaxSummary`` if the table is found, otherwise ``None``.

    """
    table = find_table_by_title(soup, _TITLE_PREFIX)
    if table is None:
        return None

    rows: list[TaxSummaryRow] = []
    current_rate: int | None = None

    for tr in table.find_all('tr'):
        kind, payload = _classify_row(tr)
        if kind == 'skip':
            continue
        if kind == 'section':
            # Set the rate for all subsequent data rows. A "Ставка" row whose
            # rate cannot be parsed resets the bracket to None.
            current_rate = payload
            continue

        cells = [cell_text(c) for c in tr.find_all(['td', 'th'])]
        # Skip malformed/short rows defensively; expect 8 columns.
        if not cells or len(cells) < 8:
            continue

        rows.append(
            TaxSummaryRow(
                income_amount=parse_money(cells[0]),
                taxable_amount=parse_money(cells[1]),
                calculated_tax=parse_money(cells[2]),
                withheld_tax=parse_money(cells[3]),
                tax_to_withhold=parse_money(cells[4]),
                expenses=parse_money(cells[5]),
                deductions=parse_money(cells[6]),
                loss=parse_money(cells[7]),
                tax_rate=current_rate,
            )
        )

    return IncomeExpensesTaxSummary(rows=rows)
