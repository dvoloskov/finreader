"""Validated native CSV export and independent saved-book verification."""

from collections import Counter
from dataclasses import asdict, dataclass, replace
from datetime import date
from decimal import Decimal
import csv
import hashlib
import io
import json
import os
from pathlib import Path
from typing import cast

from finreader.accounting import build_journal
from finreader.gnucash.book import Account, Book, Split, Transaction, read_book
from finreader.gnucash.mapping import Mapping, load_mapping, validate_mapping
from finreader.models import Holding, OpeningState, ZERO
from finreader.parsers.sberbank.brokerage_report import parse
from finreader.sberbank import normalize_sberbank
from finreader.validation import exact_arithmetic, require

PREFIX = 'finreader:v1|'
CSV_HEADER = (
    'Date',
    'Transaction ID',
    'Number',
    'Description',
    'Notes',
    'Commodity/Currency',
    'Void Reason',
    'Action',
    'Memo',
    'Full Account Name',
    'Account Name',
    'Amount With Sym',
    'Amount Num.',
    'Value With Sym',
    'Value Num.',
    'Reconcile',
    'Reconcile Date',
    'Rate/Price',
)


@dataclass(frozen=True)
class Manifest:
    """Expected import results tied to account GUIDs and opening balances."""

    report_id: str
    source_id: str
    start: date
    end: date
    broker_root: str
    accounts: tuple[Account, ...]
    opening: tuple[Split, ...]
    closing: tuple[Split, ...]
    transactions: tuple[Transaction, ...]


@dataclass(frozen=True)
class ExportResult:
    """Export outcome; an exact verified repeat does not write files."""

    already_imported: bool
    transactions: int
    csv_path: Path | None = None
    manifest_path: Path | None = None


def _balances(
    book: Book, accounts: tuple[Account, ...], end: date, before: bool = False
) -> tuple[Split, ...]:
    selected = {a.path: a for a in accounts}
    quantities = dict.fromkeys(selected, ZERO)
    values = dict.fromkeys(selected, ZERO)
    for t in book.transactions:
        if t.date > end or (before and t.date == end):
            continue
        for s in t.splits:
            if s.account not in selected:
                continue
            quantities[s.account] += s.quantity
            # Currency-account balances are in their own commodity, even when
            # an old transaction was expressed in a different currency.
            if selected[s.account].commodity == 'CURRENCY::RUB':
                values[s.account] += s.quantity
            else:
                require(
                    t.currency == 'CURRENCY::RUB',
                    'Opening bond basis contains non-RUB transactions',
                )
                values[s.account] += s.value
    return tuple(Split(a.path, quantities[a.path], values[a.path]) for a in accounts)


def _notes_key(notes: str) -> str:
    # GnuCash 5.14 flattens CSV note line breaks to spaces on import.
    # Do not ignore missing provenance or any other content differences.
    return notes.replace('\r\n', '\n').replace('\n', ' ')


def _marker(notes: str) -> tuple[str, date, date, str, str] | None:
    if not notes.startswith(PREFIX):
        return None
    parts = _notes_key(notes).partition(' source: ')[0].split('|')
    require(len(parts) == 6, 'Malformed finreader import marker')
    _, source, start, end, report, event = parts
    require(
        len(source) == len(report) == 64 and bool(event), 'Malformed finreader identity'
    )
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    require(first <= last, 'Invalid marker period')
    return source, first, last, report, event


def _split_key(split: Split) -> tuple[str, Decimal, Decimal]:
    return split.account, split.quantity, split.value


def _match_transactions(book: Book, manifest: Manifest) -> None:
    expected = {_notes_key(t.notes): t for t in manifest.transactions}
    require(len(expected) == len(manifest.transactions), 'Duplicate expected marker')
    actual: dict[str, Transaction] = {}
    for t in book.transactions:
        marker = _marker(t.notes)
        if (
            marker is not None
            and marker[0] == manifest.source_id
            and marker[3] == manifest.report_id
        ):
            require(_notes_key(t.notes) not in actual, 'Duplicate imported event')
            actual[_notes_key(t.notes)] = t
        if manifest.start <= t.date <= manifest.end and any(
            s.account.startswith(manifest.broker_root + ':') for s in t.splits
        ):
            require(
                _notes_key(t.notes) in expected,
                'Conflicting or unmarked broker transaction in statement period',
            )
    require(
        set(actual) == set(expected), 'Partial, missing or unexpected imported events'
    )
    for notes, wanted in expected.items():
        got = actual[notes]
        require(
            (got.date, got.currency, got.description)
            == (wanted.date, wanted.currency, wanted.description),
            'Imported transaction metadata differs',
        )
        require(
            Counter(map(_split_key, got.splits))
            == Counter(map(_split_key, wanted.splits)),
            'Imported split accounts/quantities/values differ',
        )


@exact_arithmetic
def verify_book(book: Book, manifest: Manifest) -> None:
    """Verify saved transactions and opening/closing balances without mutating a book."""
    accounts = {a.path: a for a in book.accounts}
    for expected in manifest.accounts:
        require(
            accounts.get(expected.path) == expected,
            f'Book/account identity differs: {expected.path}',
        )
    require(
        _balances(book, manifest.accounts, manifest.start, before=True)
        == manifest.opening,
        'Opening balances changed since export',
    )
    _match_transactions(book, manifest)
    require(
        _balances(book, manifest.accounts, manifest.end) == manifest.closing,
        'Closing balances differ from manifest',
    )


@exact_arithmetic
def prepare_export(
    report_path: str | Path, book: Book, mapping: Mapping
) -> tuple[Manifest, bool]:
    """Reconcile, map and preflight a report entirely in memory before writing output."""
    statement = normalize_sberbank(parse(report_path))
    validate_mapping(mapping, book, statement)
    mapped_paths = {
        mapping.cash,
        mapping.external,
        mapping.fees,
        mapping.income,
        *(s.bond for s in mapping.securities),
        *(s.nkd for s in mapping.securities),
    }
    accounts = tuple(
        sorted(
            (a for a in book.accounts if a.path in mapped_paths), key=lambda a: a.path
        )
    )
    opening_splits = _balances(book, accounts, statement.start, before=True)
    opening_by_path = {s.account: s for s in opening_splits}
    opening = OpeningState(
        opening_by_path[mapping.cash].quantity,
        tuple(
            Holding(
                s.isin,
                opening_by_path[s.bond].quantity,
                opening_by_path[s.bond].value,
                opening_by_path[s.nkd].quantity,
            )
            for s in mapping.securities
        ),
    )
    journal = build_journal(statement, opening)
    expected: list[Transaction] = []
    by_path = {a.path: a for a in accounts}
    for entry in journal.entries:
        require(
            not any(c in entry.id for c in ('|', '\n', '\r')),
            'Unsupported separator in event identity',
        )
        notes = (
            f'{PREFIX}{statement.source_id}|{statement.start}|{statement.end}|{statement.id}|{entry.id}\nsource: '
            + ', '.join(entry.source_rows)
        )
        splits: list[Split] = []
        for posting in entry.postings:
            path = mapping.account(posting)
            quantity, value = posting.quantity, posting.value
            require(
                quantity * by_path[path].fraction
                == (quantity * by_path[path].fraction).to_integral_value(),
                f'Quantity exceeds account precision: {path}',
            )
            require(
                value * 100 == (value * 100).to_integral_value(),
                'RUB amount exceeds kopeck precision',
            )
            require(
                abs(quantity * by_path[path].fraction) <= 9223372036854775807
                and abs(value * 100) <= 9223372036854775807,
                'Amount exceeds GnuCash signed 64-bit numeric range',
            )
            splits.append(Split(path, quantity, value))
        expected.append(
            Transaction(
                hashlib.sha256(entry.id.encode()).hexdigest()[:32],
                entry.date,
                'CURRENCY::RUB',
                entry.description,
                notes,
                tuple(splits),
            )
        )
    # Preserve pre-existing activity in external funding/income/expense accounts.
    # On a verified repeat, remove only this report's marked transactions from
    # the baseline before adding the expected journal again.
    baseline = replace(
        book,
        transactions=tuple(
            t
            for t in book.transactions
            if not (
                (marker := _marker(t.notes)) is not None
                and marker[0] == statement.source_id
                and marker[3] == statement.id
            )
        ),
    )
    closing = {s.account: s for s in _balances(baseline, accounts, statement.end)}
    for t in expected:
        for s in t.splits:
            previous = closing[s.account]
            closing[s.account] = Split(
                s.account, previous.quantity + s.quantity, previous.value + s.value
            )
    manifest = Manifest(
        statement.id,
        statement.source_id,
        statement.start,
        statement.end,
        mapping.broker_root,
        accounts,
        opening_splits,
        tuple(closing[a.path] for a in accounts),
        tuple(expected),
    )
    imported = False
    for t in book.transactions:
        touches_broker = any(
            s.account.startswith(mapping.broker_root + ':') for s in t.splits
        )
        marker = _marker(t.notes)
        if touches_broker and marker is not None:
            source, first, last, report_id, _ = marker
            require(
                source == statement.source_id,
                'Broker contains another source-contract import',
            )
            require(
                first <= t.date <= last, 'Imported marker does not match posting date'
            )
            if report_id == statement.id:
                require(
                    (first, last) == (statement.start, statement.end),
                    'Imported report period changed',
                )
                imported = True
            else:
                require(
                    last < statement.start,
                    'Overlapping/corrected or out-of-order statement',
                )
        if touches_broker and t.date >= statement.start:
            require(
                marker is not None and marker[3] == statement.id,
                'Existing broker activity conflicts; only sequential empty periods can be imported',
            )
    if imported:
        verify_book(book, manifest)
    return manifest, imported


def render_csv(manifest: Manifest) -> str:
    """Render GnuCash 5 native 18-column CSV with exact quantity/value columns."""
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, lineterminator='\n')
    writer.writerow(CSV_HEADER)
    for t in manifest.transactions:
        for s in t.splits:
            writer.writerow(
                (
                    t.date.isoformat(),
                    t.id,
                    '',
                    t.description,
                    _notes_key(t.notes),
                    t.currency,
                    '',
                    '',
                    '',
                    s.account,
                    '',
                    '',
                    format(s.quantity, 'f'),
                    '',
                    format(s.value, 'f'),
                    'n',
                    '',
                    '',
                )
            )
    return stream.getvalue()


def _json_default(value: object) -> str:
    if isinstance(value, (date, Decimal)):
        return str(value)
    raise TypeError(type(value).__name__)


def render_manifest(manifest: Manifest) -> str:
    """Serialize exact decimal strings and a versioned readback contract."""
    return (
        json.dumps(
            {'version': 1, **asdict(manifest)},
            default=_json_default,
            ensure_ascii=False,
            indent=2,
        )
        + '\n'
    )


def _object(value: object) -> dict[str, object]:
    require(isinstance(value, dict), 'Manifest object expected')
    return cast(dict[str, object], value)


def _string(value: object) -> str:
    require(isinstance(value, str), 'Manifest string expected')
    return cast(str, value)


def _list(value: object) -> list[object]:
    require(isinstance(value, list), 'Manifest list expected')
    return cast(list[object], value)


def _decimal(value: object) -> Decimal:
    number = Decimal(_string(value))
    require(number.is_finite(), 'Non-finite manifest amount')
    return number


def _split(value: object) -> Split:
    row = _object(value)
    return Split(
        _string(row['account']), _decimal(row['quantity']), _decimal(row['value'])
    )


def load_manifest(path: str | Path) -> Manifest:
    """Load a versioned manifest without float conversion."""
    data = _object(cast(object, json.loads(Path(path).read_text(encoding='utf-8'))))
    require(
        type(data['version']) is int and data['version'] == 1,
        'Unsupported manifest version',
    )
    accounts: list[Account] = []
    for raw in _list(data['accounts']):
        a = _object(raw)
        require(
            type(a['fraction']) is int and type(a['placeholder']) is bool,
            'Invalid account precision/placeholder flag',
        )
        accounts.append(
            Account(
                _string(a['id']),
                _string(a['path']),
                _string(a['type']),
                _string(a['commodity']),
                cast(int, a['fraction']),
                cast(bool, a['placeholder']),
            )
        )
    transactions: list[Transaction] = []
    for raw in _list(data['transactions']):
        t = _object(raw)
        transactions.append(
            Transaction(
                _string(t['id']),
                date.fromisoformat(_string(t['date'])),
                _string(t['currency']),
                _string(t['description']),
                _string(t['notes']),
                tuple(_split(s) for s in _list(t['splits'])),
            )
        )
    return Manifest(
        _string(data['report_id']),
        _string(data['source_id']),
        date.fromisoformat(_string(data['start'])),
        date.fromisoformat(_string(data['end'])),
        _string(data['broker_root']),
        tuple(accounts),
        tuple(_split(s) for s in _list(data['opening'])),
        tuple(_split(s) for s in _list(data['closing'])),
        tuple(transactions),
    )


def export_report(
    report_path: str | Path,
    book_path: str | Path,
    mapping_path: str | Path,
    output: str | Path,
) -> ExportResult:
    """Write a validated CSV/manifest pair exclusively; never overwrite existing files."""
    output = Path(output)
    manifest_path = output.with_suffix(output.suffix + '.manifest.json')
    manifest, imported = prepare_export(
        report_path, read_book(book_path), load_mapping(mapping_path)
    )
    if imported:
        return ExportResult(True, len(manifest.transactions))
    # Both contents are fully validated/rendered before opening any destination.
    csv_content, json_content = render_csv(manifest), render_manifest(manifest)
    require(
        not output.exists() and not manifest_path.exists(),
        'Output already exists; choose a new output path',
    )
    # Exclusive creation also protects against symlinks and check/write races.
    created: list[Path] = []
    try:
        for path, content in ((manifest_path, json_content), (output, csv_content)):
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'w', encoding='utf-8', newline='') as stream:
                created.append(path)
                _ = stream.write(content)
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return ExportResult(False, len(manifest.transactions), output, manifest_path)
