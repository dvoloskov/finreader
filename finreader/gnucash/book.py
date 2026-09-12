"""Read closed GnuCash SQLite and XML snapshots without opening a writable session."""

from dataclasses import dataclass
from contextlib import closing
from datetime import date
from decimal import Decimal
import gzip
from pathlib import Path
import sqlite3
from typing import cast
from xml.etree import ElementTree as ET

from finreader.validation import exact_arithmetic, require

NS = {
    prefix: f'http://www.gnucash.org/XML/{prefix}'
    for prefix in ('gnc', 'act', 'cmdty', 'trn', 'split', 'ts', 'slot')
}


@dataclass(frozen=True)
class Commodity:
    """Native commodity identity and precision."""

    key: str
    cusip: str
    fraction: int


@dataclass(frozen=True)
class Account:
    """Resolved account identity, path and permitted quantity denominator."""

    id: str
    path: str
    type: str
    commodity: str
    fraction: int
    placeholder: bool = False


@dataclass(frozen=True)
class Split:
    """A native split with independently stored quantity and value."""

    account: str
    quantity: Decimal
    value: Decimal


@dataclass(frozen=True)
class Transaction:
    """Native transaction facts used for preflight and readback."""

    id: str
    date: date
    currency: str
    description: str
    notes: str
    splits: tuple[Split, ...]


@dataclass(frozen=True)
class Book:
    """Immutable read-only projection; never a writer for the user's ledger."""

    accounts: tuple[Account, ...]
    commodities: tuple[Commodity, ...]
    transactions: tuple[Transaction, ...]


def _accounts(
    rows: list[tuple[str, str, str, str, int, str, bool]],
) -> tuple[Account, ...]:
    by_id = {r[0]: r for r in rows}
    require(len(by_id) == len(rows), 'Duplicate account GUID')
    resolved: dict[str, str] = {}

    def path(guid: str, visiting: frozenset[str]) -> str:
        require(
            guid in by_id and guid not in visiting,
            'Missing parent or cycle in account tree',
        )
        if guid in resolved:
            return resolved[guid]
        _, name, kind, _, _, parent, _ = by_id[guid]
        if kind == 'ROOT':
            result = ''
        else:
            require(
                bool(name) and ':' not in name,
                'Account name contains an unsupported path separator',
            )
            prefix = path(parent, visiting | {guid})
            result = f'{prefix}:{name}' if prefix else name
        resolved[guid] = result
        return result

    result = tuple(
        Account(guid, path(guid, frozenset()), kind, commodity, fraction, placeholder)
        for guid, _, kind, commodity, fraction, _, placeholder in rows
    )
    require(
        len({a.path for a in result}) == len(result),
        'Ambiguous duplicate account paths',
    )
    return result


def _rational(numerator: int, denominator: int) -> Decimal:
    require(denominator > 0, 'Invalid book amount denominator')
    return Decimal(numerator) / Decimal(denominator)


def _query(connection: sqlite3.Connection, sql: str) -> list[dict[str, str]]:
    """Narrow dynamically typed DB-API values at the storage boundary."""
    cursor = connection.execute(sql)
    columns = [c[0] for c in cast(list[tuple[str, ...]], cursor.description)]
    rows = cast(list[tuple[object, ...]], cursor.fetchall())
    return [
        dict(zip(columns, ('' if v is None else str(v) for v in row), strict=True))
        for row in rows
    ]


def _sqlite(path: Path) -> Book:
    with closing(
        sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)
    ) as connection:
        _ = connection.execute('PRAGMA query_only=ON')
        commodities: list[Commodity] = []
        keys: dict[str, str] = {}
        for row in _query(
            connection,
            'SELECT guid, namespace, mnemonic, cusip, fraction FROM commodities',
        ):
            key = f'{row["namespace"]}::{row["mnemonic"]}'
            keys[str(row['guid'])] = key
            commodities.append(
                Commodity(key, str(row['cusip'] or ''), int(row['fraction']))
            )
        placeholders = {
            row['obj_guid']
            for row in _query(
                connection,
                "SELECT obj_guid FROM slots WHERE name='placeholder' AND string_val='true'",
            )
        }
        rows = [
            (
                str(r['guid']),
                str(r['name']),
                str(r['account_type']),
                keys.get(str(r['commodity_guid']), ''),
                int(r['commodity_scu']),
                str(r['parent_guid'] or ''),
                str(r['guid']) in placeholders,
            )
            for r in _query(connection, 'SELECT * FROM accounts')
        ]
        accounts = _accounts(rows)
        paths = {a.id: a.path for a in accounts}
        splits: dict[str, list[Split]] = {}
        for r in _query(
            connection,
            'SELECT tx_guid, account_guid, quantity_num, quantity_denom, value_num, value_denom FROM splits',
        ):
            account_id = str(r['account_guid'])
            require(account_id in paths, 'Split references an unknown account')
            splits.setdefault(str(r['tx_guid']), []).append(
                Split(
                    paths[account_id],
                    _rational(int(r['quantity_num']), int(r['quantity_denom'])),
                    _rational(int(r['value_num']), int(r['value_denom'])),
                )
            )
        notes: dict[str, str] = {}
        for row in _query(
            connection, "SELECT obj_guid, string_val FROM slots WHERE name='notes'"
        ):
            require(row['obj_guid'] not in notes, 'Duplicate transaction notes slots')
            notes[row['obj_guid']] = row['string_val']
        transactions: list[Transaction] = []
        for r in _query(
            connection,
            'SELECT guid, currency_guid, post_date, description FROM transactions',
        ):
            guid = str(r['guid'])
            # SQL backend timestamps are UTC strings; the first date is the
            # posted civil date (GnuCash uses neutral daytime timestamps).
            text = str(r['post_date'])
            day = date.fromisoformat(
                text[:10] if '-' in text[:10] else f'{text[:4]}-{text[4:6]}-{text[6:8]}'
            )
            transactions.append(
                Transaction(
                    guid,
                    day,
                    keys[str(r['currency_guid'])],
                    str(r['description'] or ''),
                    notes.get(guid, ''),
                    tuple(splits.pop(guid, [])),
                )
            )
        require(not splits, 'Orphan book splits')
    return Book(accounts, tuple(commodities), tuple(transactions))


def _text(node: ET.Element, path: str, default: str | None = None) -> str:
    value = node.findtext(path, namespaces=NS)
    if value is None:
        require(default is not None, f'Missing XML field: {path}')
        return default or ''
    return value


def _commodity(node: ET.Element, path: str) -> str:
    element = node.find(path, NS)
    if element is None:
        return ''
    return _text(element, 'cmdty:space') + '::' + _text(element, 'cmdty:id')


def _slots(node: ET.Element, path: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for slot in node.findall(path + '/slot', NS):
        key = _text(slot, 'slot:key')
        if key in ('notes', 'placeholder'):
            require(key not in result, f'Duplicate XML slot: {key}')
            result[key] = _text(slot, 'slot:value', '')
    return result


def _xml(data: bytes) -> Book:
    require(
        b'<!DOCTYPE' not in data.upper() and b'<!ENTITY' not in data.upper(),
        'XML DTD/entities are not supported',
    )
    require(b'\x00' not in data, 'Only UTF-8 XML snapshots are supported')
    root = ET.fromstring(data)
    commodities = [
        Commodity(
            _text(c, 'cmdty:space') + '::' + _text(c, 'cmdty:id'),
            _text(c, 'cmdty:xcode', ''),
            int(_text(c, 'cmdty:fraction')),
        )
        for c in root.findall('.//gnc:commodity', NS)
        # GnuCash may write only quote settings for built-in currencies, without
        # a fraction. Resolve these from currency accounts below, just like
        # currencies that have no standalone definition at all.
        if _text(c, 'cmdty:space') != 'CURRENCY'
        or c.find('cmdty:fraction', NS) is not None
    ]
    rows = [
        (
            _text(a, 'act:id'),
            _text(a, 'act:name'),
            _text(a, 'act:type'),
            _commodity(a, 'act:commodity'),
            int(_text(a, 'act:commodity-scu', '0')),
            _text(a, 'act:parent', ''),
            _slots(a, 'act:slots').get('placeholder') == 'true',
        )
        for a in root.findall('.//gnc:account', NS)
    ]
    accounts = _accounts(rows)
    require(bool(accounts), 'No GnuCash accounts found')
    paths = {a.id: a.path for a in accounts}
    # Built-in currencies need not have standalone XML commodity definitions.
    known = {c.key for c in commodities}
    for account in accounts:
        if (
            account.commodity.startswith('CURRENCY::')
            and account.commodity not in known
        ):
            commodities.append(Commodity(account.commodity, '', account.fraction))
            known.add(account.commodity)
    transactions: list[Transaction] = []
    for t in root.findall('.//gnc:transaction', NS):
        splits: list[Split] = []
        for s in t.findall('trn:splits/trn:split', NS):
            account_id = _text(s, 'split:account')
            require(account_id in paths, 'Split references an unknown account')

            def rational(field: str) -> Decimal:
                parts = _text(s, field).split('/')
                require(len(parts) == 2, f'Invalid XML rational: {field}')
                return _rational(int(parts[0]), int(parts[1]))

            splits.append(
                Split(
                    paths[account_id],
                    rational('split:quantity'),
                    rational('split:value'),
                )
            )
        transactions.append(
            Transaction(
                _text(t, 'trn:id'),
                date.fromisoformat(_text(t, 'trn:date-posted/ts:date')[:10]),
                _commodity(t, 'trn:currency'),
                _text(t, 'trn:description', ''),
                _slots(t, 'trn:slots').get('notes', ''),
                tuple(splits),
            )
        )
    return Book(accounts, tuple(commodities), tuple(transactions))


@exact_arithmetic
def read_book(path: str | Path) -> Book:
    """Read a closed snapshot, rejecting active lock/WAL files and malformed books."""
    path = Path(path).resolve(strict=True)
    for suffix in ('.LCK', '.LNK', '-wal', '-shm', '-journal'):
        require(
            not Path(str(path) + suffix).exists(),
            f'Book appears open; use a closed snapshot ({suffix})',
        )
    with path.open('rb') as stream:
        magic = stream.read(16)
    if magic.startswith(b'SQLite format 3'):
        book = _sqlite(path)
    else:
        opener = gzip.open if magic.startswith(b'\x1f\x8b') else open
        with opener(path, 'rb') as stream:
            data = stream.read(128 * 1024 * 1024 + 1)
        require(len(data) <= 128 * 1024 * 1024, 'XML snapshot exceeds 128 MiB')
        book = _xml(data)
    require(
        len({t.id for t in book.transactions}) == len(book.transactions),
        'Duplicate transaction GUID',
    )
    require(
        len({c.key for c in book.commodities}) == len(book.commodities),
        'Duplicate commodity identity',
    )
    return book
