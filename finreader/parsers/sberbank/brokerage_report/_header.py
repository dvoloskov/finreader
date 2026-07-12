"""
Report header parsing for Sberbank brokerage reports.

This module defines the ReportHeader dataclass and parse_header() function
for extracting the report period, investor, and contract information from
the header section of Sberbank brokerage HTML reports.
"""

import re
from dataclasses import dataclass
from datetime import date

from bs4 import BeautifulSoup, Tag

from finreader.parsers.sberbank.brokerage_report._common import parse_date


@dataclass(frozen=True)
class ReportHeader:
    """
    Header information from a Sberbank brokerage report.

    Attributes:
        start_date: Report period start date.
        end_date: Report period end date.
        creation_date: Report creation date.
        investor: Investor name (may contain Cyrillic characters).
        contract_code: Brokerage contract code (alphanumeric).
        contract_date: Contract signing date.

    """

    start_date: date
    end_date: date
    creation_date: date
    investor: str
    contract_code: str
    contract_date: date


# Regex patterns from plan
_PERIOD_REGEX = re.compile(
    r'за период с (\d\d\.\d\d\.\d{4}) по (\d\d\.\d\d\.\d{4}),\s*дата создания (\d\d\.\d\d\.\d{4})'
)

# Investor/contract regex: non-greedy capture up to " Договор"
_INVESTOR_CONTRACT_REGEX = re.compile(
    r'Инвестор: (.+?) Договор ([A-Z0-9]+)\s+от\s+(\d\d\.\d\d\.\d{4})'
)


def parse_header(soup: BeautifulSoup) -> ReportHeader:
    """
    Parse report header from BeautifulSoup object.

    Extracts:
    - Period (start_date, end_date, creation_date) from <h3> element
    - Investor, contract_code, contract_date from following <p> element

    Args:
        soup: BeautifulSoup object containing the HTML report.

    Returns:
        ReportHeader dataclass with all header fields populated.

    Raises:
        ValueError: If header cannot be parsed (missing elements or malformed
            content). Exception message describes what went wrong.

    """
    # Find the <h3> element containing period information
    h3 = soup.find('h3')
    if h3 is None:
        raise ValueError('Cannot parse report header: <h3> element not found')

    # Get text from h3 and normalize whitespace
    h3_text = h3.get_text(strip=True, separator=' ')

    # Extract period dates using regex
    period_match = _PERIOD_REGEX.search(h3_text)
    if not period_match:
        raise ValueError(
            'Cannot parse report header: period string not found in <h3> '
            + "(expected format: 'за период с DD.MM.YYYY по DD.MM.YYYY, дата создания DD.MM.YYYY')"
        )

    start_str, end_str, creation_str = period_match.groups()
    start_date = parse_date(start_str)
    assert start_date is not None, 'Report header start date missing'
    end_date = parse_date(end_str)
    assert end_date is not None, 'Report header end date missing'
    creation_date = parse_date(creation_str)
    assert creation_date is not None, 'Report header creation date missing'

    # Find the <p> element following h3 with investor/contract information
    # Use next_sibling to get the element immediately after h3
    next_element = h3.next_sibling
    p_element = None

    # Skip text/comment nodes and find the next <p>
    while next_element:
        if isinstance(next_element, Tag) and next_element.name == 'p':
            p_element = next_element
            break
        next_element = next_element.next_sibling

    if p_element is None:
        raise ValueError(
            'Cannot parse report header: <p> element with investor/contract not found'
        )

    # Get text from p and normalize whitespace
    p_text = p_element.get_text(strip=True, separator=' ')

    # Extract investor and contract using regex
    contract_match = _INVESTOR_CONTRACT_REGEX.search(p_text)
    if not contract_match:
        raise ValueError(
            'Cannot parse report header: investor/contract not found in <p> '
            + "(expected format: 'Инвестор: <name> Договор <code> от DD.MM.YYYY')"
        )

    investor, contract_code, contract_date_str = contract_match.groups()
    contract_date = parse_date(contract_date_str)
    assert contract_date is not None, 'Report header contract date missing'

    # Strip trailing spaces from investor name
    investor = investor.strip()

    return ReportHeader(
        start_date=start_date,
        end_date=end_date,
        creation_date=creation_date,
        investor=investor,
        contract_code=contract_code,
        contract_date=contract_date,
    )
