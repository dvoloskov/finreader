"""Validate source row shapes and values before constructing table models."""

from collections.abc import Callable
from dataclasses import dataclass
import re

from bs4 import Tag

from ._common import (
    cell_text,
    has_table_header,
    int_attr,
    parse_date,
    parse_int,
    parse_money,
    parse_time,
    row_classes,
)


@dataclass(frozen=True)
class Layout:
    """Positional source fields, not a financial interpretation."""

    names: tuple[str, ...]
    required: tuple[int, ...] = ()
    money: tuple[int, ...] = ()
    integers: tuple[int, ...] = ()
    dates: tuple[int, ...] = ()
    times: tuple[int, ...] = ()


LAYOUTS: dict[str, Layout] = {
    'Оценка активов, руб.': Layout(
        tuple(
            'venue start_securities start_cash start_total end_securities end_cash end_total change_securities change_cash change_total'.split()
        ),
        tuple(range(10)),
        tuple(range(1, 10)),
    ),
    'Сводная информация по движению денежных средств за период': Layout(
        ('description', 'amount', 'currency'), (0, 1, 2), (1,)
    ),
    'Денежные средства': Layout(
        tuple(
            'venue currency rate_end start change end planned_in planned_out planned_outgoing'.split()
        ),
        (0, 1, 3, 5),
        tuple(range(2, 9)),
    ),
    'Движение денежных средств за период': Layout(
        ('date', 'venue', 'description', 'currency', 'credit', 'debit'),
        (0, 1, 2, 3),
        (4, 5),
        dates=(0,),
    ),
    'Портфель Ценных Бумаг': Layout(
        tuple(
            'name isin price_currency start_quantity start_nominal start_price start_market_value start_nkd end_quantity end_nominal end_price end_market_value end_nkd change_quantity change_market_value planned_receipts planned_charges planned_outgoing'.split()
        ),
        (0, 1, 2),
        (4, 5, 6, 7, 9, 10, 11, 12, 14),
        (3, 8, 13, 15, 16, 17),
    ),
    'Сделки купли/продажи ценных бумаг': Layout(
        tuple(
            'trade_date settlement_date trade_time security_name security_code currency direction quantity price amount nkd broker_fee exchange_fee trade_number comment status'.split()
        ),
        (3, 4, 5, 6, 13, 15),
        (8, 9, 10, 11, 12),
        (7,),
        (0, 1),
        (2,),
    ),
    'Справочник Ценных Бумаг': Layout(
        ('name', 'code', 'isin', 'issuer', 'kind', 'issue'), (0, 1, 2, 4)
    ),
    'I. ДОХОДЫ И РАСХОДЫ': Layout(
        tuple(
            'contract_code income_code income_amount taxable_amount expense_code expense_amount deductions'.split()
        ),
        (0, 1, 2, 3, 4, 5),
        (2, 3, 5, 6),
    ),
    'II. ДОХОДЫ И РАСХОДЫ': Layout(
        tuple(
            'client_name income_code income_amount taxable_amount expense_code expense_amount deductions nkd_reduction loss_carryforward'.split()
        ),
        (0, 1, 2, 3, 4, 5),
        (2, 3, 5, 6, 7, 8),
    ),
    'III. ИТОГОВЫЙ ФИНАНСОВЫЙ РЕЗУЛЬТАТ': Layout(
        tuple(
            'income_amount taxable_amount calculated_tax withheld_tax tax_to_withhold expenses deductions loss'.split()
        ),
        money=tuple(range(8)),
    ),
}

SUMMARY_LAYOUTS: dict[str, Layout] = {
    'Оценка активов, руб.': Layout(
        ('label', 'start_total', 'end_total', 'change_total'), (0, 1, 2, 3), (1, 2, 3)
    ),
    'Денежные средства': Layout(
        tuple('label start change end planned_in planned_out planned_outgoing'.split()),
        (0,),
        tuple(range(1, 7)),
    ),
    'Движение денежных средств за период': Layout(
        ('label', 'credit', 'debit'), (0, 1, 2), (1, 2)
    ),
    'Портфель Ценных Бумаг': Layout(
        tuple(
            'label start_market_value start_nkd gap1 gap2 gap3 end_market_value end_nkd gap4 change_market_value gap5 gap6 gap7'.split()
        ),
        (0,),
        (1, 2, 6, 7, 9),
    ),
    'Сделки купли/продажи ценных бумаг': Layout(
        ('label', 'amount', 'nkd', 'broker_fee', 'exchange_fee', 'gap'),
        (0, 1, 2, 3, 4),
        (1, 2, 3, 4),
    ),
}


def validate_table(table: Tag, title: str) -> None:
    """Fail with section, physical row and field context on malformed content."""
    if title not in LAYOUTS:
        return
    seen_summaries: set[str] = set()
    for row_number, row in enumerate(table.find_all('tr'), 1):
        classes = row_classes(row)
        if has_table_header(row) or any(c.startswith('rn') for c in classes):
            continue
        cells = row.find_all(['td', 'th'])
        if not cells:
            raise ValueError(f'{title}, row {row_number}: empty row without cells')
        values = [cell_text(c) for c in cells]
        label = values[0]
        if len(cells) == 1 and int_attr(cells[0], 'colspan', 1) > 1:
            if not label:
                continue
            if (
                label.startswith('Площадка:')
                and label.removeprefix('Площадка:').strip()
            ):
                continue
            if re.fullmatch(r'Ставка\s+\d+\s*%', label):
                continue
        summary = label.startswith('Итого') or any(
            c in ('summary-row', 'summary-row2') for c in classes
        )
        if summary:
            if title not in SUMMARY_LAYOUTS:
                raise ValueError(f'{title}, row {row_number}: unsupported summary')
            if label in seen_summaries:
                raise ValueError(f'{title}, row {row_number}: duplicate summary')
            seen_summaries.add(label)
        layout = SUMMARY_LAYOUTS[title] if summary else LAYOUTS[title]
        # Some report versions omit the trailing empty trade-summary cell.
        if (
            summary
            and title == 'Сделки купли/продажи ценных бумаг'
            and len(values) == 5
        ):
            values.append('')
        if len(values) != len(layout.names):
            raise ValueError(
                f'{title}, row {row_number}: expected {len(layout.names)} cells, got {len(values)}'
            )
        for index, (name, value) in enumerate(zip(layout.names, values, strict=True)):
            try:
                if index in layout.required and not value:
                    raise ValueError('required value is missing')
                if name.startswith('gap') and value:
                    raise ValueError('expected an empty structural cell')
                converter: Callable[[str | None], object] | None = None
                for indices, candidate in (
                    (layout.money, parse_money),
                    (layout.integers, parse_int),
                    (layout.dates, parse_date),
                    (layout.times, parse_time),
                ):
                    if index in indices:
                        converter = candidate
                if converter is not None:
                    _ = converter(value)
                if name == 'direction' and value not in ('Покупка', 'Продажа'):
                    raise ValueError('unknown trade direction')
                if name == 'status' and value not in (
                    'З',
                    'О',
                    'И',
                    'Д',
                    'ИЦБ',
                    'ИДС',
                    'И1',
                    'П',
                    'У',
                ):
                    raise ValueError('unknown trade status')
            except ValueError as error:
                raise ValueError(
                    f'{title}, row {row_number}, field {name}: {error}'
                ) from error
