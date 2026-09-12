"""Destination-independent financial facts and balanced accounting records."""

from dataclasses import dataclass
from datetime import date as Date
from decimal import Decimal
from enum import StrEnum

ZERO = Decimal(0)


class EventKind(StrEnum):
    """Supported economic events, independent of ledger serialization."""

    BUY = 'buy'
    TRANSFER = 'transfer'
    BROKER_FEE = 'broker_fee'
    EXCHANGE_FEE = 'exchange_fee'
    COUPON = 'coupon'
    PRINCIPAL = 'principal_repayment'


class Role(StrEnum):
    """Logical accounting roles resolved only at the destination boundary."""

    CASH = 'cash'
    EXTERNAL = 'external'
    BOND = 'bond'
    NKD = 'nkd'
    FEES = 'fees'
    INCOME = 'income'


@dataclass(frozen=True)
class SecurityPosition:
    """Source opening/closing holdings; market prices are deliberately excluded."""

    isin: str
    code: str
    name: str
    opening_quantity: Decimal
    closing_quantity: Decimal
    opening_nkd: Decimal
    closing_nkd: Decimal
    opening_nominal: Decimal
    closing_nominal: Decimal


@dataclass(frozen=True)
class FinancialEvent:
    """A dated economic fact with its original statement-row provenance."""

    id: str
    kind: EventKind
    date: Date
    amount: Decimal
    source_rows: tuple[str, ...]
    description: str
    security: str = ''
    quantity: Decimal = ZERO
    nkd: Decimal = ZERO
    trade_date: Date | None = None
    trade_number: str = ''
    quoted_price: Decimal | None = None
    broker_fee: Decimal = ZERO
    exchange_fee: Decimal = ZERO


@dataclass(frozen=True)
class Statement:
    """Reconciled RUB statement suitable for multiple accounting backends."""

    id: str
    source_id: str
    start: Date
    end: Date
    opening_cash: Decimal
    closing_cash: Decimal
    securities: tuple[SecurityPosition, ...]
    events: tuple[FinancialEvent, ...]


@dataclass(frozen=True)
class Holding:
    """Opening inventory from the ledger, including its recorded principal value."""

    security: str
    quantity: Decimal
    value: Decimal
    nkd: Decimal


@dataclass(frozen=True)
class OpeningState:
    """Explicit book balances immediately before the statement period."""

    cash: Decimal
    holdings: tuple[Holding, ...]


@dataclass(frozen=True)
class Posting:
    """Signed quantity in a commodity and signed value in transaction currency."""

    role: Role
    quantity: Decimal
    value: Decimal
    commodity: str = 'RUB'
    security: str = ''


@dataclass(frozen=True)
class JournalEntry:
    """Balanced transaction with stable provenance, not a GnuCash transaction."""

    id: str
    date: Date
    description: str
    source_rows: tuple[str, ...]
    postings: tuple[Posting, ...]


@dataclass(frozen=True)
class Journal:
    """Deterministic journal and expected closing inventory."""

    statement: Statement
    entries: tuple[JournalEntry, ...]
    closing: OpeningState
