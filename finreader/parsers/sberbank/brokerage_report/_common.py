"""
Shared helper functions for parsing Sberbank brokerage reports.

This module provides common utilities for all table parsers in the
sberbank.brokerage_report package.

CONVENTIONS for all table parsers:

1. Field Naming:
   - Use English field names in dataclass models
   - Follow PEP 8 for naming conventions (snake_case for fields)

2. Optional Fields:
   - Empty or &nbsp;-only cells should be parsed as None
   - Use Optional[T] type hints for fields that may be None

3. Monetary Values:
   - Use Decimal for all monetary amounts and prices
   - Use int for quantities and counts
   - Use date and time from datetime module for dates/times

4. Helper Usage:
   - parse_soup(): Parse HTML file with BeautifulSoup (lxml parser)
   - find_table_by_title(): Find table by title prefix using document-order pairing
   - iter_data_rows(): Iterate over data rows, skipping row-number, summary, and section rows
   - iter_section_rows(): Iterate over section rows (e.g., "Площадка: Фондовый рынок")
   - parse_money(): Parse monetary values, strips spaces, U+00A0, and leading +
   - parse_int(): Parse integer values, strips whitespace and nbsp
   - parse_date(): Parse dates in DD.MM.YYYY format
   - parse_time(): Parse times in HH:MM:SS format
   - cell_text(): Extract and normalize cell text (strips whitespace, normalizes &nbsp;)

5. Error Handling:
   - Raise ValueError with descriptive messages for unparseable content
   - Do not silently assert or drop data
"""

from datetime import date, time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from bs4 import BeautifulSoup, Tag


def row_classes(tag: Tag) -> list[str]:
    """
    Return the 'class' attribute of *tag* as a list of strings.

    BeautifulSoup types ``class`` as ``str | list[str] | None`` because HTML
    allows either form; in real Sberbank reports it is always multi-valued.
    This helper centralises the narrowing so every table parser gets a
    plain ``list[str]`` to iterate or test membership against.

    Args:
        tag: BeautifulSoup Tag (e.g. a ``<tr>`` or ``<td>``).

    Returns:
        List of class names; empty list if the attribute is absent.

    """
    value = tag.get('class')
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def int_attr(tag: Tag, name: str, default: int = 0) -> int:
    """
    Return integer value of a tag attribute, or *default* if missing.

    BeautifulSoup types attribute values as ``str | list[str] | None``.
    ``colspan``/``rowspan`` are always single numeric strings in practice;
    this helper performs the narrowing and parsing in one place.

    Args:
        tag: BeautifulSoup Tag.
        name: Attribute name (e.g. ``'colspan'``).
        default: Value to return when the attribute is absent or malformed.

    Returns:
        Parsed integer, or *default*.

    """
    value = tag.get(name)
    if value is None:
        return default
    if isinstance(value, list):
        if not value:
            return default
        value = value[0]
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_soup(path: str | Path) -> BeautifulSoup:
    """
    Open file and parse with lxml parser.

    Args:
        path: Path to HTML file.

    Returns:
        BeautifulSoup object parsed with lxml.

    """
    with open(path, encoding='utf-8') as f:
        return BeautifulSoup(f, 'lxml')


def find_table_by_title(soup: BeautifulSoup, title_prefix: str) -> Tag | None:
    """
    Find table by title prefix using document-order pairing.

    This function walks through <p> and <table> elements in document order,
    tracking the most recent <p>'s stripped text. When a <table> is reached,
    it is associated with the last seen <p>. Returns the unique table whose
    associated title startswith(title_prefix), rejecting duplicate sections.
    A heading is consumed once, so an untitled footer table cannot reuse it.

    This is more robust than previous_sibling walks because it handles
    the actual document structure of Sberbank reports.

    Args:
        soup: BeautifulSoup object.
        title_prefix: Prefix to match against table titles.

    Returns:
        Tag object for the matching table, or None if not found.

    """
    last_p_text = ''
    matched: Tag | None = None
    for element in soup.find_all(['p', 'table']):
        if element.name == 'p':
            last_p_text = element.get_text(strip=True)
        elif element.name == 'table':
            if last_p_text.startswith(title_prefix):
                if matched is not None:
                    raise ValueError(f'{title_prefix}: duplicate section')
                matched = element
            last_p_text = ''
    return matched


def iter_data_rows(table: Tag) -> list[list[str]]:
    """
    Yield cell-text lists for data rows.

    Skips:
    - Row-number rows (class="rn")
    - Summary rows (class="summary-row" or "summary-row2")
    - Section rows (first cell has colspan > 1 and text starting with
      "Площадка:", "Ставка", etc.)

    Section rows are exposed separately via iter_section_rows().

    Args:
        table: BeautifulSoup Tag representing a table.

    Returns:
        List of data rows, where each row is a list of cell text values.

    """
    data_rows: list[list[str]] = []
    for row in table.find_all('tr'):
        if has_table_header(row):
            continue

        classes = row_classes(row)
        if any(cls.startswith('rn') for cls in classes):
            continue

        if any(cls in ('summary-row', 'summary-row2') for cls in classes):
            continue

        # Check for section rows (first cell has colspan > 1)
        first_cell = row.find('td')
        if first_cell and int_attr(first_cell, 'colspan', 1) > 1:
            cell_text_val = cell_text(first_cell)
            if not cell_text_val or cell_text_val.startswith(
                ('Площадка:', 'Ставка', 'Итого')
            ):
                continue

        # Extract cell text for data rows
        cells = [cell_text(cell) for cell in row.find_all(['td', 'th'])]
        if cells:  # Only add non-empty rows
            data_rows.append(cells)

    return data_rows


def iter_section_rows(table: Tag) -> list[str]:
    """
    Yield section row texts.

    Section rows are rows where the first cell has colspan > 1 and contains
    text like "Площадка: Фондовый рынок" or "Ставка 13%".

    Args:
        table: BeautifulSoup Tag representing a table.

    Returns:
        List of section row text values.

    """
    section_rows: list[str] = []
    for row in table.find_all('tr'):
        first_cell = row.find('td')
        if first_cell and int_attr(first_cell, 'colspan', 1) > 1:
            cell_text_val = cell_text(first_cell)
            if cell_text_val.startswith(('Площадка:', 'Ставка')):
                section_rows.append(cell_text_val)

    return section_rows


def parse_money(text: str | None) -> Decimal | None:
    """
    Parse monetary value.

    Strips:
    - Whitespace (regular spaces)
    - U+00A0 (non-breaking space, used as thousands separator in tax tables)
    - Leading '+' sign

    Preserves:
    - Leading '-' sign

    Returns Decimal or None if empty/&nbsp;-only.

    Args:
        text: String to parse or None.

    Returns:
        Decimal value or None.

    """
    if text is None or not text.strip():
        return None

    # Strip whitespace and nbsp
    cleaned = text.strip().replace('\xa0', '').replace(' ', '')

    # Strip leading + (but preserve -)
    if cleaned.startswith('+'):
        cleaned = cleaned[1:]

    # Replace comma with period for Decimal parsing
    cleaned = cleaned.replace(',', '.')

    try:
        value = Decimal(cleaned)
    except InvalidOperation as error:
        raise ValueError(f'Invalid monetary value: {text!r}') from error
    if not value.is_finite():
        raise ValueError(f'Non-finite monetary value: {text!r}')
    return value


def parse_int(text: str | None) -> int | None:
    """
    Parse integer value.

    Strips whitespace and nbsp. Returns int or None if empty.

    Args:
        text: String to parse or None.

    Returns:
        Integer value or None.

    """
    if text is None or not text.strip():
        return None

    # Strip whitespace and nbsp
    cleaned = text.strip().replace('\xa0', '').replace(' ', '')

    return int(cleaned)


def parse_date(text: str | None) -> date | None:
    """
    Parse date in DD.MM.YYYY format.

    Args:
        text: String to parse or None.

    Returns:
        Date object or None.

    """
    if text is None or not text.strip():
        return None

    import datetime as dt

    return dt.datetime.strptime(text.strip(), '%d.%m.%Y').date()


def parse_time(text: str | None) -> time | None:
    """
    Parse time in HH:MM:SS format.

    Args:
        text: String to parse or None.

    Returns:
        Time object or None.

    """
    if text is None or not text.strip():
        return None

    import datetime as dt

    return dt.datetime.strptime(text.strip(), '%H:%M:%S').time()


def cell_text(tag: Tag | None) -> str:
    """
    Extract cell text with &nbsp; normalization.

    Args:
        tag: BeautifulSoup Tag or None.

    Returns:
        Stripped text with &nbsp; normalized to space.

    """
    if tag is None:
        return ''

    # Get text and normalize nbsp to space
    text = tag.get_text(separator=' ', strip=True)
    return text.replace('\xa0', ' ')


def has_table_header(row: Tag) -> bool:
    """
    Check if a row is a table header row.

    A row is a header row if:
    - The row has the 'table-header' class, OR
    - Any cell in the row has the 'table-header' class, OR
    - The row has align="center"

    Args:
        row: BeautifulSoup Tag representing a table row.

    Returns:
        True if the row is a header row, False otherwise.

    """
    if 'table-header' in row_classes(row):
        return True

    if row.get('align') == 'center':
        return True

    for cell in row.find_all(['td', 'th']):
        if any('table-header' in cls for cls in row_classes(cell)):
            return True
    return False
