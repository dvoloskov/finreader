"""Parser for asset_valuation table — "Оценка активов, руб."."""

from dataclasses import dataclass

from bs4 import BeautifulSoup
from decimal import Decimal

from finreader.parsers.sberbank.brokerage_report._common import (
    cell_text,
    find_table_by_title,
    parse_money,
    row_classes,
)


@dataclass(frozen=True)
class AssetValuationRow:
    """Single row in the asset valuation table."""

    venue: str
    start_securities: Decimal
    start_cash: Decimal
    start_total: Decimal
    end_securities: Decimal
    end_cash: Decimal
    end_total: Decimal
    change_securities: Decimal
    change_cash: Decimal
    change_total: Decimal


@dataclass(frozen=True)
class AssetValuationTotals:
    """Summary totals from the Итого row."""

    start_total: Decimal
    end_total: Decimal
    change_total: Decimal


@dataclass(frozen=True)
class AssetValuation:
    """Parsed asset valuation table data."""

    rows: list[AssetValuationRow]
    total: AssetValuationTotals | None


def parse_asset_valuation(soup: BeautifulSoup) -> AssetValuation | None:
    """
    Parse the asset valuation table.

    Table title prefix: "Оценка активов, руб."
    Has a 2-row group header structure:
    - Row 1: Торговая площадка | 3× (Начало/Конец/Изменение periods)
    - Row 2: 3× (Ценные бумаги/Денежные средства/Всего) per period

    Data row example: venue "Основной рынок", change values carry leading "+".
    The summary row "Итого" uses colspan="3" per period holding only totals.

    Args:
        soup: BeautifulSoup object.

    Returns:
        AssetValuation object or None if table absent.

    """
    table = find_table_by_title(soup, 'Оценка активов, руб.')
    if table is None:
        return None

    rows: list[AssetValuationRow] = []
    total = None

    # Process all rows
    for tr in table.find_all('tr'):
        # Skip header rows (table-header class)
        classes = row_classes(tr)
        if 'table-header' in classes:
            continue

        # Skip row-number rows (rn class)
        if any(cls.startswith('rn') for cls in classes):
            continue

        cells = tr.find_all('td')
        if not cells:
            continue

        # Check if this is a summary row (Итого)
        first_cell_text = cell_text(cells[0])
        if first_cell_text == 'Итого':
            # Parse summary row with colspan="3" per period
            # Structure: Итого | colspan=3 start_total | colspan=3 end_total | colspan=3 change_total
            if len(cells) == 4:
                start_total = parse_money(cell_text(cells[1]))
                end_total = parse_money(cell_text(cells[2]))
                change_total = parse_money(cell_text(cells[3]))

                if start_total and end_total and change_total:
                    total = AssetValuationTotals(
                        start_total=start_total,
                        end_total=end_total,
                        change_total=change_total,
                    )
            continue

        # Parse data row
        # Expected: 10 cells (venue + 9 numeric columns)
        if len(cells) == 10:
            venue = cell_text(cells[0])

            # Parse 9 numeric columns:
            # Columns 1-3: Start (securities, cash, total)
            # Columns 4-6: End (securities, cash, total)
            # Columns 7-9: Change (securities, cash, total)
            start_securities = parse_money(cell_text(cells[1]))
            start_cash = parse_money(cell_text(cells[2]))
            start_total = parse_money(cell_text(cells[3]))

            end_securities = parse_money(cell_text(cells[4]))
            end_cash = parse_money(cell_text(cells[5]))
            end_total = parse_money(cell_text(cells[6]))

            change_securities = parse_money(cell_text(cells[7]))
            change_cash = parse_money(cell_text(cells[8]))
            change_total = parse_money(cell_text(cells[9]))

            # Only add row if all required fields are present
            if (
                venue
                and start_securities is not None
                and start_cash is not None
                and start_total is not None
                and end_securities is not None
                and end_cash is not None
                and end_total is not None
                and change_securities is not None
                and change_cash is not None
                and change_total is not None
            ):
                rows.append(
                    AssetValuationRow(
                        venue=venue,
                        start_securities=start_securities,
                        start_cash=start_cash,
                        start_total=start_total,
                        end_securities=end_securities,
                        end_cash=end_cash,
                        end_total=end_total,
                        change_securities=change_securities,
                        change_cash=change_cash,
                        change_total=change_total,
                    )
                )

    return AssetValuation(rows=rows, total=total)
