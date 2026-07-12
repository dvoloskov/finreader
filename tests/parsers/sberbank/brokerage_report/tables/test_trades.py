"""Tests for trades table parser (Task 8)."""

from dataclasses import FrozenInstanceError
from datetime import date, time
from decimal import Decimal

import pytest
from bs4 import BeautifulSoup

from finreader.parsers.sberbank.brokerage_report._common import parse_soup
from finreader.parsers.sberbank.brokerage_report.tables.trades import (
    Trade,
    TradeDirection,
    TradeStatus,
    Trades,
    TradesTotal,
    parse_trades,
)


@pytest.fixture
def soup() -> BeautifulSoup:
    """Load sample HTML."""
    return parse_soup('tests/data/sberbank_report_sample.html')


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


def test_trade_direction_values() -> None:
    """TradeDirection enum must use the exact Russian strings."""
    assert TradeDirection.BUY.value == 'Покупка'
    assert TradeDirection.SELL.value == 'Продажа'


def test_trade_status_values() -> None:
    """TradeStatus enum must cover all 9 footnote codes with Russian values."""
    assert TradeStatus.Z.value == 'З'
    assert TradeStatus.O.value == 'О'
    assert TradeStatus.I.value == 'И'
    assert TradeStatus.D.value == 'Д'
    assert TradeStatus.ICB.value == 'ИЦБ'
    assert TradeStatus.IDS.value == 'ИДС'
    assert TradeStatus.I1.value == 'И1'
    assert TradeStatus.P.value == 'П'
    assert TradeStatus.U.value == 'У'


def test_trade_status_from_code_known() -> None:
    """from_code returns the matching enum member for known codes."""
    assert TradeStatus.from_code('И') is TradeStatus.I
    assert TradeStatus.from_code('З') is TradeStatus.Z
    assert TradeStatus.from_code('ИЦБ') is TradeStatus.ICB
    assert TradeStatus.from_code('У') is TradeStatus.U


def test_trade_status_from_code_unknown_raises() -> None:
    """from_code must raise ValueError on unknown code."""
    with pytest.raises(ValueError):
        _ = TradeStatus.from_code('X')


def test_trade_status_from_code_strips_whitespace() -> None:
    """from_code tolerates surrounding whitespace."""
    assert TradeStatus.from_code(' И ') is TradeStatus.I


# ---------------------------------------------------------------------------
# parse_trades - structural tests
# ---------------------------------------------------------------------------


def test_parse_trades_returns_trades(soup: BeautifulSoup) -> None:
    """parse_trades returns a populated Trades object."""
    result = parse_trades(soup)
    assert result is not None
    assert isinstance(result, Trades)


def test_parse_trades_returns_none_if_table_missing() -> None:
    """parse_trades returns None when the table is absent."""
    empty_soup = BeautifulSoup('<html><body><p>No table here</p></body></html>', 'lxml')
    assert parse_trades(empty_soup) is None


def test_parse_trades_has_10_rows(soup: BeautifulSoup) -> None:
    """The sample contains exactly 10 trade rows."""
    result = parse_trades(soup)
    assert result is not None
    assert len(result.rows) == 10


def test_all_rows_are_buy(soup: BeautifulSoup) -> None:
    """All 10 sample trades are BUY."""
    result = parse_trades(soup)
    assert result is not None
    assert all(tr.direction is TradeDirection.BUY for tr in result.rows)


def test_all_rows_venue_fondovy_rinok(soup: BeautifulSoup) -> None:
    """All rows carry the section-row venue 'Фондовый рынок'."""
    result = parse_trades(soup)
    assert result is not None
    for tr in result.rows:
        assert tr.venue == 'Фондовый рынок'


# ---------------------------------------------------------------------------
# parse_trades - first row exact-value tests (from plan)
# ---------------------------------------------------------------------------


def test_first_row_exact_values(soup: BeautifulSoup) -> None:
    """Trade 1 matches the exact values documented in the plan."""
    result = parse_trades(soup)
    assert result is not None
    r = result.rows[0]
    assert isinstance(r, Trade)
    assert r.trade_date == date(2024, 1, 8)
    assert r.settlement_date == date(2024, 1, 9)
    assert r.trade_time == time(11, 3, 38)
    assert r.security_name == 'Облигация Е'
    assert r.security_code == 'RU000TEST006'
    assert r.currency == 'RUB'
    assert r.direction is TradeDirection.BUY
    assert r.quantity == 50
    assert r.price == Decimal('96.93')
    assert r.amount == Decimal('48465.00')
    assert r.nkd == Decimal('800.17')
    assert r.broker_fee == Decimal('29.08')
    assert r.exchange_fee == Decimal('6.05')
    assert r.trade_number == '10000000001'
    assert r.comment is None
    assert r.status is TradeStatus.I
    assert r.status.name == 'I'
    assert r.venue == 'Фондовый рынок'


def test_row_types(soup: BeautifulSoup) -> None:
    """All typed fields use the correct Python types."""
    result = parse_trades(soup)
    assert result is not None
    for r in result.rows:
        assert isinstance(r.trade_date, date)
        assert isinstance(r.settlement_date, date)
        assert isinstance(r.trade_time, time)
        assert isinstance(r.quantity, int)
        assert isinstance(r.price, Decimal)
        assert isinstance(r.amount, Decimal)
        assert isinstance(r.nkd, Decimal)
        assert isinstance(r.broker_fee, Decimal)
        assert isinstance(r.exchange_fee, Decimal)
        assert isinstance(r.direction, TradeDirection)
        assert isinstance(r.status, TradeStatus)


def test_empty_comment_becomes_none(soup: BeautifulSoup) -> None:
    """Empty comment cell must map to None (not empty string)."""
    result = parse_trades(soup)
    assert result is not None
    for r in result.rows:
        assert r.comment is None


def test_trade_numbers_unique_and_ordered(soup: BeautifulSoup) -> None:
    """Trade numbers match the sample's sequence 10000000001..10000000010."""
    result = parse_trades(soup)
    assert result is not None
    numbers = [r.trade_number for r in result.rows]
    expected = [f'1000000000{i}' for i in range(1, 10)] + ['10000000010']
    assert numbers == expected


def test_tenth_row_values(soup: BeautifulSoup) -> None:
    """The 10th trade (index 9) matches the sample."""
    result = parse_trades(soup)
    assert result is not None
    r = result.rows[9]
    assert r.trade_date == date(2024, 1, 28)
    assert r.settlement_date == date(2024, 1, 29)
    assert r.security_name == 'Облигация А'
    assert r.security_code == 'RU000TEST001'
    assert r.quantity == 1
    assert r.price == Decimal('104.14')
    assert r.amount == Decimal('1041.40')


# ---------------------------------------------------------------------------
# TradesTotal tests
# ---------------------------------------------------------------------------


def test_total_values(soup: BeautifulSoup) -> None:
    """The summary row 'Итого, RUB' maps to TradesTotal with exact values."""
    result = parse_trades(soup)
    assert result is not None
    assert result.total is not None
    assert isinstance(result.total, TradesTotal)
    assert result.total.amount == Decimal('312797.65')
    assert result.total.nkd == Decimal('1570.07')
    assert result.total.broker_fee == Decimal('182.08')
    assert result.total.exchange_fee == Decimal('36.50')


def test_total_amount_matches_sum_of_rows(soup: BeautifulSoup) -> None:
    """Sanity: total amount equals sum of per-row amounts."""
    result = parse_trades(soup)
    assert result is not None
    assert result.total is not None
    summed = sum(
        (r.amount for r in result.rows if r.amount is not None),
        Decimal('0'),
    )
    assert summed == result.total.amount


# ---------------------------------------------------------------------------
# Dataclass immutability
# ---------------------------------------------------------------------------


def test_all_dataclasses_are_frozen(soup: BeautifulSoup) -> None:
    """All public dataclasses must be frozen."""
    result = parse_trades(soup)
    assert result is not None

    with pytest.raises(FrozenInstanceError):
        setattr(result, 'rows', [])
    with pytest.raises(FrozenInstanceError):
        setattr(result, 'total', None)

    first = result.rows[0]
    with pytest.raises(FrozenInstanceError):
        setattr(first, 'quantity', 999)

    if result.total is not None:
        with pytest.raises(FrozenInstanceError):
            setattr(result.total, 'amount', Decimal('0'))
