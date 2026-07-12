"""
Parse the 'Справочник Ценных Бумаг' (securities) table.

This module defines dataclasses for security reference data and provides
the parser function.
"""

from dataclasses import dataclass

from bs4 import BeautifulSoup

from .._common import find_table_by_title, iter_data_rows


@dataclass(frozen=True)
class Security:
    """Single security entry from the reference table."""

    name: str
    code: str
    isin: str
    issuer: str
    kind: str
    issue: str


@dataclass(frozen=True)
class Securities:
    """Container for the securities table."""

    rows: list[Security]


def parse_securities(soup: BeautifulSoup) -> Securities | None:
    """
    Parse the securities table from BeautifulSoup object.

    Args:
        soup: BeautifulSoup object containing the HTML report.

    Returns:
        Securities dataclass with rows, or None if table absent.

    """
    table = find_table_by_title(soup, 'Справочник Ценных Бумаг')
    if table is None:
        return None

    rows: list[Security] = []
    for row_text_list in iter_data_rows(table):
        if len(row_text_list) != 6:
            continue

        name = row_text_list[0]
        code = row_text_list[1]
        isin = row_text_list[2]
        issuer = row_text_list[3]
        kind = row_text_list[4]
        issue = row_text_list[5]

        rows.append(Security(name, code, isin, issuer, kind, issue))

    return Securities(rows)
