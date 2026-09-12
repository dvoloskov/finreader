"""GnuCash adapter contract tests; simulated readback is not GUI acceptance."""

import csv
from dataclasses import replace
from datetime import date
from decimal import Decimal
import gzip
import io
from pathlib import Path
import sqlite3

import pytest

from finreader.__main__ import main
from finreader.gnucash.book import Account, Book, Split, Transaction, read_book
from finreader.gnucash.export import (
    Manifest,
    export_report,
    load_manifest,
    prepare_export,
    render_csv,
    render_manifest,
    verify_book,
)
from finreader.gnucash.mapping import Mapping, load_mapping
from finreader.validation import ReconciliationError

REPORT = Path('tests/data/sberbank_report_coherent.html')
BOOK = Path('tests/data/gnucash/opening.gnucash')
MAPPING = Path('tests/data/gnucash/mapping.toml')
D = Decimal


@pytest.fixture
def book() -> Book:
    """Read a fully synthetic native XML opening book."""
    return read_book(BOOK)


@pytest.fixture
def mapping() -> Mapping:
    """Read synthetic explicit account mappings."""
    return load_mapping(MAPPING)


@pytest.fixture
def manifest(book: Book, mapping: Mapping) -> Manifest:
    """Prepare expected output through the public boundary."""
    result, imported = prepare_export(REPORT, book, mapping)
    assert not imported
    return result


def save_sqlite(book: Book, path: Path) -> None:
    """Write test-only backend tables, never a production book writer."""
    with sqlite3.connect(path) as connection:
        _ = connection.executescript("""
            CREATE TABLE commodities (guid TEXT, namespace TEXT, mnemonic TEXT, cusip TEXT, fraction INTEGER);
            CREATE TABLE accounts (guid TEXT, name TEXT, account_type TEXT, commodity_guid TEXT, commodity_scu INTEGER, parent_guid TEXT);
            CREATE TABLE transactions (guid TEXT, currency_guid TEXT, post_date TEXT, description TEXT);
            CREATE TABLE splits (tx_guid TEXT, account_guid TEXT, quantity_num INTEGER, quantity_denom INTEGER, value_num INTEGER, value_denom INTEGER);
            CREATE TABLE slots (obj_guid TEXT, name TEXT, string_val TEXT);
        """)
        for c in book.commodities:
            namespace, mnemonic = c.key.split('::')
            _ = connection.execute(
                'INSERT INTO commodities VALUES (?,?,?,?,?)',
                (c.key, namespace, mnemonic, c.cusip, c.fraction),
            )
        accounts = {a.path: a for a in book.accounts}
        for a in book.accounts:
            parent = accounts[a.path.rpartition(':')[0]].id if a.path else ''
            _ = connection.execute(
                'INSERT INTO accounts VALUES (?,?,?,?,?,?)',
                (
                    a.id,
                    a.path.split(':')[-1] or 'Root Account',
                    a.type,
                    a.commodity,
                    a.fraction,
                    parent,
                ),
            )
            if a.placeholder:
                _ = connection.execute(
                    'INSERT INTO slots VALUES (?,?,?)', (a.id, 'placeholder', 'true')
                )
        for t in book.transactions:
            _ = connection.execute(
                'INSERT INTO transactions VALUES (?,?,?,?)',
                (t.id, t.currency, str(t.date) + ' 12:00:00', t.description),
            )
            if t.notes:
                _ = connection.execute(
                    'INSERT INTO slots VALUES (?,?,?)', (t.id, 'notes', t.notes)
                )
            for s in t.splits:
                _ = connection.execute(
                    'INSERT INTO splits VALUES (?,?,?,?,?,?)',
                    (
                        t.id,
                        accounts[s.account].id,
                        *s.quantity.as_integer_ratio(),
                        *s.value.as_integer_ratio(),
                    ),
                )


def test_reader_formats_and_no_writes(book: Book, tmp_path: Path) -> None:
    """XML, gzip and SQLite yield the same immutable facts without sidecars."""
    xml_before = BOOK.read_bytes()
    zipped = tmp_path / 'book.gz'
    _ = zipped.write_bytes(gzip.compress(xml_before))
    assert read_book(zipped) == book
    database = tmp_path / 'book.sqlite'
    save_sqlite(book, database)
    before = database.read_bytes()
    assert read_book(database) == book
    assert database.read_bytes() == before and BOOK.read_bytes() == xml_before
    assert {p.name for p in tmp_path.iterdir()} == {'book.gz', 'book.sqlite'}


@pytest.mark.parametrize('suffix', ['.LCK', '.LNK', '-wal', '-shm', '-journal'])
def test_reject_open_snapshot(tmp_path: Path, suffix: str) -> None:
    """Do not read an active database as if it were a closed snapshot."""
    path = tmp_path / 'book'
    _ = path.write_bytes(BOOK.read_bytes())
    _ = Path(str(path) + suffix).write_text('locked')
    with pytest.raises(ReconciliationError, match='closed snapshot'):
        _ = read_book(path)


def test_xml_entities_rejected(tmp_path: Path) -> None:
    """Do not resolve entity declarations from imported books."""
    path = tmp_path / 'bad.xml'
    _ = path.write_text('<!DOCTYPE foo [<!ENTITY a "x">]><foo>&a;</foo>')
    with pytest.raises(ReconciliationError, match='DTD/entities'):
        _ = read_book(path)


def test_csv_schema_values_and_escaping(manifest: Manifest) -> None:
    """Native amount/value columns preserve zero-quantity basis adjustments."""
    t = replace(
        manifest.transactions[0], description='Quoted "text", Unicode НКД\nsecond line'
    )
    content = render_csv(
        replace(manifest, transactions=(t, *manifest.transactions[1:]))
    )
    assert '\r' not in content and content.endswith('\n')
    rows = list(csv.DictReader(io.StringIO(content)))
    assert len(rows[0]) == 18 and rows[0]['Description'] == t.description
    assert rows[0]['Commodity/Currency'] == 'CURRENCY::RUB'
    adjustments = [
        r for r in rows if r['Amount Num.'] == '0' and r['Value Num.'] == '-3000'
    ]
    assert len(adjustments) == 1
    assert adjustments[0]['Full Account Name'] == 'Assets:Broker:Облигация А'
    assert len({r['Transaction ID'] for r in rows}) == 8
    assert all(r['Notes'].startswith('finreader:v1|') for r in rows)


def test_manifest_roundtrip(manifest: Manifest, tmp_path: Path) -> None:
    """Versioned JSON stores decimal strings without precision loss."""
    path = tmp_path / 'manifest.json'
    _ = path.write_text(render_manifest(manifest), encoding='utf-8')
    assert load_manifest(path) == manifest


def test_export_readback_and_repeat(
    book: Book, manifest: Manifest, tmp_path: Path
) -> None:
    """Simulate persisted native splits, then verify and suppress repeat exports."""
    output = tmp_path / 'export.csv'
    result = export_report(REPORT, BOOK, MAPPING, output)
    assert not result.already_imported and result.transactions == 8
    assert result.manifest_path is not None
    saved = replace(book, transactions=(*book.transactions, *manifest.transactions))
    database = tmp_path / 'imported.sqlite'
    save_sqlite(saved, database)
    verify_book(read_book(database), load_manifest(result.manifest_path))
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    repeated = export_report(REPORT, database, MAPPING, output)
    assert repeated.already_imported
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize(
    'case',
    [
        'missing',
        'duplicate',
        'quantity',
        'value',
        'account',
        'date',
        'description',
        'notes',
        'opening',
        'identity',
        'unmarked',
    ],
)
def test_readback_detects_corruption(book: Book, manifest: Manifest, case: str) -> None:
    """Do not confuse imported-file acceptance with matching accounting results."""
    entries = list(manifest.transactions)
    t = entries[1]
    split = t.splits[0]
    if case == 'missing':
        _ = entries.pop()
    elif case == 'duplicate':
        entries.append(replace(entries[0], id='different-guid'))
    elif case == 'quantity':
        entries[1] = replace(
            t, splits=(replace(split, quantity=split.quantity + 1), *t.splits[1:])
        )
    elif case == 'value':
        entries[1] = replace(
            t, splits=(replace(split, value=split.value + 1), *t.splits[1:])
        )
    elif case == 'account':
        entries[1] = replace(
            t, splits=(replace(split, account='Assets:Bank'), *t.splits[1:])
        )
    elif case == 'date':
        entries[1] = replace(t, date=date(2024, 2, 1))
    elif case == 'description':
        entries[1] = replace(t, description='Changed')
    elif case == 'notes':
        entries[1] = replace(t, notes='')
    elif case == 'opening':
        original = book.transactions[0]
        first = original.splits[0]
        book = replace(
            book,
            transactions=(
                replace(
                    original,
                    splits=(replace(first, quantity=D(1001)), *original.splits[1:]),
                ),
            ),
        )
    elif case == 'identity':
        accounts = tuple(
            replace(a, id='wrong') if a.path == 'Assets:Bank' else a
            for a in book.accounts
        )
        book = replace(book, accounts=accounts)
    else:
        entries.append(replace(t, id='manual', notes='Manual unrelated correction'))
    with pytest.raises(ReconciliationError):
        verify_book(
            replace(book, transactions=(*book.transactions, *entries)), manifest
        )


@pytest.mark.parametrize('case', ['partial', 'corrected', 'future', 'manual'])
def test_preflight_conflicts(
    book: Book, mapping: Mapping, manifest: Manifest, case: str
) -> None:
    """Refuse partial, overlapping, manual and out-of-order broker activity."""
    t = manifest.transactions[0]
    if case == 'corrected':
        t = replace(t, notes=t.notes.replace(manifest.report_id, 'a' * 64))
    elif case == 'future':
        t = replace(t, date=date(2024, 2, 1), notes='')
    elif case == 'manual':
        t = replace(t, notes='')
    with pytest.raises(ReconciliationError):
        _ = prepare_export(
            REPORT, replace(book, transactions=(*book.transactions, t)), mapping
        )


@pytest.mark.parametrize(
    'case',
    [
        'contract',
        'missing',
        'duplicate',
        'commodity',
        'placeholder',
        'type',
        'precision',
    ],
)
def test_mapping_rejections(book: Book, mapping: Mapping, case: str) -> None:
    """Explicit identity and account precision checks precede any output."""
    if case == 'contract':
        mapping = replace(mapping, contract_code='WRONG')
    elif case == 'missing':
        mapping = replace(mapping, cash='Missing')
    elif case == 'duplicate':
        mapping = replace(mapping, external=mapping.cash)
    elif case == 'commodity':
        sec = replace(mapping.securities[0], commodity='MICEX::UNKNOWN')
        mapping = replace(mapping, securities=(sec,))
    else:
        accounts: list[Account] = []
        for a in book.accounts:
            if a.path == mapping.cash:
                if case == 'placeholder':
                    a = replace(a, placeholder=True)
                elif case == 'type':
                    a = replace(a, type='INCOME')
                else:
                    a = replace(a, fraction=0)
            accounts.append(a)
        book = replace(book, accounts=tuple(accounts))
    with pytest.raises(ReconciliationError):
        _ = prepare_export(REPORT, book, mapping)


def test_external_activity_is_preserved(book: Book, mapping: Mapping) -> None:
    """Existing bank activity must not be mistaken for imported broker activity."""
    external = Transaction(
        'unrelated',
        date(2024, 1, 5),
        'CURRENCY::RUB',
        'Other banking',
        '',
        (Split(mapping.external, D(50), D(50)), Split('Equity', D(-50), D(-50))),
    )
    book = replace(book, transactions=(*book.transactions, external))
    manifest, _ = prepare_export(REPORT, book, mapping)
    assert (
        next(s for s in manifest.closing if s.account == mapping.external).quantity
        == 50
    )
    imported = replace(book, transactions=(*book.transactions, *manifest.transactions))
    verify_book(imported, manifest)
    repeated, already = prepare_export(REPORT, imported, mapping)
    assert already and repeated == manifest


def test_error_does_not_create_output(tmp_path: Path) -> None:
    """An inconsistent statement cannot leave an importable partial artifact."""
    output = tmp_path / 'bad.csv'
    with pytest.raises(ReconciliationError):
        _ = export_report(
            'tests/data/sberbank_report_sample.html', BOOK, MAPPING, output
        )
    assert list(tmp_path.iterdir()) == []


def test_no_overwrite(tmp_path: Path) -> None:
    """Protect pre-existing output rather than silently replacing it."""
    output = tmp_path / 'existing.csv'
    _ = output.write_text('keep me')
    with pytest.raises(ReconciliationError, match='already exists'):
        _ = export_report(REPORT, BOOK, MAPPING, output)
    assert output.read_text() == 'keep me'
    assert list(tmp_path.iterdir()) == [output]


def test_cli_export_and_verify(book: Book, manifest: Manifest, tmp_path: Path) -> None:
    """Exercise the user-facing commands with simulated saved-book readback."""
    output = tmp_path / 'cli.csv'
    assert (
        main(
            [
                'export',
                str(REPORT),
                '--book',
                str(BOOK),
                '--mapping',
                str(MAPPING),
                '--output',
                str(output),
            ]
        )
        == 0
    )
    imported = tmp_path / 'saved.sqlite'
    save_sqlite(
        replace(book, transactions=(*book.transactions, *manifest.transactions)),
        imported,
    )
    assert (
        main(
            [
                'verify',
                '--book',
                str(imported),
                '--manifest',
                str(output) + '.manifest.json',
            ]
        )
        == 0
    )
    assert (
        main(
            [
                'verify',
                '--book',
                str(BOOK),
                '--manifest',
                str(output) + '.manifest.json',
            ]
        )
        == 1
    )


def test_real_gnucash_514_import(manifest: Manifest, mapping: Mapping) -> None:
    """Verify the synthetic book actually imported and saved by GnuCash 5.14."""
    imported = read_book('tests/data/gnucash/imported-5.14.gnucash')
    assert len(imported.transactions) == 9
    verify_book(imported, manifest)
    repeated, already = prepare_export(REPORT, imported, mapping)
    assert already and repeated == manifest
    assert (
        next(c for c in imported.commodities if c.key == 'CURRENCY::RUB').fraction
        == 100
    )


def test_actual_import_repeat_writes_nothing(tmp_path: Path) -> None:
    """A saved native import suppresses a second CSV without modifying the book."""
    path = Path('tests/data/gnucash/imported-5.14.gnucash')
    before = path.read_bytes()
    result = export_report(REPORT, path, MAPPING, tmp_path / 'repeat.csv')
    assert result.already_imported and result.transactions == 8
    assert list(tmp_path.iterdir()) == []
    assert path.read_bytes() == before


def test_note_flattening_does_not_hide_provenance_changes(manifest: Manifest) -> None:
    """Tolerate native line-break flattening, but not changed source references."""
    imported = read_book('tests/data/gnucash/imported-5.14.gnucash')
    changed = tuple(
        replace(
            t, notes=t.notes.replace('source: cash_flow:1', 'source: cash_flow:999')
        )
        for t in imported.transactions
    )
    with pytest.raises(ReconciliationError):
        verify_book(replace(imported, transactions=changed), manifest)


def test_export_notes_are_single_line(manifest: Manifest) -> None:
    """Avoid importer-dependent multiline Notes while keeping complete provenance."""
    rows = list(csv.DictReader(io.StringIO(render_csv(manifest))))
    assert all('\n' not in row['Notes'] and ' source: ' in row['Notes'] for row in rows)


def test_missing_security_fraction_still_rejected(tmp_path: Path) -> None:
    """Only built-in currencies may omit their standalone fraction."""
    path = tmp_path / 'bad.gnucash'
    _ = path.write_text(
        BOOK.read_text().replace('<cmdty:fraction>10000</cmdty:fraction>', '')
    )
    with pytest.raises(ReconciliationError, match='cmdty:fraction'):
        _ = read_book(path)
