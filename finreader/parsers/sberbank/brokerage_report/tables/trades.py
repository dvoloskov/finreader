"""
Parse the 'Сделки купли/продажи ценных бумаг' (trades) table.

Status code meanings come from the report footnote:
  З  - сделка заключена в течение периода;
  О  - на конец периода ни одно обязательство по сделке не исполнено;
  И  - на конец периода сделка исполнена в полном объеме;
  Д  - донорская сделка, заключенная НКО НКЦ(АО);
  ИЦБ - (внебиржевые) исполнены обязательства/требования по ценным бумагам;
  ИДС - (внебиржевые) исполнены обязательства/требования по денежным средствам;
  И1 - на конец периода исполнены обязательства по 1-й части;
  П  - на конец периода сделка подлежит урегулированию;
  У  - на конец периода сделка урегулирована.
"""

from .._validation import validate_table

from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal
from enum import Enum

from bs4 import BeautifulSoup, Tag

from finreader.parsers.sberbank.brokerage_report._common import (
    cell_text,
    find_table_by_title,
    has_table_header,
    int_attr,
    parse_date,
    parse_int,
    parse_money,
    parse_time,
    row_classes,
)


class TradeDirection(Enum):
    """Direction of a trade (Вид)."""

    BUY = 'Покупка'
    SELL = 'Продажа'

    @classmethod
    def from_code(cls, code: str) -> 'TradeDirection':
        """
        Resolve a Russian direction label to the enum member.

        Raises ValueError on unknown labels.
        """
        cleaned = code.strip()
        for member in cls:
            if member.value == cleaned:
                return member
        raise ValueError(f'Unknown trade direction: {code!r}')


class TradeStatus(Enum):
    """Status of a trade (Статус сделки) per the report footnote."""

    Z = 'З'
    O = 'О'  # noqa: E741 (required Cyrillic status code)
    I = 'И'  # noqa: E741 (required Cyrillic status code)
    D = 'Д'
    ICB = 'ИЦБ'
    IDS = 'ИДС'
    I1 = 'И1'
    P = 'П'
    U = 'У'

    @classmethod
    def from_code(cls, code: str) -> 'TradeStatus':
        """
        Resolve a Cyrillic status code to the enum member.

        Raises ValueError on unknown codes.
        """
        cleaned = code.strip()
        for member in cls:
            if member.value == cleaned:
                return member
        raise ValueError(f'Unknown trade status code: {code!r}')


@dataclass(frozen=True)
class Trade:
    """Single trade row."""

    trade_date: date | None
    settlement_date: date | None
    trade_time: time | None
    security_name: str
    security_code: str
    currency: str
    direction: TradeDirection
    quantity: int | None
    price: Decimal | None
    amount: Decimal | None
    nkd: Decimal | None
    broker_fee: Decimal | None
    exchange_fee: Decimal | None
    trade_number: str
    comment: str | None
    status: TradeStatus
    venue: str


@dataclass(frozen=True)
class TradesTotal:
    """Summary row (Итого, RUB) of the trades table."""

    amount: Decimal
    nkd: Decimal
    broker_fee: Decimal
    exchange_fee: Decimal


@dataclass(frozen=True)
class Trades:
    """Container for the trades table."""

    rows: list[Trade]
    total: TradesTotal | None


_TITLE_PREFIX = 'Сделки купли/продажи ценных бумаг'
_VENUE_PREFIX = 'Площадка:'


def _is_section_row(tr: Tag) -> str | None:
    """If ``tr`` is a section row, return the venue string; else None."""
    first_cell = tr.find('td')
    if first_cell is None:
        return None
    if int_attr(first_cell, 'colspan', 1) <= 1:
        return None
    text = cell_text(first_cell)
    if text.startswith(_VENUE_PREFIX):
        return text[len(_VENUE_PREFIX) :].strip()
    return None


def parse_trades(soup: BeautifulSoup) -> Trades | None:
    """
    Parse the 'Сделки купли/продажи ценных бумаг' table.

    Returns ``None`` if the table is absent.

    The table has 16 data columns and may contain:
      - Section rows ``Площадка: <venue>`` (set ``venue`` for subsequent rows).
      - A summary row ``Итого, RUB`` (``colspan="9"`` label) → ``TradesTotal``.

    Args:
        soup: BeautifulSoup object.

    Returns:
        ``Trades`` or ``None``.

    """
    table = find_table_by_title(soup, _TITLE_PREFIX)
    if table is None:
        return None

    validate_table(table, 'Сделки купли/продажи ценных бумаг')

    rows: list[Trade] = []
    total: TradesTotal | None = None
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

        if 'summary-row' in classes:
            cells = tr.find_all(['td', 'th'])
            values = [cell_text(c) for c in cells[1:]]
            money_values = [parse_money(v) for v in values]
            amount, nkd, broker_fee, exchange_fee = (money_values + [None] * 4)[:4]
            if (
                amount is not None
                and nkd is not None
                and broker_fee is not None
                and exchange_fee is not None
            ):
                total = TradesTotal(
                    amount=amount,
                    nkd=nkd,
                    broker_fee=broker_fee,
                    exchange_fee=exchange_fee,
                )
            continue

        cells = [cell_text(c) for c in tr.find_all(['td', 'th'])]
        if len(cells) < 16:
            continue

        comment_text = cells[14].strip()
        row = Trade(
            trade_date=parse_date(cells[0]),
            settlement_date=parse_date(cells[1]),
            trade_time=parse_time(cells[2]),
            security_name=cells[3].strip(),
            security_code=cells[4].strip(),
            currency=cells[5].strip(),
            direction=TradeDirection.from_code(cells[6]),
            quantity=parse_int(cells[7]),
            price=parse_money(cells[8]),
            amount=parse_money(cells[9]),
            nkd=parse_money(cells[10]),
            broker_fee=parse_money(cells[11]),
            exchange_fee=parse_money(cells[12]),
            trade_number=cells[13].strip(),
            comment=comment_text or None,
            status=TradeStatus.from_code(cells[15]),
            venue=current_venue,
        )
        rows.append(row)

    return Trades(rows=rows, total=total)
