"""Command-line export and read-only saved-book verification."""

import argparse
from collections.abc import Sequence
from decimal import DecimalException
from pathlib import Path
import sqlite3
import sys
from xml.etree.ElementTree import ParseError

from finreader.gnucash.book import read_book
from finreader.gnucash.export import export_report, load_manifest, verify_book


class Arguments(argparse.Namespace):
    """Typed argparse boundary; command-specific required fields are enforced by argparse."""

    command: str = ''
    report: Path = Path()
    book: Path = Path()
    mapping: Path = Path()
    output: Path = Path()
    manifest: Path = Path()


def main(argv: Sequence[str] | None = None) -> int:
    """Run a guarded export/verify command, reporting failures without tracebacks."""
    parser = argparse.ArgumentParser(
        description='Sberbank RUB bond reports → GnuCash 5 CSV (closed snapshots only).'
    )
    commands = parser.add_subparsers(dest='command', required=True)
    export = commands.add_parser(
        'export', help='Validate and export; never modifies the book'
    )
    _ = export.add_argument('report', type=Path)
    _ = export.add_argument('--book', required=True, type=Path)
    _ = export.add_argument('--mapping', required=True, type=Path)
    _ = export.add_argument('--output', required=True, type=Path)
    verify = commands.add_parser(
        'verify', help='Check a saved imported book against its manifest'
    )
    _ = verify.add_argument('--book', required=True, type=Path)
    _ = verify.add_argument('--manifest', required=True, type=Path)
    args = parser.parse_args(argv, namespace=Arguments())
    try:
        if args.command == 'export':
            result = export_report(args.report, args.book, args.mapping, args.output)
            if result.already_imported:
                print(
                    f'Already imported and verified: {result.transactions} transactions; no files written.'
                )
            else:
                print(
                    f'Exported {result.transactions} transactions to {result.csv_path}'
                )
                print(f'Manifest: {result.manifest_path}')
                print(
                    'Not yet imported. Import into a disposable GnuCash 5.x book, save/close, then run verify.'
                )
        else:
            verify_book(read_book(args.book), load_manifest(args.manifest))
            print(
                'Verified transactions, split quantities/values and opening/closing balances.'
            )
    except (
        ValueError,
        OSError,
        sqlite3.Error,
        ParseError,
        DecimalException,
        KeyError,
    ) as error:
        print(f'finreader: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
